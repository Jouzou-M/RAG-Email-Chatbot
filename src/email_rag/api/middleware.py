from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from email_rag.config import settings

logger = logging.getLogger(__name__)


def setup_middleware(app: FastAPI) -> None:
    """Configure all middleware for the FastAPI application."""

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_logging(request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        start = time.perf_counter()

        # Attach request ID
        request.state.request_id = request_id

        try:
            response: Response = await call_next(request)
        except Exception as e:
            duration = time.perf_counter() - start
            logger.error(
                "[%s] %s %s — 500 (%.3fs) — %s",
                request_id,
                request.method,
                request.url.path,
                duration,
                str(e),
            )
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error", "request_id": request_id},
            )

        duration = time.perf_counter() - start
        logger.info(
            "[%s] %s %s — %d (%.3fs)",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration,
        )
        response.headers["X-Request-ID"] = request_id
        return response
