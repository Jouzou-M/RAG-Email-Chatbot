from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import streamlit as st


def render_sidebar() -> None:
    """Render the sidebar with sync controls and filters."""
    api_base = st.session_state.api_base

    st.sidebar.title("Email RAG Chatbot")
    st.sidebar.divider()

    # --- Sync Section ---
    st.sidebar.subheader("Email Sync")

    try:
        resp = httpx.get(f"{api_base}/api/ingest/status", timeout=5.0)
        status = resp.json()
        if status.get("email_address"):
            st.sidebar.success(f"Connected: {status['email_address']}")
        st.sidebar.metric("Emails Indexed", status.get("total_messages_synced", 0))
        st.sidebar.metric("Total Chunks", status.get("total_chunks", 0))
        if status.get("last_sync_at"):
            st.sidebar.caption(f"Last sync: {status['last_sync_at'][:19]}")
        if status.get("is_syncing"):
            st.sidebar.warning("Sync in progress...")
    except Exception:
        st.sidebar.warning("API not connected")

    col1, col2 = st.sidebar.columns(2)
    _needs_rerun = False
    with col1:
        if st.button("Sync Now", use_container_width=True):
            try:
                httpx.post(f"{api_base}/api/ingest/sync", json={}, timeout=5.0)
                st.session_state["_flash"] = ("info", "Sync started!")
                _needs_rerun = True
            except Exception as e:
                st.sidebar.error(f"Sync failed: {e}")
    with col2:
        if st.button("Full Reindex", use_container_width=True):
            try:
                httpx.post(f"{api_base}/api/ingest/reindex", timeout=5.0)
                st.session_state["_flash"] = ("info", "Reindex started!")
                _needs_rerun = True
            except Exception as e:
                st.sidebar.error(f"Reindex failed: {e}")

    # Show flash messages that survive reruns, and rerun outside column context
    if "_flash" in st.session_state:
        level, msg = st.session_state.pop("_flash")
        getattr(st.sidebar, level)(msg)
    if _needs_rerun:
        st.rerun()

    st.sidebar.divider()

    # --- Filter Section ---
    st.sidebar.subheader("Search Filters")

    sender_filter = st.sidebar.text_input("Sender (email or domain)", value="")
    date_option = st.sidebar.selectbox(
        "Date range",
        ["Any time", "Today", "This week", "This month", "Last month", "Custom"],
    )

    conditions: list[dict] = []

    if sender_filter:
        if "@" in sender_filter:
            conditions.append({"sender": sender_filter})
        elif "." in sender_filter:
            # Looks like a domain (e.g., "example.com")
            conditions.append({"sender_domain": sender_filter})
        # else: name-only input — let semantic search handle it

    # Date filters for ALL options, not just Custom
    now = datetime.now(timezone.utc)
    if date_option == "Today":
        ts = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        conditions.append({"date_timestamp": {"$gte": ts}})
    elif date_option == "This week":
        start = now - timedelta(days=now.weekday())
        ts = start.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        conditions.append({"date_timestamp": {"$gte": ts}})
    elif date_option == "This month":
        ts = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp()
        conditions.append({"date_timestamp": {"$gte": ts}})
    elif date_option == "Last month":
        first_this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_m = (first_this - timedelta(days=1)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        conditions.append({"date_timestamp": {"$gte": last_m.timestamp()}})
        conditions.append({"date_timestamp": {"$lte": first_this.timestamp()}})
    elif date_option == "Custom":
        date_from = st.sidebar.date_input("From", value=None)
        date_to = st.sidebar.date_input("To", value=None)
        if date_from is not None:
            ts = datetime.combine(date_from, datetime.min.time(), tzinfo=timezone.utc).timestamp()
            conditions.append({"date_timestamp": {"$gte": ts}})
        if date_to is not None:
            ts = datetime.combine(date_to, datetime.max.time(), tzinfo=timezone.utc).timestamp()
            conditions.append({"date_timestamp": {"$lte": ts}})

    sent_filter = st.sidebar.radio("Direction", ["All", "Received", "Sent"], horizontal=True)
    if sent_filter == "Sent":
        conditions.append({"is_sent": True})
    elif sent_filter == "Received":
        conditions.append({"is_sent": False})

    # Combine conditions into a single ChromaDB where clause
    if not conditions:
        st.session_state.filters = {}
    elif len(conditions) == 1:
        st.session_state.filters = conditions[0]
    else:
        st.session_state.filters = {"$and": conditions}

    st.sidebar.divider()

    # --- Session Section ---
    st.sidebar.subheader("Session")
    st.sidebar.caption(f"ID: {st.session_state.session_id[:8]}...")
    if st.sidebar.button("New Chat", use_container_width=True):
        st.session_state.messages = []
        import uuid
        st.session_state.session_id = str(uuid.uuid4())
        st.rerun()
