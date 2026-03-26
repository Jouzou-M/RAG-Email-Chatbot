from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator

from email_rag.config import settings

logger = logging.getLogger(__name__)


class RAGChain:
    """Configurable LLM generation chain supporting OpenAI, Anthropic, and Ollama."""

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> None:
        self.provider = provider or settings.llm_provider
        self.model = model or settings.llm_model
        self.temperature = temperature if temperature is not None else settings.llm_temperature
        self.max_tokens = max_tokens if max_tokens is not None else settings.llm_max_tokens
        self._openai_client = None
        self._anthropic_client = None

    def _get_openai_client(self):
        if self._openai_client is None:
            from openai import AsyncOpenAI

            key = settings.openai_api_key or None
            self._openai_client = AsyncOpenAI(api_key=key)
        return self._openai_client

    def _get_anthropic_client(self):
        if self._anthropic_client is None:
            from anthropic import AsyncAnthropic

            key = settings.anthropic_api_key or None
            self._anthropic_client = AsyncAnthropic(api_key=key)
        return self._anthropic_client

    async def generate(
        self,
        messages: list[dict[str, str]],
    ) -> str:
        """Generate a complete response (non-streaming)."""
        chunks: list[str] = []
        async for chunk in self.stream(messages):
            chunks.append(chunk)
        return "".join(chunks)

    async def stream(
        self,
        messages: list[dict[str, str]],
    ) -> AsyncGenerator[str, None]:
        """Stream tokens from the configured LLM provider."""
        if self.provider == "openai":
            async for token in self._stream_openai(messages):
                yield token
        elif self.provider == "anthropic":
            async for token in self._stream_anthropic(messages):
                yield token
        elif self.provider == "ollama":
            async for token in self._stream_ollama(messages):
                yield token
        else:
            raise ValueError(f"Unknown LLM provider: {self.provider}")

    async def _stream_openai(
        self, messages: list[dict[str, str]]
    ) -> AsyncGenerator[str, None]:
        client = self._get_openai_client()
        stream = await client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore[arg-type]
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def _stream_anthropic(
        self, messages: list[dict[str, str]]
    ) -> AsyncGenerator[str, None]:
        client = self._get_anthropic_client()

        # Anthropic uses a separate system param
        system_msg = ""
        chat_messages: list[dict[str, str]] = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                chat_messages.append(msg)

        async with client.messages.stream(
            model=self.model,
            messages=chat_messages,  # type: ignore[arg-type]
            system=system_msg,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def _stream_ollama(
        self, messages: list[dict[str, str]]
    ) -> AsyncGenerator[str, None]:
        import httpx

        async with httpx.AsyncClient(base_url=settings.ollama_base_url) as client:
            async with client.stream(
                "POST",
                "/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": True,
                    "options": {
                        "temperature": self.temperature,
                        "num_predict": self.max_tokens,
                    },
                },
                timeout=120.0,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    content = data.get("message", {}).get("content", "")
                    if content:
                        yield content
