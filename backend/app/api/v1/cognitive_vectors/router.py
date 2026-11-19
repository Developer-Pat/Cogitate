"""REST endpoints for vector store operations.

Provides search, index, and clear operations for per-agent vector memory.
"""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.domain.providers.embeddings import EmbeddingService, resolve_embedding_service
from app.services.cognitive_pipeline.vector_store import TurnVectorStore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cognitive/vectors", tags=["cognitive-vector"])


async def _embedding_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> EmbeddingService:
    """The install's embedding service, resolved from the `embeddings` capability.

    These endpoints used to build ``TurnVectorStore(agent_folder=…)`` and let the store's own
    ``DEFAULT_OLLAMA_BASE``/``DEFAULT_EMBEDDING_MODEL``/``DEFAULT_EMBEDDING_DIMS`` decide what it
    embedded with — three copies of a decision that belongs to the capability. The store is now built
    from this ONE answer, and an install that has configured none is refused.
    """
    return await resolve_embedding_service(db)


def _store(agent_folder: str, embedding: EmbeddingService) -> TurnVectorStore:
    """The per-agent turn store — or a refusal naming what the install has not configured."""
    if not embedding.resolved:
        raise HTTPException(503, embedding.report())
    return TurnVectorStore(agent_folder=agent_folder, embedding=embedding)


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


class IndexRequest(BaseModel):
    session_id: str
    role: str
    content: str
    turn_index: int = 0


@router.post("/{agent_folder}/search")
async def search_vectors(
    agent_folder: str,
    req: SearchRequest,
    embedding: Annotated[EmbeddingService, Depends(_embedding_service)],
):
    """Search for semantically similar turns."""
    store = _store(agent_folder, embedding)
    try:
        results = store.search(req.query, top_k=req.top_k)
        return {"results": results, "count": len(results)}
    finally:
        store.close()


@router.post("/{agent_folder}/index")
async def index_turn(
    agent_folder: str,
    req: IndexRequest,
    embedding: Annotated[EmbeddingService, Depends(_embedding_service)],
):
    """Index a conversation turn."""
    store = _store(agent_folder, embedding)
    try:
        ok = store.index_turn(
            session_id=req.session_id,
            role=req.role,
            content=req.content,
            turn_index=req.turn_index,
        )
        if ok:
            return {"message": "Turn indexed"}
        raise HTTPException(500, "Failed to index turn (embedding may have failed)")
    finally:
        store.close()


@router.delete("/{agent_folder}/session/{session_id}")
async def remove_session(
    agent_folder: str,
    session_id: str,
    embedding: Annotated[EmbeddingService, Depends(_embedding_service)],
):
    """Remove all indexed turns for a session."""
    store = _store(agent_folder, embedding)
    try:
        count = store.remove_session(session_id)
        return {"removed": count}
    finally:
        store.close()


@router.delete("/{agent_folder}/all")
async def clear_all(
    agent_folder: str,
    embedding: Annotated[EmbeddingService, Depends(_embedding_service)],
):
    """Remove ALL indexed turns for an agent."""
    store = _store(agent_folder, embedding)
    try:
        count = store.clear_all()
        return {"removed": count}
    finally:
        store.close()
