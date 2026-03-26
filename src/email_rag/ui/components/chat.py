from __future__ import annotations

import json

import httpx
import streamlit as st


def render_chat() -> None:
    """Render the main chat interface."""
    # Display message history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("sources"):
                _render_sources(msg["sources"])

    # Chat input
    if prompt := st.chat_input("Ask about your emails..."):
        # Display user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Get streaming response from API
        with st.chat_message("assistant"):
            response_text, sources = _stream_response(prompt)

        # Always record an assistant message to avoid dangling user turns
        # which would create consecutive user messages in the history.
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": response_text or "Sorry, I encountered an error processing your request.",
                "sources": sources,
            }
        )


def _stream_response(prompt: str) -> tuple[str, list[dict]]:
    """Send query to API and stream the response."""
    api_base = st.session_state.api_base
    sources: list[dict] = []

    payload = {
        "message": prompt,
        "session_id": st.session_state.session_id,
        "filters": st.session_state.get("filters") or None,
    }

    try:
        placeholder = st.empty()
        full_response = ""

        with httpx.Client(timeout=120.0) as client:
            with client.stream(
                "POST",
                f"{api_base}/api/chat/stream",
                json=payload,
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = json.loads(line[6:])
                    event_type = data.get("type")

                    if event_type == "token":
                        full_response += data["content"]
                        placeholder.markdown(full_response + " ▌")
                    elif event_type == "sources":
                        sources = data.get("sources", [])
                    elif event_type == "error":
                        st.error(f"Error: {data.get('message')}")
                        return "", []

        placeholder.markdown(full_response)

        if sources:
            _render_sources(sources)

        return full_response, sources

    except httpx.ConnectError:
        st.error(
            "Cannot connect to API server. Make sure it's running:\n"
            "```\nmake run-api\n```"
        )
        return "", []
    except Exception as e:
        st.error(f"Error: {e}")
        return "", []


def _render_sources(sources: list[dict]) -> None:
    """Render source citations as expandable cards."""
    if not sources:
        return

    with st.expander(f"Sources ({len(sources)} emails)", expanded=False):
        for i, src in enumerate(sources, 1):
            sender = src.get("sender_name") or src.get("sender", "Unknown")
            date = src.get("date", "")
            if "T" in date:
                date = date.split("T")[0]
            subject = src.get("subject", "(no subject)")
            direction = "You sent" if src.get("is_sent") else f"From: {sender}"

            st.markdown(
                f"**{i}.** {direction} | {date} | *{subject}*"
            )
            if src.get("snippet"):
                st.caption(src["snippet"][:150])
            if i < len(sources):
                st.divider()
