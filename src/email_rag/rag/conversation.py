from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConversationTurn:
    """A single turn in a conversation."""

    user_query: str
    assistant_response: str
    sources: list[dict[str, Any]] = field(default_factory=list)


class ConversationMemory:
    """
    Manages multi-turn conversation state per session.
    Keeps the last N turns for context injection.
    """

    def __init__(self, max_turns: int = 10, max_sessions: int = 1000) -> None:
        self._max_turns = max_turns
        self._max_sessions = max_sessions
        self._sessions: dict[str, list[ConversationTurn]] = {}

    def add_turn(
        self,
        session_id: str,
        user_query: str,
        assistant_response: str,
        sources: list[dict[str, Any]] | None = None,
    ) -> None:
        """Record a conversation turn."""
        if session_id not in self._sessions:
            # Evict oldest session if at capacity to prevent unbounded memory growth
            if len(self._sessions) >= self._max_sessions:
                oldest_key = next(iter(self._sessions))
                del self._sessions[oldest_key]
            self._sessions[session_id] = []

        self._sessions[session_id].append(
            ConversationTurn(
                user_query=user_query,
                assistant_response=assistant_response,
                sources=sources or [],
            )
        )

        # Trim to max turns
        if len(self._sessions[session_id]) > self._max_turns:
            self._sessions[session_id] = self._sessions[session_id][-self._max_turns :]

    def get_history(self, session_id: str) -> list[dict[str, str]]:
        """
        Get conversation history formatted as message dicts for LLM context.
        Returns list of {role: "user"/"assistant", content: ...} dicts.
        """
        turns = self._sessions.get(session_id, [])
        messages: list[dict[str, str]] = []
        for turn in turns:
            messages.append({"role": "user", "content": turn.user_query})
            messages.append({"role": "assistant", "content": turn.assistant_response})
        return messages

    def get_turns(self, session_id: str) -> list[ConversationTurn]:
        """Get raw conversation turns for a session."""
        return self._sessions.get(session_id, [])

    def clear_session(self, session_id: str) -> None:
        """Clear all history for a session."""
        self._sessions.pop(session_id, None)

    def has_session(self, session_id: str) -> bool:
        return session_id in self._sessions and len(self._sessions[session_id]) > 0
