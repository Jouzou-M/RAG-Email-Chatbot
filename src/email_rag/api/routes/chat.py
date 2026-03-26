from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from email_rag.api.deps import get_retriever
from email_rag.api.schemas import ChatRequest, ChatResponse, SourceReference

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Non-streaming chat endpoint."""
    retriever = get_retriever()

    try:
        answer, sources = await retriever.query(
            question=request.message,
            session_id=request.session_id,
            extra_filters=request.filters,
        )
    except Exception:
        logger.exception("Chat query failed")
        raise HTTPException(status_code=500, detail="Failed to process query")

    source_refs = [
        SourceReference(
            sender=s.get("sender", ""),
            sender_name=s.get("sender_name", ""),
            date=s.get("date", ""),
            subject=s.get("subject", ""),
            snippet=s.get("snippet", ""),
            is_sent=s.get("is_sent", False),
        )
        for s in sources
    ]

    return ChatResponse(
        answer=answer,
        session_id=request.session_id,
        sources=source_refs,
    )


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """Streaming chat endpoint using Server-Sent Events."""
    retriever = get_retriever()

    async def event_generator():
        try:
            async for token, sources in retriever.query_stream(
                question=request.message,
                session_id=request.session_id,
                extra_filters=request.filters,
            ):
                if token is not None:
                    yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                elif sources is not None:
                    source_refs = [
                        {
                            "sender": s.get("sender", ""),
                            "sender_name": s.get("sender_name", ""),
                            "date": s.get("date", ""),
                            "subject": s.get("subject", ""),
                            "snippet": s.get("snippet", ""),
                            "is_sent": s.get("is_sent", False),
                        }
                        for s in sources
                    ]
                    yield f"data: {json.dumps({'type': 'sources', 'sources': source_refs})}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception:
            logger.exception("Streaming chat failed")
            yield f"data: {json.dumps({'type': 'error', 'message': 'An internal error occurred.'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/history/{session_id}")
async def get_history(session_id: str):
    """Get conversation history for a session."""
    retriever = get_retriever()
    turns = retriever.memory.get_turns(session_id)
    return {
        "session_id": session_id,
        "turns": [
            {
                "user": t.user_query,
                "assistant": t.assistant_response,
                "sources": t.sources,
            }
            for t in turns
        ],
    }


@router.delete("/history/{session_id}")
async def clear_history(session_id: str):
    """Clear conversation history for a session."""
    retriever = get_retriever()
    retriever.memory.clear_session(session_id)
    return {"status": "cleared", "session_id": session_id}
