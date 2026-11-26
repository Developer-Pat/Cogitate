"""
RAG Ingest API Router.

Provides REST endpoints for RAG index health monitoring, triggering
ingestion, and polling job status.

All endpoints are mounted under ``/api/v1/rag/*`` via the parent ``app.include_router()`` in main.py.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import BASE_DIR, Paths
from app.core.database import get_db_session
from app.domain.providers.embeddings import EmbeddingService, resolve_embedding_service

from app.core.system_manager import SystemManagerConfig
from app.domain.rag.schemas import (
    IngestJobStatusResponse,
    IngestProgress,
    IngestRequest,
    IngestResponse,
    IngestStatusFile,
    RagStatusResponse,
)
from app.domain.rag.service import (
    INGESTION_DIRS,
    RagIngestService,
    estimate_ingest,
    _job_is_live,
    _pid_is_alive,
    _read_status_file,
    _write_status_file,
)
from fastapi import Depends

logger = logging.getLogger(__name__)


def _settle_cancelled(record: IngestStatusFile) -> None:
    """Mark a job cancelled whose owner never wrote its own last word.

    The child handles SIGTERM and says so itself; this is the backstop for a job whose process simply
    stopped existing (a kill -9, a crash, a box that went down). It never touches a record that is no
    longer running, and never a newer job's.
    """
    current = _read_status_file()
    if current is None or current.job_id != record.job_id or current.status != "running":
        return
    current.status = "cancelled"
    current.completed_at = datetime.now(timezone.utc)
    current.error = "cancelled: the process stopped without writing its result"
    current.progress = None
    _write_status_file(current)

rag_router = APIRouter(prefix="", tags=["rag"])

# THE CHILDREN THIS PROCESS SPAWNED. Holding the Popen is not bookkeeping — it is the only way to
# REAP a finished child, and an unreaped child stays a zombie whose pid still answers `os.kill(pid, 0)`.
# `_reap()` is called from the two endpoints that read the record, so a finished run becomes a visible
# exit code instead of a process that looks alive for ever.
_ingest_children: dict[str, subprocess.Popen] = {}


def _reap(job_id: str | None = None) -> None:
    """Collect exit status for finished children (all of them when no job is named)."""
    for key in list(_ingest_children):
        if job_id is not None and key != job_id:
            continue
        child = _ingest_children[key]
        if child.poll() is not None:
            logger.info("ingest child %s exited with %s", key, child.returncode)
            _ingest_children.pop(key, None)


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

    # ── The roots this run may name ──────────────────────────────────────
    if request.dirs is not None:
        unknown = [root for root in request.dirs if root not in INGESTION_DIRS]
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"unknown ingestion root(s): {', '.join(unknown)} — "
                    f"known: {', '.join(INGESTION_DIRS)}"
                ),
            )

    # ── Conflict guard ───────────────────────────────────────────────────
    # `is_running()` is liveness now (pid + heartbeat), so a record left behind by a killed job no
    # longer refuses every future run — which is exactly what it did, twice, on the test box.
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
    dirs = list(request.dirs) if request.dirs else list(INGESTION_DIRS)

    # ── Spawn the child ──────────────────────────────────────────────────
    # THE WORK LEAVES THIS PROCESS (2026-11-26). In-process, an ingest died with every backend cycle
    # — a `--reload`, a restart, a deploy — and left the record saying `running`, which locked the
    # page out. A child in its own session owns its lifetime; this process only starts it and reads
    # the record it writes. `start_new_session=True` is also what makes cancel a group kill.
    _write_status_file(
        IngestStatusFile(
            job_id=job_id,
            status="starting",
            mode=request.mode,
            index_type=request.index_type,
            started_at=started_at,
            dirs=dirs,
            pid=None,
        )
    )

    log_path = Path(Paths.logs_dir) / "ingest.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "ab") as child_log:
        child = subprocess.Popen(  # noqa: S603 — our own module, our own interpreter
            [
                sys.executable,
                "-m",
                "app.domain.rag.ingest_cli",
                "--job-id",
                job_id,
                "--mode",
                request.mode,
                "--index-type",
                request.index_type,
                "--dirs",
                ",".join(dirs),
            ],
            cwd=str(BASE_DIR),
            stdout=child_log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=os.environ.copy(),
        )
    _ingest_children[job_id] = child

    # The record is live from here: the pid is what `is_running()` asks about, so a second Start is
    # refused the moment this returns (and a child that dies instantly is detected on the next read).
    _write_status_file(
        IngestStatusFile(
            job_id=job_id,
            status="running",
            mode=request.mode,
            index_type=request.index_type,
            started_at=started_at,
            dirs=dirs,
            pid=child.pid,
            heartbeat_at=started_at,
            progress=IngestProgress(),
        )
    )

    logger.info(
        "Ingest job %s spawned as pid %s (mode=%s, dirs=%s)",
        job_id,
        child.pid,
        request.mode,
        ",".join(dirs),
    )

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
    _reap()
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
        dirs=status_info.dirs,
        pid=status_info.pid,
        started_at=status_info.started_at,
        completed_at=status_info.completed_at,
        error=status_info.error,
        progress=status_info.progress,
        result=status_info.result,
    )

@rag_router.post(
    "/ingest/cancel",
    status_code=status.HTTP_200_OK,
    summary="Stop the running ingest job",
)
async def cancel_ingest() -> dict:
    """Stop the run, and leave a record that says so.

    The job is a child in its own session, so cancel is a **group kill**: the child's own SIGTERM
    handler writes `cancelled` and exits, and if it is wedged the record is marked here after a short
    wait. Nothing is cancelled by a word in a file alone — the process is asked to stop, and the
    record follows.
    """
    record = _read_status_file()
    if record is not None:
        _reap(record.job_id)
        record = _read_status_file()
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No ingest job has been started yet."
        )
    if not _job_is_live(record):
        return {
            "cancelled": False,
            "status": record.status,
            "message": "No live ingest job: the record's owner is gone (or it already finished).",
        }
    if not record.pid or record.pid == os.getpid():
        # An in-process job (a test, or a caller that ran it here) has no group to signal — killing
        # the group would kill this API. Refuse honestly rather than take the app down with it.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This job runs inside the API process and cannot be signalled; it stops with the app.",
        )

    try:
        os.killpg(record.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass  # it died between the check and the signal — the record check below settles it

    for _ in range(50):  # ~5 s
        await asyncio.sleep(0.1)
        current = _read_status_file()
        if current is not None and current.status != "running":
            return {"cancelled": True, "status": current.status, "job_id": current.job_id}
        if not _pid_is_alive(record.pid):
            # It died without leaving a word (a SIGKILL, a crash, a machine that stopped). The record
            # is settled HERE — a job whose owner is gone must not keep the page locked out.
            _settle_cancelled(record)
            return {"cancelled": True, "status": "cancelled", "job_id": record.job_id}

    # Still alive after the signal: say so instead of pretending it stopped.
    return {
        "cancelled": False,
        "status": "running",
        "job_id": record.job_id,
        "message": "The job did not stop within 5 s — it may be inside an embedding call.",
    }


@rag_router.post(
    "/index/clear",
    status_code=status.HTTP_200_OK,
    summary="Empty the documentation index",
)
async def clear_index(
    embedding: Annotated[EmbeddingService, Depends(_resolve_embedding_service)],
) -> dict:
    """Empty the index — the destructive half of Rebuild, offered on its own.

    Refused while a job is running (a clear under a live writer is a race nobody can reason about).
    The next ingest rebuilds from whatever is on disk.
    """
    from app.domain.tools.builtin.doc_vector_store import DocVectorStore  # noqa: PLC0415

    if RagIngestService.is_running():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An ingest job is running — cancel it before clearing the index.",
        )
    store = DocVectorStore.get_instance(db_path=str(Paths.rag_index_path), embedding=embedding)
    removed = store.clear()
    logger.info("RAG index cleared: %s chunks removed", removed["chunks"])
    return {"cleared": True, **removed}

class IngestEstimateRequest(BaseModel):
    """Request body for ``POST /rag/ingest/estimate``."""

    dirs: list[str] | None = None


@rag_router.post(
    "/ingest/estimate",
    status_code=status.HTTP_200_OK,
    summary="Price a run before starting it",
)
async def estimate_ingest_run(request: IngestEstimateRequest) -> dict:
    """What a run over these roots would cost — files and bytes counted, chunks and minutes estimated.

    The rate is the LAST RUN'S OWN measurement (`result.s_per_chunk`), and the payload says which rate
    it used; an install that has never run is priced with a labelled default. Nothing here starts work.
    """
    if request.dirs is not None and not request.dirs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="name at least one root, or omit them all"
        )
    if request.dirs:
        unknown = [root for root in request.dirs if root not in INGESTION_DIRS]
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"unknown ingestion root(s): {', '.join(unknown)} — known: {', '.join(INGESTION_DIRS)}",
            )

    record = _read_status_file()
    measured = record.result.s_per_chunk if record is not None and record.result is not None else None
    return estimate_ingest(request.dirs, measured)
