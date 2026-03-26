from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    session_id: str = Field(default="default", max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    filters: dict | None = None


class SourceReference(BaseModel):
    sender: str = ""
    sender_name: str = ""
    date: str = ""
    subject: str = ""
    snippet: str = ""
    is_sent: bool = False


class ChatResponse(BaseModel):
    answer: str
    session_id: str
    sources: list[SourceReference] = Field(default_factory=list)


class SyncRequest(BaseModel):
    query: str = ""
    max_results: int | None = None
    full_sync: bool = False


class SyncStatusResponse(BaseModel):
    is_syncing: bool = False
    last_sync_at: str | None = None
    total_messages_synced: int = 0
    total_chunks: int = 0
    email_address: str = ""


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"


class ReadinessResponse(BaseModel):
    status: str = "ok"
    vector_store: bool = False
    embedding_provider: bool = False
    llm_provider: bool = False
