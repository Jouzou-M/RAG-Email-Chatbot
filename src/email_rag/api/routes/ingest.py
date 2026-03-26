from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException

from email_rag.api.deps import get_gmail_client, get_vector_store
from email_rag.api.schemas import SyncRequest, SyncStatusResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ingest", tags=["ingest"])

# In-memory sync lock. Only safe with a single uvicorn worker.
# Multi-worker deployments need a distributed lock (e.g., file lock or Redis).
_syncing = False


async def _run_sync(query: str, max_results: int | None, full_sync: bool) -> None:
    """Background sync task. Caller must set _syncing=True before scheduling."""
    global _syncing
    try:
        store = get_vector_store()

        # Create Gmail client in a thread to avoid blocking the event loop
        # during OAuth token loading / refresh
        client = await asyncio.to_thread(get_gmail_client)

        if full_sync:
            logger.info("Starting full reindex")
            store.clear()
            sync_state = None
        else:
            sync_state = store.get_sync_state()
            if sync_state.last_history_id:
                logger.info("Starting incremental sync from history %s", sync_state.last_history_id)
            else:
                logger.info("No prior sync state, performing full sync")

        # Gmail API calls are synchronous and blocking — run in thread.
        # Use a lambda with keyword args so parameter order can't silently break.
        messages, new_state = await asyncio.to_thread(
            lambda: client.sync_messages(
                sync_state=sync_state,
                query=query,
                max_results=max_results,
            )
        )

        if messages:
            chunks_added = await store.add_emails(messages)
            logger.info("Added %d chunks from %d messages", chunks_added, len(messages))

        store.set_sync_state(new_state)
        logger.info("Sync complete. Total messages: %d", new_state.total_messages_synced)

    except Exception:
        logger.exception("Sync failed")
    finally:
        _syncing = False


@router.post("/sync")
async def trigger_sync(
    request: SyncRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    global _syncing
    if _syncing:
        raise HTTPException(status_code=409, detail="Sync already in progress")

    # Set lock BEFORE scheduling to close the race window between
    # checking the flag and the background task actually starting.
    _syncing = True
    background_tasks.add_task(
        _run_sync,
        request.query,
        request.max_results,
        request.full_sync,
    )
    return {"status": "started", "full_sync": request.full_sync}


@router.get("/status", response_model=SyncStatusResponse)
async def sync_status():
    store = get_vector_store()
    stats = store.get_stats()
    return SyncStatusResponse(
        is_syncing=_syncing,
        last_sync_at=stats.get("last_sync_at"),
        total_messages_synced=stats.get("total_messages_synced", 0),
        total_chunks=stats.get("total_chunks", 0),
        email_address=stats.get("email_address", ""),
    )


@router.post("/reindex")
async def reindex(background_tasks: BackgroundTasks) -> dict[str, str]:
    global _syncing
    if _syncing:
        raise HTTPException(status_code=409, detail="Sync already in progress")

    _syncing = True
    background_tasks.add_task(_run_sync, "", None, True)
    return {"status": "reindex_started"}
