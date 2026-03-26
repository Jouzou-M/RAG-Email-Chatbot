from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from email_rag.gmail.models import EmailMessage


def extract_chunk_metadata(message: EmailMessage, chunk_index: int, total_chunks: int) -> dict[str, Any]:
    """
    Build the metadata dict stored alongside each chunk in the vector store.
    All values must be ChromaDB-compatible types: str, int, float, bool.
    """
    date_ts = message.date.timestamp() if message.date else 0.0
    date_iso = message.date.isoformat() if message.date else ""

    return {
        "message_id": message.id,
        "thread_id": message.thread_id,
        "subject": message.subject,
        "sender": message.sender,
        "sender_name": message.sender_name,
        "sender_domain": message.sender_domain,
        "recipients_to": json.dumps(message.recipients_to),
        "recipients_cc": json.dumps(message.recipients_cc),
        "date": date_iso,
        "date_timestamp": date_ts,
        "labels": json.dumps(message.labels),
        "is_sent": message.is_sent,
        "has_attachments": message.has_attachments,
        "snippet": message.snippet[:200],
        "chunk_index": chunk_index,
        "total_chunks": total_chunks,
    }


def build_context_string(metadata: dict[str, Any]) -> str:
    """
    Format metadata into a human-readable header for RAG context injection.
    """
    sender = metadata.get("sender_name") or metadata.get("sender", "Unknown")
    date = metadata.get("date", "Unknown date")
    subject = metadata.get("subject", "(no subject)")

    return f"From: {sender} | Date: {date} | Subject: {subject}"


def parse_date_filter(date_str: str) -> datetime | None:
    """Parse a date string into a datetime for filtering. Supports ISO format and common formats."""
    formats = [
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%m/%d/%Y",
        "%d/%m/%Y",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None
