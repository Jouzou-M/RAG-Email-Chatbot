from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class EmailAttachment(BaseModel):
    filename: str
    mime_type: str
    size: int
    attachment_id: str


class EmailMessage(BaseModel):
    id: str
    thread_id: str
    subject: str = ""
    sender: str = ""
    sender_name: str = ""
    sender_domain: str = ""
    recipients_to: list[str] = Field(default_factory=list)
    recipients_cc: list[str] = Field(default_factory=list)
    date: datetime | None = None
    labels: list[str] = Field(default_factory=list)
    snippet: str = ""
    body_text: str = ""
    body_html: str = ""
    is_sent: bool = False
    has_attachments: bool = False
    attachments: list[EmailAttachment] = Field(default_factory=list)
    in_reply_to: str = ""
    references: list[str] = Field(default_factory=list)
    raw_headers: dict[str, str] = Field(default_factory=dict)


class EmailThread(BaseModel):
    thread_id: str
    subject: str = ""
    messages: list[EmailMessage] = Field(default_factory=list)
    participants: list[str] = Field(default_factory=list)
    date_start: datetime | None = None
    date_end: datetime | None = None
    message_count: int = 0


class SyncState(BaseModel):
    last_history_id: str | None = None
    last_sync_at: datetime | None = None
    total_messages_synced: int = 0
    email_address: str = ""
