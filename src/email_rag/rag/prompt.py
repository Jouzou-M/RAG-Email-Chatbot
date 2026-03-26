from __future__ import annotations

from typing import Any

SYSTEM_PROMPT = """\
You are an intelligent email assistant with access to the user's email archive. \
Your role is to answer questions about their emails accurately and helpfully.

Rules:
1. Always cite your sources. For each claim, reference the email by sender, date, and subject.
2. If the retrieved emails don't contain enough information to answer, say so clearly. \
   Don't fabricate information.
3. When summarizing multiple emails, organize by topic or chronology as appropriate.
4. Preserve the original tone and intent of emails when quoting or paraphrasing.
5. If asked about attachments, mention them but note you can only see metadata (filename, type), \
   not content.
6. For date-related queries, be precise about when emails were sent.

Citation format: [From: sender | Date: YYYY-MM-DD | Subject: ...]
"""


def format_context(results: list[dict[str, Any]]) -> str:
    """Format retrieval results into context for the LLM prompt."""
    if not results:
        return "No relevant emails found."

    sections: list[str] = []
    for i, result in enumerate(results, 1):
        meta = result.get("metadata", {})
        text = result.get("document", "")

        sender = meta.get("sender_name") or meta.get("sender", "Unknown")
        date = meta.get("date", "Unknown date")
        if "T" in date:
            date = date.split("T")[0]
        subject = meta.get("subject", "(no subject)")
        is_sent = meta.get("is_sent", False)
        direction = "Sent by you" if is_sent else f"From: {sender}"

        sections.append(
            f"[Email {i}] {direction} | Date: {date} | Subject: {subject}\n"
            f"---\n{text}\n---"
        )

    return "\n\n".join(sections)


def build_messages(
    query: str,
    context: str,
    conversation_history: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """
    Build the full message list for the LLM call.

    Returns a list of {role, content} dicts.
    """
    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]

    # Add conversation history
    if conversation_history:
        for turn in conversation_history:
            messages.append(turn)

    # Build the user message with context
    user_message = (
        f"Here are the relevant emails from my inbox:\n\n"
        f"{context}\n\n"
        f"My question: {query}"
    )
    messages.append({"role": "user", "content": user_message})

    return messages
