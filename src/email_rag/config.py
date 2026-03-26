from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Gmail
    gmail_credentials_path: Path = Path("credentials.json")
    gmail_token_path: Path = Path("data/token.json")
    gmail_max_results: int = 500
    gmail_scopes: list[str] = Field(
        default=["https://www.googleapis.com/auth/gmail.readonly"]
    )

    # Embeddings
    embedding_provider: Literal["openai", "sentence-transformer"] = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536
    openai_api_key: str = ""

    # LLM
    llm_provider: Literal["openai", "anthropic", "ollama"] = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 2048
    anthropic_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"

    # Vector Store
    chroma_persist_dir: Path = Path("data/chroma")
    chroma_collection_name: str = "emails"

    # RAG
    retrieval_top_k: int = 10
    chunk_size: int = 512
    chunk_overlap: int = 64

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = Field(default=["http://localhost:8501"])

    # Logging
    log_level: str = "INFO"


settings = Settings()
