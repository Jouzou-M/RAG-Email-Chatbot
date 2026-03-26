"""Email RAG Chatbot — Streamlit UI."""

import streamlit as st

st.set_page_config(
    page_title="Email RAG Chatbot",
    page_icon="📧",
    layout="wide",
    initial_sidebar_state="expanded",
)

from email_rag.ui.state import init_session_state
from email_rag.ui.components.sidebar import render_sidebar
from email_rag.ui.components.chat import render_chat

init_session_state()
render_sidebar()
render_chat()
