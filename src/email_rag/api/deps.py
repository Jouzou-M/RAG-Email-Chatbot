from __future__ import annotations

from functools import lru_cache

from email_rag.gmail.client import GmailClient
from email_rag.rag.chain import RAGChain
from email_rag.rag.conversation import ConversationMemory
from email_rag.rag.retriever import EmailRetriever
from email_rag.vectorstore.store import EmailVectorStore


@lru_cache(maxsize=1)
def get_vector_store() -> EmailVectorStore:
    return EmailVectorStore()


@lru_cache(maxsize=1)
def get_rag_chain() -> RAGChain:
    return RAGChain()


@lru_cache(maxsize=1)
def get_conversation_memory() -> ConversationMemory:
    return ConversationMemory()


def get_retriever() -> EmailRetriever:
    return EmailRetriever(
        vector_store=get_vector_store(),
        chain=get_rag_chain(),
        memory=get_conversation_memory(),
    )


@lru_cache(maxsize=1)
def get_gmail_client() -> GmailClient:
    return GmailClient()
