from __future__ import annotations

import asyncio
import logging

from email_rag.embeddings.base import EmbeddingProvider

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "all-MiniLM-L6-v2"
DEFAULT_DIMENSION = 384


class SentenceTransformerEmbedding(EmbeddingProvider):
    """Local embedding provider using sentence-transformers."""

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        self._model_name = model_name
        self._model = None
        self._dim = DEFAULT_DIMENSION

    def _load_model(self):  # type: ignore[no-untyped-def]
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading sentence-transformers model: %s", self._model_name)
            self._model = SentenceTransformer(self._model_name)
            self._dim = self._model.get_sentence_embedding_dimension()
        return self._model

    @property
    def dimension(self) -> int:
        return self._dim

    def _encode_sync(self, texts: list[str]) -> list[list[float]]:
        """Synchronous encoding — called from a thread to avoid blocking the event loop."""
        model = self._load_model()
        embeddings = model.encode(texts, show_progress_bar=len(texts) > 100)
        return [e.tolist() for e in embeddings]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed documents using local model. Runs in a thread to avoid blocking."""
        if not texts:
            return []
        return await asyncio.to_thread(self._encode_sync, texts)

    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query."""
        result = await self.embed_documents([text])
        return result[0]
