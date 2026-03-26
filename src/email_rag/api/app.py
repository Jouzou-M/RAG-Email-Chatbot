from __future__ import annotations

import logging
import sys

import structlog
from fastapi import FastAPI

from email_rag import __version__
from email_rag.api.middleware import setup_middleware
from email_rag.api.routes import chat, health, ingest
from email_rag.config import settings


def _configure_logging() -> None:
    """Set up structured logging."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer() if sys.stderr.isatty() else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def create_app() -> FastAPI:
    """FastAPI application factory."""
    _configure_logging()

    app = FastAPI(
        title="Email RAG Chatbot",
        version=__version__,
        description="Production-grade RAG chatbot for Gmail emails",
    )

    setup_middleware(app)

    app.include_router(health.router)
    app.include_router(ingest.router)
    app.include_router(chat.router)

    return app
