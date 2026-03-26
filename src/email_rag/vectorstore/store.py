from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import chromadb

from email_rag.config import settings
from email_rag.embeddings import get_embedding_provider
from email_rag.embeddings.base import EmbeddingProvider
from email_rag.gmail.models import EmailMessage, SyncState
from email_rag.processing.chunker import chunk_text
from email_rag.processing.metadata import extract_chunk_metadata
from email_rag.processing.parser import get_clean_body
from email_rag.vectorstore.schema import make_chunk_id, validate_metadata

logger = logging.getLogger(__name__)

SYNC_COLLECTION = "_sync_metadata"


class EmailVectorStore:
    """ChromaDB-backed vector store for email chunks with hybrid search."""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider | None = None,
        persist_dir: str | None = None,
        collection_name: str | None = None,
    ) -> None:
        persist = persist_dir or str(settings.chroma_persist_dir)
        self._collection_name = collection_name or settings.chroma_collection_name
        self._embedder = embedding_provider or get_embedding_provider()

        self._client = chromadb.PersistentClient(path=persist)
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._sync_collection = self._client.get_or_create_collection(
            name=SYNC_COLLECTION,
        )
        logger.info(
            "Vector store initialized: %d documents in '%s'",
            self._collection.count(),
            self._collection_name,
        )

    @property
    def count(self) -> int:
        return self._collection.count()

    async def add_emails(self, messages: list[EmailMessage]) -> int:
        """Process, chunk, embed, and upsert emails. Returns number of chunks added."""
        if not messages:
            return 0

        all_texts: list[str] = []
        all_ids: list[str] = []
        all_metadata: list[dict[str, Any]] = []
        emails_with_body = 0

        for msg in messages:
            body = get_clean_body(msg.body_text, msg.body_html)
            if not body.strip():
                continue
            emails_with_body += 1

            chunks = chunk_text(body)
            for chunk in chunks:
                doc_id = make_chunk_id(msg.id, chunk.chunk_index)
                meta = extract_chunk_metadata(msg, chunk.chunk_index, chunk.total_chunks)
                meta = validate_metadata(meta)

                all_texts.append(chunk.text)
                all_ids.append(doc_id)
                all_metadata.append(meta)

        if not all_texts:
            return 0

        # Embed all chunks
        logger.info(
            "Embedding %d chunks from %d emails (%d skipped, no body)",
            len(all_texts), emails_with_body, len(messages) - emails_with_body,
        )
        embeddings = await self._embedder.embed_documents(all_texts)

        # Upsert in batches (ChromaDB limit: ~41666 per batch)
        batch_size = 5000
        for i in range(0, len(all_texts), batch_size):
            end = min(i + batch_size, len(all_texts))
            self._collection.upsert(
                ids=all_ids[i:end],
                documents=all_texts[i:end],
                embeddings=embeddings[i:end],
                metadatas=all_metadata[i:end],
            )

        logger.info("Upserted %d chunks", len(all_texts))
        return len(all_texts)

    async def search(
        self,
        query: str,
        top_k: int | None = None,
        where: dict[str, Any] | None = None,
        where_document: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search for relevant email chunks.

        Args:
            query: Natural language query.
            top_k: Number of results to return.
            where: ChromaDB metadata filter (e.g., {"sender": "john@example.com"}).
            where_document: ChromaDB document content filter.

        Returns:
            List of dicts with keys: id, document, metadata, distance.
        """
        top_k = top_k or settings.retrieval_top_k

        # ChromaDB raises an error when n_results exceeds available documents
        collection_count = self._collection.count()
        if collection_count == 0:
            return []
        top_k = min(top_k, collection_count)

        query_embedding = await self._embedder.embed_query(query)

        kwargs: dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": top_k,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where
        if where_document:
            kwargs["where_document"] = where_document

        try:
            results = self._collection.query(**kwargs)
        except Exception as e:
            # Filters can narrow results below n_results — return empty on error
            if "not enough" in str(e).lower() or "insufficient" in str(e).lower():
                logger.warning("Search returned fewer results than requested: %s", e)
                return []
            raise

        items: list[dict[str, Any]] = []
        if not results["ids"] or not results["ids"][0]:
            return items

        for i, doc_id in enumerate(results["ids"][0]):
            items.append(
                {
                    "id": doc_id,
                    "document": results["documents"][0][i] if results["documents"] else "",
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else 1.0,
                }
            )

        return items

    def delete_emails(self, message_ids: list[str]) -> int:
        """Delete all chunks for the given message IDs."""
        if not message_ids:
            return 0

        # Fetch existing chunks for these messages
        deleted = 0
        for msg_id in message_ids:
            results = self._collection.get(
                where={"message_id": msg_id},
                include=[],
            )
            if results["ids"]:
                self._collection.delete(ids=results["ids"])
                deleted += len(results["ids"])

        logger.info("Deleted %d chunks for %d messages", deleted, len(message_ids))
        return deleted

    def clear(self) -> None:
        """Delete all documents from the collection."""
        self._client.delete_collection(self._collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("Cleared collection '%s'", self._collection_name)

    # --- Sync State Management ---

    def get_sync_state(self) -> SyncState:
        """Load the persisted sync state from ChromaDB."""
        try:
            result = self._sync_collection.get(ids=["sync_state"], include=["metadatas"])
            if result["ids"]:
                meta = result["metadatas"][0]
                return SyncState(
                    last_history_id=meta.get("last_history_id") or None,
                    last_sync_at=(
                        datetime.fromisoformat(meta["last_sync_at"])
                        if meta.get("last_sync_at")
                        else None
                    ),
                    total_messages_synced=int(meta.get("total_messages_synced", 0)),
                    email_address=meta.get("email_address", ""),
                )
        except Exception:
            pass
        return SyncState()

    def set_sync_state(self, state: SyncState) -> None:
        """Persist sync state to ChromaDB."""
        meta = {
            "last_history_id": state.last_history_id or "",
            "last_sync_at": state.last_sync_at.isoformat() if state.last_sync_at else "",
            "total_messages_synced": state.total_messages_synced,
            "email_address": state.email_address,
        }
        self._sync_collection.upsert(
            ids=["sync_state"],
            documents=["sync_state"],
            metadatas=[meta],
        )

    def get_stats(self) -> dict[str, Any]:
        """Return collection statistics."""
        sync_state = self.get_sync_state()
        return {
            "total_chunks": self._collection.count(),
            "collection_name": self._collection_name,
            "last_sync_at": sync_state.last_sync_at.isoformat() if sync_state.last_sync_at else None,
            "total_messages_synced": sync_state.total_messages_synced,
            "email_address": sync_state.email_address,
        }
