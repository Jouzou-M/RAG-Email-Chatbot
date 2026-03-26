from __future__ import annotations

import os
import uuid

import streamlit as st


def init_session_state() -> None:
    """Initialize Streamlit session state with defaults."""
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "api_base" not in st.session_state:
        # Configurable via env var for Docker (where localhost doesn't work between containers)
        st.session_state.api_base = os.environ.get("API_BASE_URL", "http://localhost:8000")

    if "filters" not in st.session_state:
        st.session_state.filters = {}
