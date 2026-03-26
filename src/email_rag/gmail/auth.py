from __future__ import annotations

import logging
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build, Resource

from email_rag.config import settings

logger = logging.getLogger(__name__)

SCOPES = settings.gmail_scopes


def get_credentials(
    credentials_path: Path | None = None,
    token_path: Path | None = None,
) -> Credentials:
    """Load or create OAuth2 credentials for Gmail API access."""
    creds_path = credentials_path or settings.gmail_credentials_path
    tok_path = token_path or settings.gmail_token_path

    creds: Credentials | None = None

    if tok_path.exists():
        creds = Credentials.from_authorized_user_file(str(tok_path), SCOPES)
        logger.info("Loaded existing credentials from %s", tok_path)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        logger.info("Refreshing expired credentials")
        creds.refresh(Request())
    else:
        if not creds_path.exists():
            raise FileNotFoundError(
                f"OAuth credentials file not found at {creds_path}. "
                "Download it from Google Cloud Console."
            )
        logger.info("Starting OAuth2 consent flow")
        flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
        creds = flow.run_local_server(port=0)

    # Persist the token
    tok_path.parent.mkdir(parents=True, exist_ok=True)
    tok_path.write_text(creds.to_json())
    logger.info("Saved credentials to %s", tok_path)

    return creds


def get_gmail_service(
    credentials_path: Path | None = None,
    token_path: Path | None = None,
) -> Resource:
    """Return an authorized Gmail API service instance."""
    creds = get_credentials(credentials_path, token_path)
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    return service
