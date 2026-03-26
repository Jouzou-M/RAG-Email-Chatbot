from __future__ import annotations

from typing import Any

# Metadata fields stored per chunk in ChromaDB.
# All values must be: str, int, float, or bool (ChromaDB constraint).
METADATA_FIELDS = [
    "message_id",
    "thread_id",
    "subject",
    "sender",
    "sender_name",
    "sender_domain",
    "recipients_to",     # JSON-encoded list
    "recipients_cc",     # JSON-encoded list
    "date",              # ISO 8601
    "date_timestamp",    # float, for range queries
    "labels",            # JSON-encoded list
    "is_sent",
    "has_attachments",
    "snippet",
    "chunk_index",
    "total_chunks",
]


def make_chunk_id(message_id: str, chunk_index: int) -> str:
    """Generate a deterministic ChromaDB document ID for a chunk."""
    return f"{message_id}_{chunk_index}"


def validate_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Ensure all metadata values are ChromaDB-compatible types."""
    cleaned: dict[str, Any] = {}
    for key, value in metadata.items():
        if value is None:
            cleaned[key] = ""
        elif isinstance(value, (str, int, float, bool)):
            cleaned[key] = value
        else:
            cleaned[key] = str(value)
    return cleaned
