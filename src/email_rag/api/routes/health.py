from __future__ import annotations

from fastapi import APIRouter

from email_rag import __version__
from email_rag.api.schemas import HealthResponse, ReadinessResponse
from email_rag.api.deps import get_vector_store

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok", version=__version__)


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness():
    vs_ok = False
    embed_ok = False
    llm_ok = False

    try:
        store = get_vector_store()
        _ = store.count
        vs_ok = True
    except Exception:
        pass

    try:
        from email_rag.embeddings import get_embedding_provider

        provider = get_embedding_provider()
        _ = provider.dimension
        embed_ok = True
    except Exception:
        pass

    try:
        from email_rag.rag.chain import RAGChain

        _ = RAGChain()
        llm_ok = True
    except Exception:
        pass

    status = "ok" if (vs_ok and embed_ok and llm_ok) else "degraded"
    return ReadinessResponse(
        status=status,
        vector_store=vs_ok,
        embedding_provider=embed_ok,
        llm_provider=llm_ok,
    )
