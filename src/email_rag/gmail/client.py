from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone
from email.utils import parseaddr, parsedate_to_datetime
from typing import Any

from googleapiclient.discovery import Resource

from email_rag.config import settings
from email_rag.gmail.auth import get_gmail_service
from email_rag.gmail.models import (
    EmailAttachment,
    EmailMessage,
    EmailThread,
    SyncState,
)

logger = logging.getLogger(__name__)

_DATETIME_MIN_UTC = datetime.min.replace(tzinfo=timezone.utc)


class GmailClient:
    """High-level client for Gmail API operations."""

    def __init__(self, service: Resource | None = None) -> None:
        self._service = service or get_gmail_service()
        self._user_id = "me"

    @property
    def service(self) -> Resource:
        return self._service

    def get_profile(self) -> dict[str, Any]:
        """Get the authenticated user's email profile."""
        return self._service.users().getProfile(userId=self._user_id).execute()

    def list_message_ids(
        self,
        query: str = "",
        max_results: int | None = None,
        label_ids: list[str] | None = None,
    ) -> list[dict[str, str]]:
        """List message IDs matching a query. Returns list of {id, threadId}."""
        max_results = max_results or settings.gmail_max_results
        messages: list[dict[str, str]] = []
        page_token: str | None = None

        while len(messages) < max_results:
            batch_size = min(max_results - len(messages), 500)
            kwargs: dict[str, Any] = {
                "userId": self._user_id,
                "maxResults": batch_size,
            }
            if query:
                kwargs["q"] = query
            if label_ids:
                kwargs["labelIds"] = label_ids
            if page_token:
                kwargs["pageToken"] = page_token

            response = self._service.users().messages().list(**kwargs).execute()
            batch = response.get("messages", [])
            messages.extend(batch)

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        logger.info("Listed %d message IDs", len(messages))
        return messages[:max_results]

    def get_message(self, message_id: str) -> EmailMessage:
        """Fetch and parse a single email message."""
        raw = (
            self._service.users()
            .messages()
            .get(userId=self._user_id, id=message_id, format="full")
            .execute()
        )
        return self._parse_message(raw)

    def get_thread(self, thread_id: str) -> EmailThread:
        """Fetch and parse an entire email thread."""
        raw = (
            self._service.users()
            .threads()
            .get(userId=self._user_id, id=thread_id, format="full")
            .execute()
        )

        messages = [self._parse_message(m) for m in raw.get("messages", [])]
        messages.sort(key=lambda m: m.date or _DATETIME_MIN_UTC)

        participants = list(
            {m.sender for m in messages}
            | {r for m in messages for r in m.recipients_to}
        )

        return EmailThread(
            thread_id=thread_id,
            subject=messages[0].subject if messages else "",
            messages=messages,
            participants=participants,
            date_start=messages[0].date if messages else None,
            date_end=messages[-1].date if messages else None,
            message_count=len(messages),
        )

    def sync_messages(
        self,
        sync_state: SyncState | None = None,
        query: str = "",
        max_results: int | None = None,
    ) -> tuple[list[EmailMessage], SyncState]:
        """
        Sync emails. Uses History API for incremental sync if sync_state
        has a history_id, otherwise does a full sync.
        """
        profile = self.get_profile()
        current_history_id = profile.get("historyId", "")
        email_address = profile.get("emailAddress", "")

        do_full_sync = not (sync_state and sync_state.last_history_id)

        if not do_full_sync:
            messages = self._incremental_sync(sync_state.last_history_id)  # type: ignore[union-attr]
            if messages is None:
                # History expired — _incremental_sync signals fallback
                logger.info("History expired, falling back to full sync")
                do_full_sync = True
            else:
                total = (sync_state.total_messages_synced or 0) + len(messages)  # type: ignore[union-attr]

        if do_full_sync:
            logger.info("Performing full sync")
            message_ids = self.list_message_ids(query=query, max_results=max_results)
            messages = []
            for i, msg_ref in enumerate(message_ids):
                msg = self.get_message(msg_ref["id"])
                messages.append(msg)
                if (i + 1) % 50 == 0:
                    logger.info("Fetched %d / %d messages", i + 1, len(message_ids))
            total = len(messages)

        new_state = SyncState(
            last_history_id=current_history_id,
            last_sync_at=datetime.now(timezone.utc),
            total_messages_synced=total,
            email_address=email_address,
        )
        logger.info(
            "Sync complete: %d new messages, total %d", len(messages), total
        )
        return messages, new_state

    def _incremental_sync(self, history_id: str) -> list[EmailMessage] | None:
        """
        Fetch messages added since the given history ID.
        Returns None if the history ID has expired (caller should do full sync).
        """
        messages: list[EmailMessage] = []
        page_token: str | None = None
        seen_ids: set[str] = set()

        try:
            while True:
                kwargs: dict[str, Any] = {
                    "userId": self._user_id,
                    "startHistoryId": history_id,
                    "historyTypes": ["messageAdded"],
                }
                if page_token:
                    kwargs["pageToken"] = page_token

                response = (
                    self._service.users().history().list(**kwargs).execute()
                )

                for record in response.get("history", []):
                    for added in record.get("messagesAdded", []):
                        msg_id = added["message"]["id"]
                        if msg_id not in seen_ids:
                            seen_ids.add(msg_id)
                            try:
                                messages.append(self.get_message(msg_id))
                            except Exception:
                                logger.warning(
                                    "Failed to fetch message %s, skipping", msg_id
                                )

                page_token = response.get("nextPageToken")
                if not page_token:
                    break

        except Exception as e:
            if "404" in str(e) or "historyId" in str(e).lower():
                logger.warning("History ID %s expired", history_id)
                return None
            raise

        logger.info("Incremental sync found %d new messages", len(messages))
        return messages

    def _parse_message(self, raw: dict[str, Any]) -> EmailMessage:
        """Parse a raw Gmail API message response into an EmailMessage."""
        headers = {
            h["name"].lower(): h["value"]
            for h in raw.get("payload", {}).get("headers", [])
        }

        sender_full = headers.get("from", "")
        sender_name, sender_email = parseaddr(sender_full)
        sender_domain = sender_email.split("@")[1] if "@" in sender_email else ""

        date = None
        if date_str := headers.get("date"):
            try:
                date = parsedate_to_datetime(date_str)
                if date.tzinfo is None:
                    date = date.replace(tzinfo=timezone.utc)
            except Exception:
                pass

        recipients_to = self._parse_address_list(headers.get("to", ""))
        recipients_cc = self._parse_address_list(headers.get("cc", ""))

        body_text, body_html = self._extract_body(raw.get("payload", {}))

        attachments = self._extract_attachments(raw.get("payload", {}))

        labels = raw.get("labelIds", [])
        is_sent = "SENT" in labels

        in_reply_to = headers.get("in-reply-to", "")
        references_str = headers.get("references", "")
        references = references_str.split() if references_str else []

        return EmailMessage(
            id=raw["id"],
            thread_id=raw.get("threadId", ""),
            subject=headers.get("subject", "(no subject)"),
            sender=sender_email,
            sender_name=sender_name,
            sender_domain=sender_domain,
            recipients_to=recipients_to,
            recipients_cc=recipients_cc,
            date=date,
            labels=labels,
            snippet=raw.get("snippet", ""),
            body_text=body_text,
            body_html=body_html,
            is_sent=is_sent,
            has_attachments=len(attachments) > 0,
            attachments=attachments,
            in_reply_to=in_reply_to,
            references=references,
            raw_headers=headers,
        )

    def _extract_body(self, payload: dict[str, Any]) -> tuple[str, str]:
        """Recursively extract text and HTML body from MIME payload."""
        text_parts: list[str] = []
        html_parts: list[str] = []

        self._walk_parts(payload, text_parts, html_parts)

        return "\n".join(text_parts), "\n".join(html_parts)

    def _walk_parts(
        self,
        part: dict[str, Any],
        text_parts: list[str],
        html_parts: list[str],
    ) -> None:
        """Recursively walk MIME parts to extract body content."""
        mime_type = part.get("mimeType", "")

        if mime_type.startswith("multipart/"):
            for sub_part in part.get("parts", []):
                self._walk_parts(sub_part, text_parts, html_parts)
        elif mime_type == "text/plain":
            data = part.get("body", {}).get("data", "")
            if data:
                text_parts.append(
                    base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                )
        elif mime_type == "text/html":
            data = part.get("body", {}).get("data", "")
            if data:
                html_parts.append(
                    base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                )

    def _extract_attachments(
        self, payload: dict[str, Any]
    ) -> list[EmailAttachment]:
        """Extract attachment metadata from MIME payload."""
        attachments: list[EmailAttachment] = []
        self._walk_attachments(payload, attachments)
        return attachments

    def _walk_attachments(
        self, part: dict[str, Any], attachments: list[EmailAttachment]
    ) -> None:
        """Recursively find attachments in MIME parts."""
        filename = part.get("filename", "")
        body = part.get("body", {})

        if filename and body.get("attachmentId"):
            attachments.append(
                EmailAttachment(
                    filename=filename,
                    mime_type=part.get("mimeType", "application/octet-stream"),
                    size=body.get("size", 0),
                    attachment_id=body["attachmentId"],
                )
            )

        for sub_part in part.get("parts", []):
            self._walk_attachments(sub_part, attachments)

    @staticmethod
    def _parse_address_list(header_value: str) -> list[str]:
        """Parse a comma-separated list of email addresses."""
        if not header_value:
            return []
        addresses: list[str] = []
        for part in header_value.split(","):
            _, email = parseaddr(part.strip())
            if email:
                addresses.append(email)
        return addresses
