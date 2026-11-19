"""
RAG ingest domain.

Provides ``RagIngestService`` for orchestrating documentation ingestion into
the ``DocVectorStore`` (sqlite-vec) index, along with Pydantic schemas for
request/response validation.

Usage::

    from app.domain.rag.service import RagIngestService
    from app.domain.rag.schemas import RagStatusResponse, IngestRequest
"""

from app.domain.rag.schemas import (
    IngestProgress,
    IngestRequest,
    IngestResponse,
    IngestResult,
    IngestJobStatusResponse,
    IngestStatusFile,
    RagHealthConfig,
    RagStatusResponse,
)
from app.domain.rag.service import RagIngestService

__all__ = [
    "RagIngestService",
    "RagStatusResponse",
    "RagHealthConfig",
    "IngestRequest",
    "IngestResponse",
    "IngestJobStatusResponse",
    "IngestProgress",
    "IngestResult",
    "IngestStatusFile",
]
