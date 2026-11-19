"""
RAG ingest domain service.

Provides ``RagIngestService`` — the orchestrator for RAG documentation ingestion.
Manages the status file, discovers files, runs incremental checks, and delegates
to ``DocVectorStore`` for chunking/embedding/indexing.

Designed to be called from both the REST API (via ``asyncio.create_task``) and
the CLI script (``scripts/core/ingest_docs_for_rag.py``).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import tempfile
import time
from datetime import datetime, timezone
from fnmatch import fnmatch
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from app.core.config import BASE_DIR, Paths
from app.core.system_manager import SystemManagerConfig
from app.domain.providers.embeddings import (
    EmbeddingService,
    configuration_note,
    declared_width_of,
)
from app.domain.rag.schemas import (
    IngestProgress,
    IngestResult,
    IngestStatusFile,
    RagHealthConfig,
    RagStatusResponse,
)

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

STATUS_FILE = str(Paths.rag_status_file)

# Directories to ingest (relative to project root).
#
# ⚠️ COUPLING WARNING ⚠️
# This list determines what documents are vector-indexed and searchable via
# the doc-reader tool's ``semantic_search`` operation.  If you narrow this
# list, agents will no longer be able to find documents outside
# these directories via semantic search — even though the doc-reader's
# ``read`` / ``search`` operations may still have filesystem access to them
# (see ``doc_reader.py:ALLOWED_BASE_DIRS``).
#
# When modifying this list, also consider updating ``ALLOWED_BASE_DIRS`` in
# ``backend/app/domain/tools/builtin/doc_reader.py`` to keep the two in sync.
INGESTION_DIRS: List[str] = [
    # PHASE-4 (2026-08-18, the user's call): the WHOLE wiki — the
    # knowledge surface the RAG exists to serve. The 547-doc index
    # was built from roughly this surface before the wiki grew;
    # entities + dev-notes alone shrank it to 82.
    "wiki/entities",
    "wiki/dev-notes",
    "wiki/atlas",
    "wiki/help",
    "wiki/docs",
    "wiki/references",
]

# Allowed file extensions — only markdown for now.
ALLOWED_EXTENSIONS: Set[str] = {".md"}

# Denied path patterns — prevent indexing of non-documentation artifacts.
DENIED_PATTERNS: List[str] = [
    ".env",
    ".venv",
    "node_modules",
    "__pycache__",
    "display-tests",  # test artifacts — not knowledge (Phase 4)
    "_archive",  # archived docs — stale by definition (Phase 4)
    "*.db",
    "*.sqlite",
    "*.log",
    "backend/app",
]


# ─── File Discovery Helpers ───────────────────────────────────────────────────


def _matches_denied(path: str, patterns: List[str]) -> bool:
    """Check if *path* matches any of the denied patterns.

    Uses :func:`fnmatch.fnmatch` for glob-style matching (e.g. ``*.db``),
    and also checks if the pattern appears as a path component.
    """
    for pattern in patterns:
        if fnmatch(path, pattern):
            return True
        # Check if pattern matches any path component
        normalized = "/" + pattern.lstrip("/")
        if normalized in path:
            return True
    return False


def discover_files(
    ingest_dirs: Optional[List[str]] = None,
    allowed_extensions: Optional[Set[str]] = None,
    denied_patterns: Optional[List[str]] = None,
    project_root: Optional[Path] = None,
) -> List[Tuple[Path, str]]:
    """Walk ingestion directories and return discoverable files.

    Returns a list of ``(absolute_path, relative_path)`` tuples where
    ``relative_path`` is the path relative to *project_root* (used as the
    ``source_path`` when indexing).

    Files are sorted alphabetically for deterministic ordering.
    """
    ingest_dirs = ingest_dirs or INGESTION_DIRS
    allowed_extensions = allowed_extensions or ALLOWED_EXTENSIONS
    denied_patterns = denied_patterns or DENIED_PATTERNS
    project_root = project_root or BASE_DIR

    files: List[Tuple[Path, str]] = []
    for dir_rel in ingest_dirs:
        dir_abs = (project_root / dir_rel).resolve()
        if not dir_abs.exists():
            logger.warning("Ingestion directory not found, skipping: %s", dir_abs)
            continue
        if not dir_abs.is_dir():
            logger.warning("Path is not a directory, skipping: %s", dir_abs)
            continue

        for file_path in sorted(dir_abs.rglob("*")):
            if not file_path.is_file():
                continue

            # Filter by allowed extension
            if file_path.suffix.lower() not in allowed_extensions:
                continue

            # Compute relative path for indexing and pattern-matching
            try:
                rel_path = str(file_path.relative_to(project_root))
            except ValueError:
                continue  # outside project root — skip

            # Skip files matching denied patterns
            if _matches_denied(rel_path, denied_patterns):
                continue

            # Skip hidden files and directories
            if any(part.startswith(".") for part in file_path.parts):
                continue

            files.append((file_path, rel_path))

    return files


# ─── Incremental Mode Helpers ────────────────────────────────────────────────


def _load_indexed_paths(db_path: str) -> Dict[str, str]:
    """Query *doc_chunks* for every source path and its latest *updated_at*.

    Returns a dict mapping ``source_path → updated_at`` (ISO-8601 datetime
    string).  Returns an empty dict if the database file does not exist or
    the table has not been created yet.
    """
    if not os.path.isfile(db_path):
        return {}

    import sqlite3

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """
            SELECT source_path, MAX(updated_at) AS updated_at
            FROM doc_chunks
            GROUP BY source_path
            """
        )
        result: Dict[str, str] = {
            row["source_path"]: row["updated_at"] for row in cursor.fetchall()
        }
        conn.close()
        return result
    except (sqlite3.OperationalError, sqlite3.DatabaseError) as exc:
        logger.warning("Cannot query index for incremental check: %s", exc)
        return {}


def _is_stale(rel_path: str, mtime: float, indexed: Dict[str, str]) -> bool:
    """Determine if a file needs re-indexing.

    Returns ``True`` if:
    - The file is not yet in the index (new file).
    - The file's modification time is newer than its last index *updated_at*.
    """
    indexed_ts = indexed.get(rel_path)
    if indexed_ts is None:
        return True  # not indexed yet

    try:
        indexed_dt = datetime.fromisoformat(indexed_ts)
        # DB stores UTC timestamps via SQLite's datetime('now');
        # ensure we parse as UTC to avoid local-timezone skew.
        if indexed_dt.tzinfo is None:
            indexed_dt = indexed_dt.replace(tzinfo=timezone.utc)
        indexed_mtime = indexed_dt.timestamp()
    except (ValueError, TypeError):
        return True  # unparseable timestamp → re-index to be safe

    return mtime > indexed_mtime


# ─── Status File Management ───────────────────────────────────────────────────


def _read_status_file() -> Optional[IngestStatusFile]:
    """Read the on-disk status file, returning ``None`` if missing or corrupt."""
    try:
        with open(STATUS_FILE, "r") as f:
            data = json.load(f)
        return IngestStatusFile(**data)
    except (FileNotFoundError, json.JSONDecodeError, TypeError) as exc:
        logger.debug("No valid status file found: %s", exc)
        return None


def _write_status_file(status: IngestStatusFile) -> None:
    """Write the status file atomically (write to temp, rename)."""
    # Ensure parent directory exists
    Path(STATUS_FILE).parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(
        suffix=".json",
        prefix="rag_ingest_status_",
        dir=str(Path(STATUS_FILE).parent),
    )
    try:
        with os.fdopen(fd, "w") as f:
            f.write(status.model_dump_json(indent=2, by_alias=False))
        os.replace(tmp_path, STATUS_FILE)
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ─── RagIngestService ─────────────────────────────────────────────────────────


def declared_index_width(db_path: "str | Path") -> Optional[int]:
    """The width the index's vec table was CREATED at — read from the INDEX, never from a model.

    `DocVectorStore.init_db` declares the table from the resolved dims with ``IF NOT EXISTS``, so an
    existing table keeps the width it was born with. Two surfaces need to know: `/rag/status` reports
    it, and the capability write compares it with the model being saved (`configuration_note`). Reading
    ``sqlite_master`` is a plain text query — it needs no vec extension and creates nothing.
    """
    path = Path(db_path)
    if not path.is_file():
        return None
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            row = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'vec_docs'").fetchone()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        logger.warning("could not read the index's declared width: %s", exc)
        return None
    return declared_width_of(row[0] if row else None)


class RagIngestService:
    """Orchestrates RAG ingestion jobs with progress tracking.

    This is a stateless service class; all state is persisted in the JSON
    status file at ``data/rag_ingest_status.json``.
    """

    # ── Status Queries (class methods — no instance needed) ──────────────

    @classmethod
    def get_status(cls) -> Optional[IngestStatusFile]:
        """Return the current job status, or ``None`` if no job has run yet."""
        return _read_status_file()

    @classmethod
    def is_running(cls) -> bool:
        """Check whether an ingest job is currently running."""
        status = _read_status_file()
        return status is not None and status.status == "running"

    @classmethod
    def get_index_health(
        cls,
        config: SystemManagerConfig,
        embedding: EmbeddingService,
        running: Optional[EmbeddingService] = None,
    ) -> RagStatusResponse:
        """Query the vector index and return health statistics.

        Args:
            config: System manager config, for ``doc_index_path``.
            embedding: the resolved embedding service — the address the ingest dials, the model it
                embeds with, and (through the model) the width of the vectors already in the index.
                The caller resolves it (the `embeddings` capability); this method REPORTS it, and an
                unresolved service is reported as such rather than completed with a default.
            running: what the stores IN THIS PROCESS were built with, or None when none has been built
                yet. Passed in so the response can say when the configuration and the running process
                disagree (`configuration_note`) instead of reporting a model the process is not using.

        Returns:
            A ``RagStatusResponse`` with index stats and configuration.
        """
        # THE INDEX'S PATH COMES FROM THE ONE LOCATOR — the same resolution the ingest uses
        # (`:433` below), and that both search routes, `doc_reader` and the registry all read.
        #
        # This method used to join a RELATIVE `config.doc_index_path` onto `data_dir`, so the default
        # `data/system_docs_vector.db` resolved to `<install>/data/data/system_docs_vector.db` — a file
        # that never exists. An install WITH an index was therefore reported as an empty one: zero
        # documents, zero chunks, size 0 (measured 2026-10-12 against a 55 MB index). Found while
        # landing option C of the embedding-configuration issue, in this same function.
        #
        # An absolute path in the config is still honoured as given.
        _idx = Path(config.doc_index_path)
        db_path = str(_idx if _idx.is_absolute() else Paths.rag_index_path)
        db_size = 0
        doc_count = 0
        chunk_count = 0
        index_width: Optional[int] = None
        last_indexed: Optional[datetime] = None

        # Try to query the database
        if os.path.isfile(db_path):
            import sqlite3

            try:
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row

                # Count distinct source paths (documents)
                cursor = conn.execute(
                    "SELECT COUNT(DISTINCT source_path) AS cnt FROM doc_chunks"
                )
                doc_count = cursor.fetchone()["cnt"] or 0

                # Count total chunks
                cursor = conn.execute("SELECT COUNT(*) AS cnt FROM doc_chunks")
                chunk_count = cursor.fetchone()["cnt"] or 0

                # Most recent update
                cursor = conn.execute(
                    "SELECT MAX(updated_at) AS max_ts FROM doc_chunks"
                )
                row = cursor.fetchone()
                if row and row["max_ts"]:
                    ts = row["max_ts"]
                    try:
                        last_indexed = datetime.fromisoformat(ts)
                    except (ValueError, TypeError):
                        pass

                # THE INDEX'S OWN WIDTH, read from the table it was CREATED as. `init_db` declares the
                # vec table from the resolved dims with IF NOT EXISTS, so an existing table keeps its
                # original width: after a model change of a different width the index and the model
                # disagree, and the note below says so. (The read itself lives in
                # `declared_index_width`, because the capability write needs the same number.)
                index_width = declared_index_width(db_path)

                conn.close()

                db_size = os.path.getsize(db_path)
            except Exception as exc:
                logger.warning("Failed to query doc index health: %s", exc)

        # THE ADDRESS, THE MODEL AND THE DIMS ARE RESOLVED, NOT DEFAULTED (2026-10-10, the
        # service-literals arc — the address half, then its model half). These lines used to be
        # `getattr(config, "ollama_base_url", "http://localhost:11434")` and
        # `config.embedding_model` / `config.embedding_dimensions` — against a field
        # `SystemManagerConfig` does not have, so the address literal was ALWAYS the live value, and
        # the model/dims were two more copies of one fact. The router resolves the `embeddings`
        # capability and passes the one answer in; `None` halves are reported as null.
        return RagStatusResponse(
            indexed_documents=doc_count,
            total_chunks=chunk_count,
            last_indexed=last_indexed,
            database_path=config.doc_index_path,
            database_size_bytes=db_size,
            config=RagHealthConfig(
                ingestion_dirs=list(INGESTION_DIRS),
                embedding_model=embedding.model,
                index_width=index_width,
                running_model=running.model if running else None,
                running_address=running.address if running else None,
                note=configuration_note(embedding, index_width),
                ollama_base_url=embedding.address,
            ),
        )

    # ── Instance Methods ─────────────────────────────────────────────────

    def __init__(self) -> None:
        self._project_root: Path = BASE_DIR

    async def run(
        self,
        mode: str,
        index_type: str = "docs",
        config: Optional[SystemManagerConfig] = None,
        embedding: Optional[EmbeddingService] = None,
    ) -> None:
        """Execute the ingestion pipeline in a background task.

        Args:
            mode: ``"incremental"``, ``"full"``, or ``"force-reingest"``.
            index_type: Which index to rebuild (currently only ``"docs"``).
            config: System manager config. If ``None``, uses code-level defaults.
            embedding: the resolved embedding service (the `embeddings` capability). Required: an
                ingest without an address, a model and a width would write vectors nobody can read.

        This method is designed to be run via ``asyncio.create_task()``.
        It updates the status file as it progresses and handles all exceptions
        internally, writing the final status (``completed`` or ``failed``).
        """
        # ── Resolve configuration ─────────────────────────────────────────
        if config is None:
            config = SystemManagerConfig.defaults()

        # THE ADDRESS, THE MODEL AND THE DIMS ARRIVE TOGETHER (2026-10-10, the service-literals arc's
        # model half): the router resolves the `embeddings` capability and passes the one answer in.
        # The address alone was the previous rung's guard; the model and the dims are the same class
        # of fact, so anything less than all three STOPS here and says which half is missing (the
        # router refuses up front with a 503; this is the guard for a direct caller).
        if embedding is None or not embedding.resolved:
            raise RuntimeError((embedding or EmbeddingService()).report())
        # PHASE-4 (2026-08-18): the index path resolves through the
        # locator — the config override still wins when set (tests,
        # custom installs), else the canonical Paths entry.
        doc_index_rel = config.doc_index_path
        doc_index_abs = str(
            Path(doc_index_rel).resolve()
            if doc_index_rel and os.path.isabs(doc_index_rel)
            else Paths.rag_index_path
        )

        job_id = f"rag-ingest-{int(time.time())}"
        started_at = datetime.now(timezone.utc)

        # Initialise progress
        progress = IngestProgress.model_construct()
        status = IngestStatusFile(
            job_id=job_id,
            status="running",
            mode=mode,
            index_type=index_type,
            started_at=started_at,
            progress=progress,
        )
        _write_status_file(status)

        # ── File discovery ────────────────────────────────────────────────
        try:
            discovered = discover_files(project_root=self._project_root)
        except Exception as exc:
            logger.error("File discovery failed: %s", exc)
            status.status = "failed"
            status.error = f"File discovery failed: {exc}"
            status.completed_at = datetime.now(timezone.utc)
            _write_status_file(status)
            return

        progress.files_discovered = len(discovered)

        # Capture full set before incremental filtering so stale cleanup
        # can distinguish uptodate files from missing files.
        all_discovered_paths: Set[str] = {rel_path for _, rel_path in discovered}

        if not discovered:
            logger.info("No files discovered for ingestion.")
            status.status = "completed"
            status.completed_at = datetime.now(timezone.utc)
            progress.elapsed_seconds = (datetime.now(timezone.utc) - started_at).total_seconds()
            status.progress = progress
            status.result = IngestResult(
                files_discovered=0,
                files_processed=0,
                files_failed=0,
                total_chunks=0,
                stale_removed=0,
                elapsed_seconds=progress.elapsed_seconds,
            )
            _write_status_file(status)
            return

        # ── Incremental filtering ─────────────────────────────────────────
        if mode == "incremental":
            indexed_paths = _load_indexed_paths(doc_index_abs)
            filtered: List[Tuple[Path, str]] = []
            for abs_path, rel_path in discovered:
                mtime = abs_path.stat().st_mtime
                if _is_stale(rel_path, mtime, indexed_paths):
                    filtered.append((abs_path, rel_path))
                # Files that are up-to-date are simply skipped
            discovered = filtered

            if not discovered:
                logger.info("All %d files are up to date.", progress.files_discovered)
                status.status = "completed"
                status.completed_at = datetime.now(timezone.utc)
                progress.elapsed_seconds = (datetime.now(timezone.utc) - started_at).total_seconds()
                status.progress = progress
                status.result = IngestResult(
                    files_discovered=progress.files_discovered,
                    files_processed=0,
                    files_failed=0,
                    total_chunks=0,
                    stale_removed=0,
                    elapsed_seconds=progress.elapsed_seconds,
                )
                _write_status_file(status)
                return

        # ── Initialise DocVectorStore ─────────────────────────────────────
        # NOTE: Lazy import to avoid circular import via
        # builtin/__init__.py → config_inspector → stream_service → router.
        from app.domain.tools.builtin.doc_vector_store import DocVectorStore  # noqa: PLC0415

        try:
            store = DocVectorStore.get_instance(
                db_path=doc_index_abs,
                embedding=embedding,
                batch_size=config.embedding_batch_size,
            )
            store.init_db()
        except Exception as exc:
            logger.error("DocVectorStore initialisation failed: %s", exc)
            status.status = "failed"
            status.error = f"Vector store initialisation failed: {exc}"
            status.completed_at = datetime.now(timezone.utc)
            _write_status_file(status)
            return

        # ── Ingestion loop ────────────────────────────────────────────────
        total = len(discovered)
        logger.info("Ingesting %d file(s) ...", total)

        for abs_path, rel_path in discovered:
            try:
                content = abs_path.read_text(encoding="utf-8")
                if not content.strip():
                    logger.debug("Skipping empty file: %s", rel_path)
                    continue

                n_chunks = store.index_document(rel_path, content)
                progress.total_chunks += n_chunks
                progress.files_processed += 1

                logger.debug(
                    "Indexed %s → %d chunk(s) (%d/%d)",
                    rel_path, n_chunks, progress.files_processed, total,
                )

            except Exception as exc:
                progress.files_failed += 1
                logger.error("Failed to ingest %s: %s", rel_path, exc)

            # Update progress after every file
            progress.elapsed_seconds = (datetime.now(timezone.utc) - started_at).total_seconds()
            status.progress = progress
            _write_status_file(status)

            # Yield control briefly so the event loop can handle other tasks
            # (e.g., polling requests for status).
            await asyncio.sleep(0)

        # ── Stale document cleanup ────────────────────────────────────────
        stale_removed = 0
        try:
            stale_removed = store.remove_stale_documents(all_discovered_paths)
            if stale_removed:
                logger.info("Removed %d stale chunk(s)", stale_removed)
        except Exception as exc:
            logger.error("Stale-document cleanup failed: %s", exc)

        # ── Regenerate doc index ─────────────────────────────────────────
        try:
            from app.domain.tools.builtin.doc_vector_store import _rebuild_doc_index_json  # noqa: PLC0415

            _rebuild_doc_index_json(doc_index_abs, self._project_root)
        except Exception as exc:
            logger.error("Failed to regenerate doc index: %s", exc)

        # ── Final status ──────────────────────────────────────────────────
        elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
        status.status = "completed"
        status.completed_at = datetime.now(timezone.utc)
        status.progress = None  # clear progress in favour of result
        status.result = IngestResult(
            files_discovered=progress.files_discovered,
            files_processed=progress.files_processed,
            files_failed=progress.files_failed,
            total_chunks=progress.total_chunks,
            stale_removed=stale_removed,
            elapsed_seconds=elapsed,
        )
        _write_status_file(status)

        logger.info(
            "Ingest complete: %d processed, %d failed, %d chunks, %d stale removed (%.1fs)",
            status.result.files_processed,
            status.result.files_failed,
            status.result.total_chunks,
            status.result.stale_removed,
            elapsed,
        )
