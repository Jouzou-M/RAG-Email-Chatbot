from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from email_rag.config import settings
from email_rag.rag.prompt import build_messages, format_context
from email_rag.rag.chain import RAGChain
from email_rag.rag.conversation import ConversationMemory
from email_rag.vectorstore.store import EmailVectorStore

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Result from the retrieval pipeline."""

    results: list[dict[str, Any]] = field(default_factory=list)
    query: str = ""
    filters_applied: dict[str, Any] = field(default_factory=dict)


@dataclass
class QueryFilters:
    """Parsed metadata filters from a natural language query."""

    sender: str | None = None
    date_after: datetime | None = None
    date_before: datetime | None = None
    labels: list[str] | None = None
    subject_contains: str | None = None
    is_sent: bool | None = None


class EmailRetriever:
    """
    Orchestrates the full RAG pipeline:
    1. Parse query for implicit metadata filters
    2. Search vector store with filters
    3. Deduplicate results across chunks
    4. Format context and generate response
    """

    def __init__(
        self,
        vector_store: EmailVectorStore,
        chain: RAGChain | None = None,
        memory: ConversationMemory | None = None,
    ) -> None:
        self._store = vector_store
        self._chain = chain or RAGChain()
        self._memory = memory or ConversationMemory()

    @property
    def memory(self) -> ConversationMemory:
        return self._memory

    async def query(
        self,
        question: str,
        session_id: str = "default",
        top_k: int | None = None,
        extra_filters: dict[str, Any] | None = None,
    ) -> tuple[str, list[dict[str, Any]]]:
        """
        Full RAG pipeline: retrieve, format, generate.

        Returns: (answer, sources)
        """
        retrieval = await self.retrieve(question, top_k=top_k, extra_filters=extra_filters)

        context = format_context(retrieval.results)
        history = self._memory.get_history(session_id)
        messages = build_messages(question, context, history)

        answer = await self._chain.generate(messages)

        # Record the turn
        sources = [r["metadata"] for r in retrieval.results]
        self._memory.add_turn(session_id, question, answer, sources)

        return answer, sources

    async def query_stream(
        self,
        question: str,
        session_id: str = "default",
        top_k: int | None = None,
        extra_filters: dict[str, Any] | None = None,
    ):
        """
        Streaming RAG pipeline. Yields tokens as they're generated.

        Returns an async generator of (token, None) tuples during streaming,
        then yields (None, sources) at the end.
        """
        retrieval = await self.retrieve(question, top_k=top_k, extra_filters=extra_filters)

        context = format_context(retrieval.results)
        history = self._memory.get_history(session_id)
        messages = build_messages(question, context, history)

        sources = [r["metadata"] for r in retrieval.results]
        full_response: list[str] = []

        async for token in self._chain.stream(messages):
            full_response.append(token)
            yield token, None

        # Record the complete turn
        answer = "".join(full_response)
        self._memory.add_turn(session_id, question, answer, sources)

        yield None, sources

    async def retrieve(
        self,
        question: str,
        top_k: int | None = None,
        extra_filters: dict[str, Any] | None = None,
    ) -> RetrievalResult:
        """Retrieve relevant email chunks for a question."""
        top_k = top_k or settings.retrieval_top_k

        # Parse implicit filters from the query
        filters = parse_query_filters(question)
        where = _build_where_clause(filters, extra_filters)

        results = await self._store.search(
            query=question,
            top_k=top_k,
            where=where if where else None,
        )

        # Deduplicate: keep best chunk per email
        results = _deduplicate_by_email(results)

        return RetrievalResult(
            results=results,
            query=question,
            filters_applied=where or {},
        )


def parse_query_filters(query: str) -> QueryFilters:
    """
    Extract implicit metadata filters from natural language queries.
    Uses regex heuristics for speed (no LLM call needed).
    """
    filters = QueryFilters()
    query_lower = query.lower()

    # Detect time references FIRST — so we can exclude false-positive sender matches
    # like "from this week" (sender="this") or "from last month" (sender="last").
    now = datetime.now(timezone.utc)
    _TIME_WORDS = {"today", "yesterday", "this", "last", "the", "my", "all", "any", "recent"}
    if "today" in query_lower:
        filters.date_after = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif "yesterday" in query_lower:
        yesterday = now - timedelta(days=1)
        filters.date_after = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        filters.date_before = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif "this week" in query_lower:
        start_of_week = now - timedelta(days=now.weekday())
        filters.date_after = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    elif "last week" in query_lower:
        start_of_last_week = now - timedelta(days=now.weekday() + 7)
        end_of_last_week = start_of_last_week + timedelta(days=7)
        filters.date_after = start_of_last_week.replace(hour=0, minute=0, second=0, microsecond=0)
        filters.date_before = end_of_last_week.replace(hour=0, minute=0, second=0, microsecond=0)
    elif "this month" in query_lower:
        filters.date_after = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif "last month" in query_lower:
        first_of_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_month = first_of_this_month - timedelta(days=1)
        filters.date_after = last_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        filters.date_before = first_of_this_month

    # Detect sender references: "from john", "emails from sarah@..."
    # Run AFTER time detection to exclude false positives like "from this week".
    sender_match = re.search(
        r"(?:from|by|sent by)\s+([a-zA-Z0-9_.+-]+(?:@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)?)",
        query_lower,
    )
    if sender_match:
        candidate = sender_match.group(1)
        # Exclude time-related words that follow "from" in date phrases
        if candidate not in _TIME_WORDS:
            filters.sender = candidate

    # Detect sent vs received
    if any(phrase in query_lower for phrase in ["i sent", "i wrote", "my sent", "emails i sent"]):
        filters.is_sent = True
    elif any(phrase in query_lower for phrase in ["i received", "sent to me", "inbox"]):
        filters.is_sent = False

    return filters


def _build_where_clause(
    filters: QueryFilters,
    extra_filters: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Convert parsed filters into a ChromaDB where clause."""
    conditions: list[dict[str, Any]] = []

    if filters.sender:
        if "@" in filters.sender:
            # Full email address — exact match on sender field
            conditions.append({"sender": filters.sender})
        # For name-only senders (no "@"), don't add a metadata filter.
        # ChromaDB doesn't support substring matching, and sender_domain
        # won't match a person's name. The semantic search will naturally
        # rank emails from/about this person higher.

    if filters.date_after:
        conditions.append({"date_timestamp": {"$gte": filters.date_after.timestamp()}})

    if filters.date_before:
        conditions.append({"date_timestamp": {"$lte": filters.date_before.timestamp()}})

    if filters.is_sent is not None:
        conditions.append({"is_sent": filters.is_sent})

    if extra_filters:
        # Flatten: if extra_filters is {"$and": [...]}, merge the inner conditions
        # directly instead of nesting $and inside $and.
        if "$and" in extra_filters:
            conditions.extend(extra_filters["$and"])
        else:
            for key, value in extra_filters.items():
                conditions.append({key: value})

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


def _deduplicate_by_email(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only the best-scoring chunk per email message."""
    seen: dict[str, dict[str, Any]] = {}
    for result in results:
        msg_id = result.get("metadata", {}).get("message_id", result["id"])
        if msg_id not in seen or result["distance"] < seen[msg_id]["distance"]:
            seen[msg_id] = result
    return sorted(seen.values(), key=lambda r: r["distance"])
