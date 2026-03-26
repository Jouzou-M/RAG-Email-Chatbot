from __future__ import annotations

import logging

from openai import AsyncOpenAI

from email_rag.config import settings
from email_rag.embeddings.base import EmbeddingProvider

logger = logging.getLogger(__name__)

BATCH_SIZE = 2048


class OpenAIEmbedding(EmbeddingProvider):
    """OpenAI embedding provider using text-embedding-3-small/large."""

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        dimensions: int | None = None,
    ) -> None:
        self._model = model or settings.embedding_model
        self._dimensions = dimensions or settings.embedding_dimension
        # Pass None instead of empty string to allow env var fallback
        key = api_key or settings.openai_api_key or None
        self._client = AsyncOpenAI(api_key=key)

    @property
    def dimension(self) -> int:
        return self._dimensions

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed documents in batches."""
        if not texts:
            return []

        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i : i + BATCH_SIZE]
            # Replace empty strings to avoid API errors
            batch = [t if t.strip() else " " for t in batch]

            response = await self._client.embeddings.create(
                model=self._model,
                input=batch,
                dimensions=self._dimensions,
            )
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)

            if i + BATCH_SIZE < len(texts):
                logger.info(
                    "Embedded %d / %d documents", i + BATCH_SIZE, len(texts)
                )

        return all_embeddings

    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query."""
        result = await self.embed_documents([text])
        return result[0]
