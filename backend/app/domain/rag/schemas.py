"""
RAG ingest domain schemas.

Pydantic models for RAG index health, ingest trigger, and job status
request/response validation.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ─── Index Health ─────────────────────────────────────────────────────────────


class RagHealthConfig(BaseModel):
    """Embedding / indexing configuration exposed in the health response."""

    ingestion_dirs: List[str] = Field(
        default_factory=lambda: [
            "wiki/entities",
            "wiki/dev-notes",
        ],
        description="Directories scanned for ingestible documents.",
    )
    embedding_model: Optional[str] = Field(
        default=None,
        description=(
            "The embedding model the index was built with — the `embeddings` capability's model. "
            "Null when the install has configured none: the field reports a fact, it does not supply "
            "a default."
        ),
    )
    index_width: Optional[int] = Field(
        default=None,
        description=(
            "The width the index was CREATED at, read from the index file's vec table — null when "
            "there is no index yet. It is the index's own width, not the model's: the two disagree "
            "after a model change, and a restart does not repair that."
        ),
    )
    running_model: Optional[str] = Field(
        default=None,
        description=(
            "The model the stores IN THIS PROCESS were built with, or null when none has been built "
            "yet. This is what is actually embedding right now — `embedding_model` above is what the "
            "install has CONFIGURED, which is what the next start will use."
        ),
    )
    running_address: Optional[str] = Field(
        default=None,
        description="The address those same stores dial — null when none has been built yet.",
    )
    note: Optional[str] = Field(
        default=None,
        description=(
            "What to say when the configuration and the running process disagree: the width mismatch "
            "(the index must be rebuilt) or the restart note. Null when they agree, or when no store "
            "has been built yet — nothing is then waiting on a restart."
        ),
    )
    ollama_base_url: str | None = Field(
        default=None,
        description=(
            "The Ollama server the ingest actually dials — the `ollama` provider row's endpoint. "
            "Null when no row declares one: the field reports a fact, it does not supply a default."
        ),
    )


class RagStatusResponse(BaseModel):
    """Response model for ``GET /rag/status``."""

    indexed_documents: int = Field(
        ..., ge=0, description="Number of unique source paths in the index."
    )
    total_chunks: int = Field(
        ..., ge=0, description="Total number of indexed chunks."
    )
    last_indexed: Optional[datetime] = Field(
        None, description="Timestamp of the most recent index update."
    )
    database_path: str = Field(
        ..., description="Filesystem path to the vector index database."
    )
    database_size_bytes: int = Field(
        ..., ge=0, description="Size of the database file in bytes."
    )
    config: RagHealthConfig = Field(
        default_factory=RagHealthConfig,
        description="Current embedding/indexing configuration.",
    )


# ─── Ingest Trigger ───────────────────────────────────────────────────────────


class IngestRequest(BaseModel):
    """Request body for ``POST /rag/ingest``."""

    mode: str = Field(
        default="incremental",
        description=(
            "Ingestion mode.  'incremental' only re-indexes files whose "
            "modification time is newer than the last index.  'full' re-processes "
            "all discovered files.  'force-reingest' bypasses incremental checks "
            "and re-indexes everything."
        ),
        pattern=r"^(incremental|full|force-reingest)$",
    )
    index_type: str = Field(
        default="docs",
        description="Which index to rebuild. Currently only 'docs' is supported.",
        pattern=r"^(docs|code)$",
    )


class IngestResponse(BaseModel):
    """Response model for a successfully triggered ingest (202 Accepted)."""

    job_id: str = Field(..., description="Unique job identifier for polling.")
    status: str = Field(
        default="running", description="Initial job status (always 'running')."
    )
    mode: str = Field(..., description="The ingestion mode that was triggered.")
    started_at: datetime = Field(
        ..., description="Timestamp when the job was created."
    )


# ─── Job Status Polling ───────────────────────────────────────────────────────


class IngestProgress(BaseModel):
    """Progress sub-model for a running ingest job.

    Two chunk counters, because they answer different questions. ``total_chunks`` is what the INDEX
    holds from this run — it moves when a document commits. ``chunks_done`` is how far the work has
    got — it moves per chunk, which is the only way a card can show life during a six-minute document
    (measured: `0 / 0` for six minutes while embeddings visibly flowed).
    """

    files_discovered: int = Field(0, ge=0)
    files_processed: int = Field(0, ge=0)
    files_failed: int = Field(0, ge=0)
    total_chunks: int = Field(0, ge=0)
    chunks_done: int = Field(0, ge=0)
    current_file: str = Field("", description="The document being indexed right now, if any.")
    elapsed_seconds: float = Field(0.0, ge=0.0)


class IngestResult(BaseModel):
    """Result sub-model for a completed ingest job."""

    files_discovered: int = Field(..., ge=0)
    files_processed: int = Field(..., ge=0)
    files_failed: int = Field(..., ge=0)
    total_chunks: int = Field(..., ge=0)
    stale_removed: int = Field(0, ge=0)
    elapsed_seconds: float = Field(..., ge=0.0)
    # MEASURED, NOT ASSUMED: the run's own seconds-per-chunk, which the Ingestables tab multiplies by
    # an estimated chunk count to price a run. None when the run indexed nothing.
    s_per_chunk: Optional[float] = Field(
        None, description="Seconds per chunk this run measured — the rate an estimate is built on."
    )


class IngestJobStatusResponse(BaseModel):
    """Response model for ``GET /rag/ingest/status``."""

    job_id: str = Field(..., description="Job identifier.")
    status: str = Field(
        ...,
        description="Job status: 'running', 'completed', 'failed' or 'cancelled'.",
        pattern=r"^(running|completed|failed|cancelled)$",
    )
    mode: str = Field(..., description="The ingestion mode used.")
    dirs: List[str] = Field(default_factory=list, description="The ingestion roots this run was given.")
    pid: Optional[int] = Field(None, description="The process doing the work.")
    started_at: datetime = Field(..., description="Job creation timestamp.")
    completed_at: Optional[datetime] = Field(
        None, description="Job completion timestamp (null while running)."
    )
    error: Optional[str] = Field(
        None, description="Error message if status is 'failed'."
    )
    progress: Optional[IngestProgress] = Field(
        None, description="Progress info while status is 'running'."
    )
    result: Optional[IngestResult] = Field(
        None, description="Final result if status is 'completed'."
    )


# ─── Status File Format (internal, not exposed via API) ───────────────────────


class IngestStatusFile(BaseModel):
    """Internal model matching the on-disk ``data/rag_ingest_status.json`` format.

    THE RECORD IS THE CONTRACT between the UI, the API and the process doing the work, so liveness is
    carried IN it rather than inferred from one word: ``pid`` says which process owns the job and
    ``heartbeat_at`` says when it last proved it was alive. A record that says ``running`` with a dead
    pid or a cold heartbeat is a job nobody is doing — and that is what used to lock the RAG page out
    for good (`is_running()` was the word alone).
    """

    job_id: str
    status: str  # running | completed | failed | cancelled
    mode: str
    index_type: str = "docs"
    started_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    dirs: List[str] = Field(
        default_factory=list, description="The ingestion roots this run was given."
    )
    pid: Optional[int] = Field(None, description="The process doing the work (None before it starts).")
    heartbeat_at: Optional[datetime] = Field(
        None, description="Last proof of life from that process."
    )
    progress: Optional[IngestProgress] = None
    result: Optional[IngestResult] = None
