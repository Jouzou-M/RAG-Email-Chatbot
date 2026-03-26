from __future__ import annotations

from email_rag.config import settings
from email_rag.embeddings.base import EmbeddingProvider


def get_embedding_provider() -> EmbeddingProvider:
    """Factory function returning the configured embedding provider."""
    if settings.embedding_provider == "openai":
        from email_rag.embeddings.openai import OpenAIEmbedding

        return OpenAIEmbedding()
    elif settings.embedding_provider == "sentence-transformer":
        from email_rag.embeddings.sentence_transformer import SentenceTransformerEmbedding

        return SentenceTransformerEmbedding()
    else:
        raise ValueError(f"Unknown embedding provider: {settings.embedding_provider}")
