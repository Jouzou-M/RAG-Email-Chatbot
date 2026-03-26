from __future__ import annotations

from datetime import datetime, timezone

from email_rag.gmail.models import EmailMessage, EmailThread
from email_rag.processing.parser import get_clean_body

_DATETIME_MIN_UTC = datetime.min.replace(tzinfo=timezone.utc)


def reconstruct_thread(thread: EmailThread) -> str:
    """
    Reconstruct an email thread as a formatted conversation string.
    Messages are ordered chronologically.
    """
    if not thread.messages:
        return ""

    parts: list[str] = []
    parts.append(f"Thread: {thread.subject}")
    parts.append(f"Participants: {', '.join(thread.participants)}")
    parts.append(f"Messages: {thread.message_count}")
    parts.append("=" * 60)

    for msg in thread.messages:
        date_str = msg.date.strftime("%Y-%m-%d %H:%M") if msg.date else "Unknown"
        sender = msg.sender_name or msg.sender
        body = get_clean_body(msg.body_text, msg.body_html)

        parts.append(f"\n[{date_str}] {sender}:")
        parts.append(body[:2000] if len(body) > 2000 else body)
        parts.append("-" * 40)

    return "\n".join(parts)


def group_messages_by_thread(
    messages: list[EmailMessage],
) -> dict[str, list[EmailMessage]]:
    """Group a flat list of messages by thread_id."""
    threads: dict[str, list[EmailMessage]] = {}
    for msg in messages:
        threads.setdefault(msg.thread_id, []).append(msg)

    # Sort messages within each thread by date
    for thread_msgs in threads.values():
        thread_msgs.sort(key=lambda m: m.date or _DATETIME_MIN_UTC)

    return threads


def get_thread_summary(messages: list[EmailMessage]) -> str:
    """Generate a brief summary line for a thread."""
    if not messages:
        return ""

    subject = messages[0].subject
    participants = list({m.sender_name or m.sender for m in messages})
    count = len(messages)
    date_range = ""

    if messages[0].date and messages[-1].date:
        start = messages[0].date.strftime("%Y-%m-%d")
        end = messages[-1].date.strftime("%Y-%m-%d")
        date_range = f" ({start} to {end})" if start != end else f" ({start})"

    return f"{subject} — {count} messages between {', '.join(participants[:3])}{date_range}"
