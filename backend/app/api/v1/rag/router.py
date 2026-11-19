"""
RAG Ingest API Router.

Provides REST endpoints for RAG index health monitoring, triggering
ingestion, and polling job status.

All endpoints are mounted under ``/api/v1/rag/*`` via the parent ``app.include_router()`` in main.py.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.domain.providers.embeddings import EmbeddingService, resolve_embedding_service

from app.core.system_manager import SystemManagerConfig
from app.domain.rag.schemas import (
    IngestRequest,
    IngestResponse,
    IngestJobStatusResponse,
    RagStatusResponse,
)
from app.domain.rag.service import RagIngestService
from fastapi import Depends

logger = logging.getLogger(__name__)

rag_router = APIRouter(prefix="", tags=["rag"])

# Active background task reference (singleton per process).
# We store the asyncio.Task so we can inspect it if needed.
_active_ingest_task: asyncio.Task | None = None


async def _resolve_embedding_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> "EmbeddingService":
    """**THE embedding service this install uses** — the `embeddings` capability, resolved.

    This module used to answer with a literal and CALL it a resolution:
    ``_get_ollama_base(config)`` took an argument, ignored it, and returned
    ``http://localhost:11434`` while its docstring said *"Resolve the Ollama base URL from config or
    default"*, and the model and the dims came from ``SystemManagerConfig``'s own code defaults —
    three literals, in two homes. That is the class of lie the service-literals arc exists to remove
    (`wiki/issues/resolved/embedded-service-literals/local-embedding-server.md` RULED option C, staged; its model half is
    `wiki/issues/resolved/embedded-service-literals/embedding-model-and-dims.md`).

    The answer carries the ADDRESS (from the capability's provider row), the MODEL (from the
    capability) and the DIMS (derived from the model). An install that configured none of it gets an
    unresolved service, and every route below REPORTS that instead of dialling a guess.
    """
    return await resolve_embedding_service(db)


# ─── Dependency ───────────────────────────────────────────────────────────────


async def _load_config() -> SystemManagerConfig:
    """Return the default RAG configuration.

    The legacy system_manager_config table is retired; the RAG service uses code-level defaults for
    what is genuinely the index's own (where it lives, the embedding batch size). The embedding
    ADDRESS, MODEL and DIMS are NOT here — they are the `embeddings` capability's answer, resolved
    alongside this by `_resolve_embedding_service`.
    """
    return SystemManagerConfig.defaults()


# ─── Endpoints ────────────────────────────────────────────────────────────────


class RagSearchResponse(BaseModel):
    query: str
    hits: list[dict]
    count: int


class RagSearchRequest(BaseModel):
    query: str
    top_k: int = 5


@rag_router.post(
    "/search",
    response_model=RagSearchResponse,
    summary="Search the RAG index (the search-knowledge capability, HTTP)",
)
async def search_rag(
    request: RagSearchRequest,
    embedding: Annotated[EmbeddingService, Depends(_resolve_embedding_service)],
):
    """Search the RAG knowledge index.

    THE EXPERTISE WIRING (2026-08-22): the search-knowledge handler was
    registered in the internal tool registry (unreachable by Exa's Hermes
    session). This exposes the same capability over HTTP: embed the query,
    ANN-search the doc_chunks index, return the verified hits.

    The search embeds with the install's `embeddings` capability (resolved above) — the same model
    the index was built with, so a query and its chunks are the same width. An install that has
    configured no model is REFUSED rather than searched with a default.
    """
    q = request.query.strip()
    if not q:
        return RagSearchResponse(query=q, hits=[], count=0)
    if not embedding.resolved:
        raise HTTPException(status_code=503, detail=embedding.report())
    try:
        from app.domain.tools.builtin.doc_vector_store import DocVectorStore
        from app.core.config import Paths as _Paths
        store = DocVectorStore.get_instance(
            db_path=str(_Paths.rag_index_path), embedding=embedding
        )
        emb = store.embed_query(q)
        if not emb:
            raise HTTPException(status_code=503, detail="Embedding failed (is the embedding server up?)")
        hits = store.search(emb, top_k=request.top_k, min_score=0.25)
        return RagSearchResponse(
            query=q,
            hits=[
                {
                    "source": h.get("source_path"),
                    "heading": h.get("heading"),
                    "score": round(float(h.get("similarity_score", 0)), 3),
                    "snippet": (h.get("chunk_text") or "")[:240],
                }
                for h in hits
            ],
            count=len(hits),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("rag search failed")
        raise HTTPException(status_code=500, detail=f"Knowledge search failed: {e}")


def _running_embedding_service() -> "EmbeddingService | None":
    """What the RAG store IN THIS PROCESS was built with — ``None`` when none has been built yet.

    THE SINGLETON TRAP'S READ SIDE (the embedding-configuration ruling, option C, 2026-10-12): the
    store captures the resolved service at first construction and ignores every later one, so a
    surface that wants to say what is ACTUALLY embedding asks the store — the capability ladder
    answers what the NEXT process will use. The import is lazy for the same reason this router's other
    store imports are: `tools/builtin/__init__` reaches back into the app.
    """
    from app.domain.tools.builtin.doc_vector_store import DocVectorStore  # noqa: PLC0415

    return DocVectorStore.current_service()


@rag_router.get(
    "/status",
    response_model=RagStatusResponse,
    summary="Get RAG index health stats",
)
async def get_rag_status(
    config: Annotated[SystemManagerConfig, Depends(_load_config)],
    embedding: Annotated[EmbeddingService, Depends(_resolve_embedding_service)],
) -> RagStatusResponse:
    """Return health statistics for the vector index.

    Queries the ``doc_chunks`` table for document count, chunk count, last
    indexed timestamp, and database file size.  Also returns the current
    embedding/indexing configuration — the address, the model and (through the
    model) the width the index is built at, as the `embeddings` capability answers them.

    **The configured answer and the RUNNING one are both reported, and their disagreement is
    named.** The stores are singletons that captured the service they were built with, so
    `running_model` is what is embedding right now and `note` says what to do when a change has not
    reached the process (a restart) or cannot (`the index is 768 wide and … — re-run the ingest`).

    If the database file does not exist or is empty, returns zero counts
    with ``last_indexed: null`` (not an error).
    """
    return RagIngestService.get_index_health(
        config, embedding, running=_running_embedding_service()
    )


@rag_router.post(
    "/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger RAG documentation ingestion",
    responses={
        409: {"description": "An ingest job is already running"},
        503: {"description": "Ollama / vector store unavailable"},
    },
)
async def trigger_ingest(
    request: IngestRequest,
    config: Annotated[SystemManagerConfig, Depends(_load_config)],
    embedding: Annotated[EmbeddingService, Depends(_resolve_embedding_service)],
) -> IngestResponse:
    """Trigger a RAG documentation ingestion job.

    Runs ingestion in the background.  Returns immediately with ``202 Accepted``
    and a ``job_id`` for polling progress via ``GET /rag/ingest/status``.

    **Modes:**
    - ``incremental`` — only re-index files whose modification time is newer
      than the last index.
    - ``full`` — re-process all discovered files.
    - ``force-reingest`` — bypass incremental checks and re-index everything.

    **Errors:**
    - ``409 Conflict`` — if an ingest job is already running.
    - ``503 Service Unavailable`` — if Ollama is unreachable (detected during
      the initial embedding call; the job will eventually fail).
    """
    global _active_ingest_task  # noqa: PLW0603

    # ── The embedding guard ──────────────────────────────────────────────
    # An ingest with no address, model or width would import a whole corpus into nothing, so it is
    # refused UP FRONT and the reason is named (the documented 503): the `embeddings` capability is
    # the decision, and an install that has made none is told exactly what is missing.
    if not embedding.resolved:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=embedding.report(),
        )

    # ── Conflict guard ───────────────────────────────────────────────────
    if RagIngestService.is_running():
        status_info = RagIngestService.get_status()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "An ingest job is already running.",
                "job_id": status_info.job_id if status_info else None,
            },
        )

    # ── Create job record ────────────────────────────────────────────────
    job_id = f"rag-ingest-{int(datetime.now(timezone.utc).timestamp())}"
    started_at = datetime.now(timezone.utc)

    # ── Launch background task ───────────────────────────────────────────
    service = RagIngestService()
    _active_ingest_task = asyncio.create_task(
        service.run(
            mode=request.mode,
            index_type=request.index_type,
            config=config,
            embedding=embedding,
        )
    )

    # Add a done callback to log completion
    def _on_done(t: asyncio.Task) -> None:
        if t.cancelled():
            logger.warning("Ingest job %s was cancelled", job_id)
        elif t.exception():
            logger.error("Ingest job %s failed: %s", job_id, t.exception())
        else:
            logger.info("Ingest job %s completed successfully", job_id)

    _active_ingest_task.add_done_callback(_on_done)

    logger.info("Ingest job %s triggered (mode=%s, index_type=%s)", job_id, request.mode, request.index_type)

    return IngestResponse(
        job_id=job_id,
        status="running",
        mode=request.mode,
        started_at=started_at,
    )


@rag_router.get(
    "/ingest/status",
    response_model=IngestJobStatusResponse,
    summary="Poll the current ingest job status",
    responses={
        404: {"description": "No ingest job has been started yet"},
    },
)
async def get_ingest_job_status() -> IngestJobStatusResponse:
    """Poll the current ingest job's progress.

    Returns the job status from the on-disk status file.  Poll every 2-3
    seconds from the frontend while the status is ``running``.

    **States:**
    - ``running`` — job is in progress; ``progress`` field provides details.
    - ``completed`` — job finished successfully; ``result`` field provides
      final statistics.
    - ``failed`` — job terminated with an error; ``error`` field provides
      the error message.

    **Errors:**
    - ``404 Not Found`` — if no ingest job has ever been triggered.
    """
    status_info = RagIngestService.get_status()
    if status_info is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No ingest job has been started yet.",
        )

    return IngestJobStatusResponse(
        job_id=status_info.job_id,
        status=status_info.status,
        mode=status_info.mode,
        started_at=status_info.started_at,
        completed_at=status_info.completed_at,
        error=status_info.error,
        progress=status_info.progress,
        result=status_info.result,
    )
