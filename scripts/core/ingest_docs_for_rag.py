#!/usr/bin/env python3
"""
Ingest documentation files into the RAG vector index.

Discovers markdown files in configured documentation directories, chunks them
with heading-aware splitting, computes embeddings via the Ollama HTTP API, and
stores vectors in the sqlite-vec powered ``data/system_docs_vector.db``.

Usage
-----
    # Dry run — preview without modifying the index
    uv run python3 scripts/ingest_docs_for_rag.py --dry-run

    # Full ingest — process all discovered files
    uv run python3 scripts/ingest_docs_for_rag.py

    # Incremental — only re-index files that have changed
    uv run python3 scripts/ingest_docs_for_rag.py --incremental

    # Force re-ingest — re-process everything from scratch
    uv run python3 scripts/ingest_docs_for_rag.py --force-reingest

    # Verbose output — per-file progress and configuration details
    uv run python3 scripts/ingest_docs_for_rag.py --verbose

Environment variables
---------------------
    OLLAMA_BASE_URL   Ollama server base URL  (default: http://localhost:11434)
    DOC_INDEX_PATH    Path to vector index DB (default: data/system_docs_vector.db)

Exit codes
----------
    0   Success
    1   Error (initialization failure or file ingestion errors)
"""

from __future__ import annotations

import argparse
import importlib.util
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set, Tuple

logger = logging.getLogger(__name__)

# ─── Module Loading ──────────────────────────────────────────────────────────

# The ``app.domain.tools.builtin`` package's ``__init__.py`` eagerly imports all
# built-in tool classes, which triggers circular imports through the the external agent
# module chain.  To avoid this, we load ``doc_vector_store`` directly via
# ``importlib``, skipping the package-level ``__init__.py`` entirely.

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DOC_VECTOR_STORE_PATH = (
    _PROJECT_ROOT / "backend" / "app" / "domain" / "tools" / "builtin" / "doc_vector_store.py"
)

_spec = importlib.util.spec_from_file_location(
    "doc_vector_store",
    str(_DOC_VECTOR_STORE_PATH),
)
assert _spec is not None, f"Could not find module at {_DOC_VECTOR_STORE_PATH}"
_dvs = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_dvs)

# Re-export constants, the class, and helper functions for use in this script.
DEFAULT_DB_PATH = _dvs.DEFAULT_DB_PATH
DEFAULT_OLLAMA_BASE = _dvs.DEFAULT_OLLAMA_BASE
DEFAULT_EMBEDDING_MODEL = _dvs.DEFAULT_EMBEDDING_MODEL
DEFAULT_EMBEDDING_DIMS = _dvs.DEFAULT_EMBEDDING_DIMS
DEFAULT_BATCH_SIZE = _dvs.DEFAULT_BATCH_SIZE
DocVectorStore = _dvs.DocVectorStore
_rebuild_doc_index_json = _dvs._rebuild_doc_index_json

# ─── Constants ────────────────────────────────────────────────────────────────

# Directories to ingest (relative to project root).
# These are the initial scope for the RAG corpus; expand as needed.
INGESTION_DIRS: List[str] = [
    "docs",
]

# Allowed file extensions — only markdown for now.
ALLOWED_EXTENSIONS: Set[str] = {".md"}

# Denied path patterns (reused from doc_reader.py).
# These prevent indexing of non-documentation artifacts.
DENIED_PATTERNS: List[str] = [
    ".env",
    ".venv",
    "node_modules",
    "__pycache__",
    "*.db",
    "*.sqlite",
    "*.log",
    "backend/app",
]

# Environment variable names for configuration overrides.
ENV_OLLAMA_BASE_URL = "OLLAMA_BASE_URL"
ENV_DOC_INDEX_PATH = "DOC_INDEX_PATH"

# ─── File Discovery ────────────────────────────────────────────────────────────


def _matches_denied(path: str, patterns: List[str]) -> bool:
    """Check if *path* matches any of the denied patterns.

    Uses :func:`fnmatch.fnmatch` for glob-style matching (e.g. ``*.db``),
    and also checks if the pattern appears as a path component.
    """
    from fnmatch import fnmatch

    for pattern in patterns:
        if fnmatch(path, pattern):
            return True
        # Check if pattern matches any path component
        normalized = "/" + pattern.lstrip("/")
        if normalized in path:
            return True
    return False


def discover_files(
    ingest_dirs: List[str],
    allowed_extensions: Set[str],
    denied_patterns: List[str],
    project_root: Path,
) -> List[Tuple[Path, str]]:
    """Walk ingestion directories and return discoverable files.

    Returns a list of ``(absolute_path, relative_path)`` tuples where
    ``relative_path`` is the path relative to *project_root* (used as the
    ``source_path`` when indexing).

    Files are sorted alphabetically for deterministic ordering.
    """
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
                # File is outside project root — skip silently
                continue

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


# ─── Stats Tracking ──────────────────────────────────────────────────────────


class IngestionStats:
    """Collect and report ingestion metrics."""

    def __init__(self) -> None:
        self.files_discovered: int = 0
        self.files_skipped: int = 0
        self.files_processed: int = 0
        self.files_failed: int = 0
        self.total_chunks: int = 0
        self.stale_removed: int = 0
        self._start = time.time()

    @property
    def elapsed(self) -> float:
        return time.time() - self._start

    def report(self, verbose: bool = False) -> str:
        lines = [
            "─" * 52,
            "  Ingestion Complete",
            "─" * 52,
            f"  Files discovered:      {self.files_discovered}",
        ]
        if self.files_skipped:
            lines.append(
                f"  Files skipped (incr):  {self.files_skipped}"
            )
        lines.extend([
            f"  Files processed:       {self.files_processed}",
            f"  Files failed:          {self.files_failed}",
            f"  Chunks indexed:        {self.total_chunks}",
            f"  Stale chunks removed:  {self.stale_removed}",
            f"  Elapsed time:          {self.elapsed:.2f}s",
            "─" * 52,
        ])
        return "\n".join(lines)


# ─── Ingestion Pipeline ──────────────────────────────────────────────────────


def run_ingestion(
    *,
    dry_run: bool = False,
    incremental: bool = False,
    force_reingest: bool = False,
    verbose: bool = False,
    project_root: Path = _PROJECT_ROOT,
) -> int:
    """Execute the RAG documentation ingestion pipeline.

    Parameters
    ----------
    dry_run:
        Preview what would be ingested without modifying the store.
    incremental:
        Only re-index files whose modification time is newer than the index.
    force_reingest:
        Re-process all discovered files (bypasses incremental check).
    verbose:
        Print per-file progress and detailed configuration.
    project_root:
        Root directory of the project (where ``data/``, ``docs/`` etc. live).

    Returns
    -------
    Exit code — ``0`` for success, ``1`` if any files failed.
    """
    # ── Resolve configuration ─────────────────────────────────────────────
    ollama_base = os.environ.get(ENV_OLLAMA_BASE_URL, DEFAULT_OLLAMA_BASE)
    doc_index_rel = os.environ.get(ENV_DOC_INDEX_PATH, DEFAULT_DB_PATH)
    doc_index_abs = str(
        (project_root / doc_index_rel).resolve()
        if not os.path.isabs(doc_index_rel)
        else Path(doc_index_rel).resolve()
    )

    stats = IngestionStats()

    # ── File discovery ────────────────────────────────────────────────────
    if verbose:
        print(f"Project root:  {project_root}")
        print(f"Ingestion dirs: {', '.join(INGESTION_DIRS)}")
        print(f"Index path:    {doc_index_abs}")
        print(f"Ollama base:   {ollama_base}")
        print(f"Model:         {DEFAULT_EMBEDDING_MODEL} ({DEFAULT_EMBEDDING_DIMS}d)")

    discovered = discover_files(
        INGESTION_DIRS,
        ALLOWED_EXTENSIONS,
        DENIED_PATTERNS,
        project_root,
    )
    stats.files_discovered = len(discovered)

    # Capture full set before incremental filtering so stale cleanup
    # can distinguish files that are up-to-date from files that are gone.
    all_discovered_paths: Set[str] = {rel_path for _, rel_path in discovered}

    if not discovered:
        print("No files discovered for ingestion. Nothing to do.")
        return 0

    if verbose:
        print(f"\nDiscovered {len(discovered)} file(s):")
        for _, rel_path in discovered[:15]:
            print(f"  {rel_path}")
        if len(discovered) > 15:
            print(f"  ... and {len(discovered) - 15} more")

    # ── Incremental / force-reingest filtering ────────────────────────────
    if incremental and not force_reingest:
        indexed_paths = _load_indexed_paths(doc_index_abs)
        if verbose:
            print(f"\nIndex contains {len(indexed_paths)} path(s)")

        filtered: List[Tuple[Path, str]] = []
        for abs_path, rel_path in discovered:
            mtime = abs_path.stat().st_mtime
            if _is_stale(rel_path, mtime, indexed_paths):
                filtered.append((abs_path, rel_path))
            else:
                stats.files_skipped += 1
                if verbose:
                    print(f"  [UP-TO-DATE] {rel_path}")

        discovered = filtered

        if not discovered:
            print(
                f"\nAll {stats.files_discovered} files are up to date. "
                "Nothing to do."
            )
            return 0

        if verbose:
            print(
                f"\nFiles to (re-)index after incremental filter: "
                f"{len(discovered)}"
            )

    # ── Dry run — report without modifying the store ──────────────────────
    if dry_run:
        total_bytes = sum(p.stat().st_size for p, _ in discovered)
        avg_chars = 2000  # heuristic: ~one chunk per 2000 bytes ≈ 500 tokens
        estimated_chunks = sum(
            max(1, p.stat().st_size // avg_chars) for p, _ in discovered
        )

        print()
        print("═" * 52)
        print("  DRY RUN — No changes will be made")
        print("═" * 52)
        print(f"  Files to ingest:      {len(discovered)}")
        print(f"  Total size:           {total_bytes:,} bytes")
        print(f"  Estimated chunks:     ~{estimated_chunks}")
        print(f"  Embedding model:      {DEFAULT_EMBEDDING_MODEL}")
        print(f"  Embedding dimensions: {DEFAULT_EMBEDDING_DIMS}")
        print(f"  Index path:           {doc_index_abs}")
        print(f"  Ollama base URL:      {ollama_base}")
        print(f"  Mode:                 ", end="")
        if incremental:
            print("incremental")
        elif force_reingest:
            print("force re-ingest")
        else:
            print("full")
        print("─" * 52)
        for abs_path, rel_path in discovered:
            print(f"  {rel_path}  ({abs_path.stat().st_size:,} bytes)")
        print("─" * 52)
        return 0

    # ── Initialize DocVectorStore ─────────────────────────────────────────
    if verbose:
        print(f"\nInitialising DocVectorStore...")

    try:
        store = DocVectorStore.get_instance(
            db_path=doc_index_abs,
            ollama_base=ollama_base,
            embedding_model=DEFAULT_EMBEDDING_MODEL,
            embedding_dims=DEFAULT_EMBEDDING_DIMS,
            batch_size=DEFAULT_BATCH_SIZE,
        )
        store.init_db()
    except Exception as exc:
        logger.error("DocVectorStore initialisation failed: %s", exc)
        print(f"ERROR: Could not initialise vector store — {exc}", file=sys.stderr)
        return 1

    # ── Ingestion loop ────────────────────────────────────────────────────
    total = len(discovered)
    print(f"\nIngesting {total} file(s) ...")

    for idx, (abs_path, rel_path) in enumerate(discovered, 1):
        try:
            content = abs_path.read_text(encoding="utf-8")
            if not content.strip():
                if verbose:
                    print(f"  [{idx:>{len(str(total))}}/{total}] {rel_path}  (empty)")
                continue

            n_chunks = store.index_document(rel_path, content)
            stats.total_chunks += n_chunks
            stats.files_processed += 1

            if verbose:
                print(
                    f"  [{idx:>{len(str(total))}}/{total}] {rel_path}  "
                    f"→ {n_chunks} chunk{'s' if n_chunks != 1 else ''}"
                )
            elif idx % 10 == 0 or idx == total:
                print(f"  Progress: {idx}/{total}")

        except Exception as exc:
            stats.files_failed += 1
            logger.error("Failed to ingest %s: %s", rel_path, exc)
            print(f"  [ERROR] {rel_path}: {exc}", file=sys.stderr)

    # ── Stale document cleanup ───────────────────────────────────────────
    if verbose:
        print(f"\nCleaning up stale documents ...")

    try:
        existing = all_discovered_paths
        stats.stale_removed = store.remove_stale_documents(existing)
        if verbose and stats.stale_removed:
            print(f"  Removed {stats.stale_removed} stale chunk(s)")
    except Exception as exc:
        logger.error("Stale-document cleanup failed: %s", exc)
        print(f"  [WARN] Stale cleanup error — {exc}", file=sys.stderr)

    # ── Regenerate doc index ─────────────────────────────────────────────
    if not dry_run:
        if verbose:
            print(f"\nRegenerating docs/.doc_index.json ...")
        try:
            _rebuild_doc_index_json(doc_index_abs, project_root)
            if verbose:
                print(f"  Regenerated docs/.doc_index.json")
        except Exception as exc:
            logger.error("Failed to regenerate doc index: %s", exc)
            print(f"  [WARN] Doc index regeneration failed — {exc}", file=sys.stderr)

    # ── Final report ──────────────────────────────────────────────────────
    print()
    print(stats.report(verbose=verbose))

    return 0 if stats.files_failed == 0 else 1


# ─── CLI Entry Point ─────────────────────────────────────────────────────────


def main() -> None:
    """Parse command-line arguments and start ingestion."""
    parser = argparse.ArgumentParser(
        description=(
            "Ingest documentation files into the RAG vector index.  "
            "Discovers markdown files, chunks them, computes embeddings via "
            "Ollama, and stores vectors in data/system_docs_vector.db."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Environment variables:\n"
            f"  {ENV_OLLAMA_BASE_URL}   (default: {DEFAULT_OLLAMA_BASE})\n"
            f"  {ENV_DOC_INDEX_PATH}    (default: {DEFAULT_DB_PATH})"
        ),
    )

    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Preview what would be ingested without modifying the index",
    )
    parser.add_argument(
        "--incremental",
        "-i",
        action="store_true",
        help=(
            "Only re-index files whose modification time is newer than "
            "the last index"
        ),
    )
    parser.add_argument(
        "--force-reingest",
        "-f",
        action="store_true",
        help=(
            "Re-process all discovered files from scratch "
            "(bypasses incremental check)"
        ),
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show per-file progress, configuration, and debug output",
    )

    args = parser.parse_args()

    # Resolve project root: the parent of the ``scripts/`` directory.
    project_root = _PROJECT_ROOT

    exit_code = run_ingestion(
        dry_run=args.dry_run,
        incremental=args.incremental,
        force_reingest=args.force_reingest,
        verbose=args.verbose,
        project_root=project_root,
    )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
