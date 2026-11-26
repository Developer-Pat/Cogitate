"""
DocVectorStore — sqlite-vec powered vector store for the RAG system.

Provides a singleton-managed vector index backed by sqlite-vec, with:
  - Heading-aware markdown chunking
  - Ollama HTTP API embeddings (primary, via ``httpx``)
  - ANN vector search via sqlite-vec ``vec0`` virtual table
  - Graceful degradation: embedding failures log errors and return empty results

Architecture
────────────
Two tables in ``data/system_docs_vector.db``:

1. ``doc_chunks`` — metadata table (source path, chunk text, line range, etc.)
2. ``vec_docs`` — sqlite-vec virtual table (embeddings with cosine distance)

Usage
─────
    store = DocVectorStore.get_instance()
    store.init_db()

    # Index a document
    store.index_document("docs/atlas/some-file.md", content_str)

    # Search
    results = store.search(query_embedding, top_k=5)

    # Clean up stale entries
    store.remove_stale_documents(existing_paths={"docs/atlas/some-file.md", ...})
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, cast

import httpx
import sqlite3

# sqlite-vec must be loaded into the sqlite3 connection;
# the ``sqlite_vec`` package provides the loadable extension.
import sqlite_vec  # type: ignore[import-untyped]

from app.domain.providers.embeddings import (
    EmbeddingService,
    declared_width_of,
    width_mismatch_report,
)

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

DEFAULT_DB_PATH = "data/system_docs_vector.db"  # fallback; the canonical
#   path is Paths.rag_index_path (Phase 4, 2026-08-18) — the locator
#   is the single resolver; the string default only covers callers
#   that never pass a db_path and never loaded the app config.

# Maximum characters to send to the embedding model in a single call.
# nomic-embed-text has a 2048-token limit (~1500 chars), and crashes with HTTP 500
# on inputs over ~1020 chars with this model version.  Set safely at 950.
MAX_EMBED_CHARS = 950
# NO ADDRESS, MODEL OR DIMS LIVE HERE (the service-literals arc's model half, 2026-10-10). This module
# used to carry all three — `DEFAULT_OLLAMA_BASE`, and `DEFAULT_EMBEDDING_MODEL`/`DEFAULT_EMBEDDING_DIMS`
# (`nomic-embed-text`, 768) copied into four further modules. None of them is a property of THIS store:
# which server embeds, which model runs and how wide the vectors are is ONE decision, made in the
# `embeddings` capability and answered by `resolve_embedding_service`. The store receives that answer
# as a constructor argument and writes nothing down — `EmbeddingService` carries the three facts, and
# its `report()` is what a caller shows when the install has configured none of them.
DEFAULT_BATCH_SIZE = 16
DEFAULT_TOP_K = 10
MAX_TOP_K = 20
DEFAULT_MIN_SCORE = 0.0

# Maximum chunk size in characters before splitting on paragraph boundaries.
# Approx 250 tokens at ~4 chars/token.
MAX_CHUNK_CHARS = 4000

# ─── Heading-Aware Chunker ────────────────────────────────────────────────────


def chunk_document(
    content: str,
    source_path: str,
    max_chunk_chars: int = MAX_CHUNK_CHARS,
) -> List[Dict[str, Any]]:
    """Split a markdown document into heading-aware chunks.

    Each chunk preserves its heading ancestry so results include context like
    "## Installation > ### Linux" rather than just the final sub-section text.

    Parameters
    ----------
    content:
        Raw markdown content of the document.
    source_path:
        File path for tracking provenance.
    max_chunk_chars:
        Maximum characters per chunk.  Oversized sections are split on paragraph
        boundaries (double newlines).

    Returns
    -------
    List of dicts with keys: ``source_path``, ``chunk_text``, ``heading``,
    ``heading_ancestry``, ``char_start``, ``char_end``, ``checksum``.
    """
    if not content or not content.strip():
        return []

    lines = content.split("\n")
    chunks: List[Dict[str, Any]] = []

    # Parse headings: (level, text, line_number)
    headings: List[Tuple[int, str, int]] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        m = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            headings.append((level, text, i))

    if not headings:
        # No headings — treat entire document as one chunk
        checksum = hashlib.md5(content.encode("utf-8")).hexdigest()
        chunks.append({
            "source_path": source_path,
            "chunk_text": content.strip(),
            "heading": "",
            "heading_ancestry": "",
            "char_start": 0,
            "char_end": len(content),
            "checksum": checksum,
        })
        return chunks

    # Build sections: each heading starts a new section, subsuming content until
    # the next heading of the same or higher level.
    sections: List[Dict[str, Any]] = []
    for idx, (level, text, line_num) in enumerate(headings):
        # Determine section content range
        start_line = line_num
        if idx + 1 < len(headings):
            end_line = headings[idx + 1][2]
        else:
            end_line = len(lines)

        section_lines = lines[start_line:end_line]

        # Build heading ancestry
        ancestry_parts: List[str] = []
        for prev_level, prev_text, _ in headings[:idx]:
            if prev_level < level:
                ancestry_parts.append(prev_text)
        ancestry = " > ".join(ancestry_parts) if ancestry_parts else ""

        sections.append({
            "level": level,
            "heading": text,
            "heading_ancestry": ancestry,
            "start_line": start_line,
            "end_line": end_line,
            "text": "\n".join(section_lines).strip(),
        })

    # Chunk each section, splitting oversized ones on paragraph boundaries
    for sec in sections:
        if len(sec["text"]) <= max_chunk_chars:
            checksum = hashlib.md5(sec["text"].encode("utf-8")).hexdigest()
            # Calculate char positions (approximate from line ranges)
            char_start = sum(len(line) + 1 for line in lines[:sec["start_line"]])
            char_end = char_start + len(sec["text"])
            chunks.append({
                "source_path": source_path,
                "chunk_text": sec["text"],
                "heading": sec["heading"],
                "heading_ancestry": sec["heading_ancestry"],
                "char_start": char_start,
                "char_end": char_end,
                "checksum": checksum,
            })
        else:
            # Split on paragraph boundaries
            paragraphs = re.split(r"\n\s*\n", sec["text"])
            current_chunk = ""
            char_pos = sum(len(line) + 1 for line in lines[:sec["start_line"]])

            for para in paragraphs:
                if not para.strip():
                    continue
                if len(current_chunk) + len(para) + 1 > max_chunk_chars and current_chunk:
                    # Finalize current chunk
                    checksum = hashlib.md5(current_chunk.encode("utf-8")).hexdigest()
                    chunks.append({
                        "source_path": source_path,
                        "chunk_text": current_chunk.strip(),
                        "heading": sec["heading"],
                        "heading_ancestry": sec["heading_ancestry"],
                        "char_start": char_pos,
                        "char_end": char_pos + len(current_chunk),
                        "checksum": checksum,
                    })
                    char_pos += len(current_chunk) + 2
                    current_chunk = para
                else:
                    if current_chunk:
                        current_chunk += "\n\n" + para
                    else:
                        current_chunk = para

            if current_chunk.strip():
                checksum = hashlib.md5(current_chunk.encode("utf-8")).hexdigest()
                chunks.append({
                    "source_path": source_path,
                    "chunk_text": current_chunk.strip(),
                    "heading": sec["heading"],
                    "heading_ancestry": sec["heading_ancestry"],
                    "char_start": char_pos,
                    "char_end": char_pos + len(current_chunk),
                    "checksum": checksum,
                })

    return chunks


# ─── DocVectorStore ────────────────────────────────────────────────────────────


class DocVectorStore:
    """sqlite-vec powered vector store for document chunks.

    Uses a lazy singleton pattern — call ``DocVectorStore.get_instance()``
    to obtain the shared instance.
    """

    _instance: Optional["DocVectorStore"] = None
    _lock = threading.Lock()
    # The vec table this store owns — named once, because two readers need it: `init_db` creates it and
    # `_declared_width` asks the index what width it was CREATED at (see the width guard below).
    VEC_TABLE = "vec_docs"

    def __init__(
        self,
        db_path: str,
        embedding: "EmbeddingService",
        batch_size: int = DEFAULT_BATCH_SIZE,
    ):
        self.db_path = db_path
        # THE EMBEDDING SERVICE IS PASSED IN AND KEPT AS ONE THING. The three values below are
        # read OFF it for the calls that need them; an UNRESOLVED service (an install with no
        # embedding model) leaves them empty, and every use refuses loudly through
        # `_refuse_unconfigured` rather than dialling a guessed address or a 768-wide default.
        self.embedding = embedding
        self.ollama_base = (embedding.address or "").rstrip("/")
        self.embedding_model = embedding.model or ""
        self.embedding_dims = embedding.dims or 0
        self.batch_size = batch_size
        self._db: Optional[sqlite3.Connection] = None
        # THE STORE IS USED FROM MORE THAN ONE THREAD (2026-11-26). The ingest ran its per-document
        # work ON the event loop's thread, so a 16-second embedding call froze the whole app; the fix
        # moves that work to a worker thread, which means this store's connection is now touched by
        # the loop (a tool searching) and a worker (a document being written) at the same time.
        # `check_same_thread=False` makes that legal (CPython's sqlite3 is serialized:
        # `sqlite3.threadsafety == 3`), and this lock makes the write half ATOMIC — a reader never
        # sees a document half-deleted and half-inserted. It is re-entrant because `index_document`
        # takes it and then calls `_remove_document`, which takes it again.
        self._write_lock = threading.RLock()
        self._initialized = False

    def _refuse_unconfigured(self) -> bool:
        """Refuse to work when the embedding service resolved to nothing — loudly, one wording.

        The vec table's WIDTH is the model's width, so an install with no embedding model has no table
        to create and no call to make. Returning True here is the store's half of the arc's rule: it
        reports the gap (``EmbeddingService.report``, the same line `/rag/status` shows) instead of
        dialling a guessed address or assuming the old 768.
        """
        if self.embedding.resolved:
            return False
        logger.error("DocVectorStore unusable — %s", self.embedding.report())
        return True

    def _declared_width(self) -> Optional[int]:
        """The width the vec table was CREATED at — read from the INDEX, never from the service.

        `init_db` declares the table from the resolved dims with ``IF NOT EXISTS``, so an existing
        table keeps the width it was born with: a model change to another width leaves the index
        behind, and a restart does not repair it. Reading ``sqlite_master`` is a plain text query — it
        needs no vec extension and creates nothing.
        """
        if not os.path.isfile(self.db_path):
            return None
        try:
            conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
            try:
                row = conn.execute(
                    "SELECT sql FROM sqlite_master WHERE name = ?", (self.VEC_TABLE,)
                ).fetchone()
            finally:
                conn.close()
        except sqlite3.Error as exc:
            logger.warning("DocVectorStore: could not read %s's declared width: %s", self.VEC_TABLE, exc)
            return None
        return declared_width_of(row[0] if row else None)

    def _refuse_width_mismatch(self) -> bool:
        """Refuse when the index was built at another width than the configured model's.

        This is the half a restart does NOT repair, which is why it refuses rather than proceeding:
        inserting a 1024-wide vector into a ``float[768]`` table is refused by sqlite-vec, but only
        AFTER the app has spent a call on it — and the honest answer is that the index has to be
        rebuilt, which is what the report says.
        """
        if not self.embedding.resolved or not self.embedding_dims:
            return False  # the unconfigured guard owns that case, and reports it
        declared = self._declared_width()
        if declared is None or declared == self.embedding_dims:
            return False
        logger.error(
            "DocVectorStore unusable — %s", width_mismatch_report(declared, self.embedding)
        )
        return True

    def _refuse(self) -> bool:
        """Refuse to work when the store cannot be trusted: nothing configured, or an index of another width."""
        return self._refuse_unconfigured() or self._refuse_width_mismatch()

    # ── Singleton ──────────────────────────────────────────────────────────

    @classmethod
    def get_instance(
        cls,
        db_path: str,
        embedding: "EmbeddingService",
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> "DocVectorStore":
        """Return the shared singleton instance.

        On first call the instance is created with the provided parameters;
        subsequent calls ignore parameters (singleton is already configured).

        **That first-wins rule is safe as long as callers agree on the embedding service, and they
        do**: every caller resolves it from the SAME `embeddings` capability, so the second caller's
        values are the first caller's. What a caller may NOT do is construct this store before the
        capability is configured and expect it to pick the model up later — the service is captured
        here, so a changed capability needs `reset_instance()` (the singleton trap, said out loud
        rather than discovered). **The write path does exactly that**: `capabilities.replace_chain`
        drops both stores when an `embeddings` chain changes (`close=False`, so a mid-flight ingest is
        not broken), which is what makes a saved model reach the running process.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(
                        db_path=db_path,
                        embedding=embedding,
                        batch_size=batch_size,
                    )
        return cls._instance

    @classmethod
    def current_service(cls) -> Optional["EmbeddingService"]:
        """The service the instance IN THIS PROCESS was built with — ``None`` if none has been built.

        The singleton trap's READ side: a surface that wants to say what is ACTUALLY embedding asks
        here, because re-resolving the capability answers what the NEXT process will use.
        """
        with cls._lock:
            return cls._instance.embedding if cls._instance is not None else None

    @classmethod
    def reset_instance(cls, *, close: bool = True) -> None:
        """Forget the singleton.

        `close=True` (the default, and what the tests use) also closes the instance's connection.
        **`close=False` is the production path**: the capability write resets both stores when an
        `embeddings` chain changes (`capabilities.replace_chain` → `_drop_embedding_stores`), and an
        ingest may be MID-FLIGHT on that connection. Left open, that run finishes against the service it
        started with, writing the widths its own table was built for; the instance becomes unreachable,
        so the connection closes when it is collected. (Closing it instead would break the running
        ingest — the change is supposed to reach the NEXT use, not to kill the current one.)
        """
        with cls._lock:
            if cls._instance is not None:
                if close and cls._instance._db:
                    cls._instance._db.close()
                cls._instance = None

    # ── Database Initialization ────────────────────────────────────────────

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create the sqlite3 connection with sqlite-vec loaded."""
        with self._write_lock:
            if self._db is None:
                # Ensure parent directory exists
                db_dir = Path(self.db_path).parent
                db_dir.mkdir(parents=True, exist_ok=True)

                # `check_same_thread=False`: the ingest writes from a worker thread while a tool may
                # read from the event loop's (see `_write_lock`). The connection is created under the
                # lock so two threads cannot build two connections.
                self._db = sqlite3.connect(self.db_path, check_same_thread=False)
                self._db.row_factory = sqlite3.Row
                self._db.enable_load_extension(True)
                sqlite_vec.load(self._db)
                self._db.enable_load_extension(False)
                self._db.execute("PRAGMA journal_mode=WAL")
            return self._db

    def init_db(self) -> None:
        """Create tables if they don't exist.

        Creates:
        - ``doc_chunks`` — metadata / content store
        - ``vec_docs`` — sqlite-vec virtual table for ANN search
        """
        if self._refuse():
            return  # the width IS the model's; with no model there is no table to declare
        db = self._get_connection()

        # Metadata table
        db.execute("""
            CREATE TABLE IF NOT EXISTS doc_chunks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                source_path TEXT    NOT NULL,
                chunk_text  TEXT    NOT NULL,
                heading     TEXT    NOT NULL DEFAULT '',
                heading_ancestry TEXT NOT NULL DEFAULT '',
                char_start  INTEGER NOT NULL DEFAULT 0,
                char_end    INTEGER NOT NULL DEFAULT 0,
                checksum    TEXT    NOT NULL,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
                updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)

        # Index on source_path for fast listing / staleness checks
        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_doc_chunks_source_path
            ON doc_chunks(source_path)
        """)

        # Index on checksum for incremental detection
        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_doc_chunks_checksum
            ON doc_chunks(checksum)
        """)

        # sqlite-vec virtual table for embeddings
        # NOTE: vec0 uses a fixed dimension; we use the configured embedding_dims.
        db.execute(f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS {self.VEC_TABLE} USING vec0(
                embedding float[{self.embedding_dims}] distance_metric=cosine
            )
        """)

        self._initialized = True
        logger.info(
            "DocVectorStore initialized: path=%s, dims=%d, model=%s",
            self.db_path, self.embedding_dims, self.embedding_model,
        )

    # ── Embedding ──────────────────────────────────────────────────────────

    def _call_ollama_embed(self, text: str) -> Optional[List[float]]:
        """Call the Ollama embeddings API for a single text.

        Truncates text to ``MAX_EMBED_CHARS`` (~950 chars) to stay within the
        model's token limit (2048 tokens for ``nomic-embed-text``).  Longer
        prompts cause Ollama to return HTTP 500.

        Returns ``None`` on failure (logged, not raised).
        """
        if self._refuse():
            return None
        # Truncate to stay within model token budget
        if len(text) > MAX_EMBED_CHARS:
            text = text[:MAX_EMBED_CHARS]

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    f"{self.ollama_base}/api/embeddings",
                    json={"model": self.embedding_model, "prompt": text},
                )
                resp.raise_for_status()
                data = resp.json()
                embedding = data.get("embedding")
                if embedding is None:
                    logger.error(
                        "Ollama embedding returned no embedding field: %s",
                        data,
                    )
                    return None
                return cast(list[float] | None, embedding)
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Ollama embedding HTTP %d for '%s': %s",
                exc.response.status_code,
                self.embedding_model,
                exc,
            )
            return None
        except httpx.RequestError as exc:
            logger.error("Ollama embedding request failed: %s", exc)
            return None
        except Exception as exc:
            logger.error("Unexpected error in Ollama embedding: %s", exc)
            return None

    def embed_query(self, text: str) -> Optional[List[float]]:
        """Embed a single query string.

        Returns a list of floats (the embedding vector) or ``None`` on failure.
        """
        return self._call_ollama_embed(text)

    def embed_chunks(
        self, chunks: List[str], on_chunk: Optional[Callable[[], None]] = None
    ) -> List[Optional[List[float]]]:
        """Embed a list of chunk texts in batches.

        Returns a parallel list where each element is either an embedding
        vector or ``None`` if that chunk's embedding failed.

        ``on_chunk`` is called after EVERY chunk, before the next one starts. That is the ingest's
        heartbeat: a document with forty chunks takes minutes on a CPU-only box, and without a per-chunk
        signal the run's record sits at the last file it finished and reads as dead.
        """
        results: List[Optional[List[float]]] = []
        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i : i + self.batch_size]
            # Ollama API only supports one prompt per request,
            # so we call sequentially within the batch for now.
            # A future optimization could parallelize with asyncio.
            for text in batch:
                emb = self._call_ollama_embed(text)
                results.append(emb)
                if on_chunk is not None:
                    on_chunk()
        return results

    # ── Indexing ───────────────────────────────────────────────────────────

    def index_document(
        self, source_path: str, content: str, on_chunk: Optional[Callable[[], None]] = None
    ) -> int:
        """Chunk, embed, and store a document in the vector index.

        ``on_chunk`` is passed straight to :meth:`embed_chunks` — the caller's heartbeat.

        Parameters
        ----------
        source_path:
            The file path of the document (used as provenance).
        content:
            The full text content of the document.

        Returns
        -------
        Number of chunks indexed.  0 if embedding fails entirely.
        """
        if not self._initialized:
            self.init_db()

        chunks = chunk_document(content, source_path)
        if not chunks:
            return 0

        # Remove existing entries for this source path before re-indexing
        self._remove_document(source_path)

        # THE SLOW HALF STAYS OUTSIDE THE LOCK. Embedding is one blocking HTTP call per chunk — 16
        # seconds for a full-size chunk on a CPU-only box — and a search must not queue behind it.
        texts = [c["chunk_text"] for c in chunks]
        embeddings = self.embed_chunks(texts, on_chunk=on_chunk)

        # THE WRITE HALF IS ATOMIC (see `_write_lock`): a reader sees the document whole or not at all.
        with self._write_lock:
            db = self._get_connection()
            inserted = 0

            for chunk, emb in zip(chunks, embeddings):
                if emb is None:
                    logger.warning(
                        "Skipping chunk (embedding failed): %s heading=%s",
                        source_path, chunk.get("heading", ""),
                    )
                    continue

                # Insert metadata row
                cursor = db.execute(
                    """
                    INSERT INTO doc_chunks
                        (source_path, chunk_text, heading, heading_ancestry,
                         char_start, char_end, checksum)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk["source_path"],
                        chunk["chunk_text"],
                        chunk.get("heading", ""),
                        chunk.get("heading_ancestry", ""),
                        chunk.get("char_start", 0),
                        chunk.get("char_end", 0),
                        chunk["checksum"],
                    ),
                )
                chunk_id = cursor.lastrowid

                # Insert embedding into vec_docs virtual table
                from sqlite_vec import serialize_float32

                db.execute(
                    "INSERT INTO vec_docs (rowid, embedding) VALUES (?, ?)",
                    (chunk_id, serialize_float32(emb)),
                )
                inserted += 1

            db.commit()
        logger.info(
            "Indexed %d/%d chunks from %s",
            inserted, len(chunks), source_path,
        )
        return inserted

    def _remove_document(self, source_path: str) -> int:
        """Remove all chunks for a given source path.

        Returns the number of chunks removed.
        """
        if not self._initialized:
            self.init_db()

        with self._write_lock:
            db = self._get_connection()

            # Find chunk IDs for this source path
            cursor = db.execute(
                "SELECT id FROM doc_chunks WHERE source_path = ?",
                (source_path,),
            )
            ids = [row["id"] for row in cursor.fetchall()]

            if not ids:
                return 0

            # Delete from vec_docs (virtual table)
            for chunk_id in ids:
                try:
                    db.execute("DELETE FROM vec_docs WHERE rowid = ?", (chunk_id,))
                except Exception as exc:
                    logger.warning(
                        "Failed to delete vec_docs rowid=%d: %s", chunk_id, exc,
                    )

            # Delete from metadata table
            db.execute(
                "DELETE FROM doc_chunks WHERE source_path = ?",
                (source_path,),
            )
            db.commit()
            return len(ids)

    def remove_stale_documents(self, existing_paths: Set[str]) -> int:
        """Remove vector entries for documents that no longer exist.

        Parameters
        ----------
        existing_paths:
            Set of source paths that still exist on disk.  Any chunk whose
            ``source_path`` is NOT in this set will be removed.

        Returns
        -------
        Number of stale chunks removed.
        """
        if not self._initialized:
            self.init_db()

        db = self._get_connection()

        # Find all distinct source paths in the index
        cursor = db.execute("SELECT DISTINCT source_path FROM doc_chunks")
        indexed_paths = {row["source_path"] for row in cursor.fetchall()}

        stale = indexed_paths - existing_paths
        total_removed = 0
        for path in stale:
            removed = self._remove_document(path)
            total_removed += removed
            if removed:
                logger.info("Removed stale index for %s (%d chunks)", path, removed)

        return total_removed

    # ── Indexed Paths Listing ──────────────────────────────────────────────

    def list_indexed_paths(self) -> List[str]:
        """Return all distinct source paths currently in the vector index.

        Queries the ``doc_chunks`` table and returns a sorted list of
        unique ``source_path`` values.

        Returns
        -------
        List of source path strings (empty list if the table doesn't exist yet).
        """
        if not self._initialized:
            self.init_db()

        db = self._get_connection()
        try:
            cursor = db.execute("SELECT DISTINCT source_path FROM doc_chunks ORDER BY source_path")
            return [row["source_path"] for row in cursor.fetchall()]
        except sqlite3.OperationalError:
            # Table may not exist yet
            return []

    # ── Search ─────────────────────────────────────────────────────────────

    def search(
        self,
        embedding: List[float],
        top_k: int = DEFAULT_TOP_K,
        min_score: float = DEFAULT_MIN_SCORE,
        source_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Perform ANN vector search.

        Parameters
        ----------
        embedding:
            The query embedding vector.
        top_k:
            Maximum number of results (clamped to ``MAX_TOP_K``).
        min_score:
            Minimum similarity score threshold (1.0 = perfect match,
            0.0 = orthogonal).  Results below this threshold are excluded.
        source_filter:
            Optional glob-style filter to restrict results to a specific
            source path prefix (e.g. ``"docs/atlas/%"``).

        Returns
        -------
        List of result dicts with keys: ``source_path``, ``chunk_text``,
        ``heading``, ``heading_ancestry``, ``similarity_score``,
        ``char_start``, ``char_end``.
        """
        if not self._initialized:
            self.init_db()

        top_k = min(top_k, MAX_TOP_K)
        db = self._get_connection()

        from sqlite_vec import serialize_float32

        try:
            serialized = serialize_float32(embedding)
        except Exception as exc:
            logger.error("Failed to serialize embedding: %s", exc)
            return []

        # Search the vector index
        try:
            cursor = db.execute(
                """
                SELECT rowid, distance
                FROM vec_docs
                WHERE embedding MATCH ?
                  AND k = ?
                """,
                (serialized, top_k),
            )
            vector_results = list(cursor.fetchall())
        except Exception as exc:
            logger.error("sqlite-vec search failed: %s", exc)
            return []

        if not vector_results:
            return []

        # Fetch metadata for matching rows
        ids = [row["rowid"] for row in vector_results]
        distance_map = {row["rowid"]: row["distance"] for row in vector_results}

        placeholders = ",".join("?" for _ in ids)
        query = f"""
            SELECT id, source_path, chunk_text, heading, heading_ancestry,
                   char_start, char_end
            FROM doc_chunks
            WHERE id IN ({placeholders})
        """

        # Apply source filter if provided
        params: List[Any] = ids
        if source_filter:
            query += " AND source_path LIKE ?"
            params.append(source_filter)

        cursor = db.execute(query, params)
        rows = cursor.fetchall()

        results: List[Dict[str, Any]] = []
        for row in rows:
            chunk_id = row["id"]
            distance = distance_map.get(chunk_id, 1.0)
            # sqlite-vec returns cosine distance (0 = identical, 2 = opposite).
            # Convert to similarity score: 1.0 - (distance / 2)
            similarity = 1.0 - (distance / 2.0)

            if similarity < min_score:
                continue

            results.append({
                "source_path": row["source_path"],
                "chunk_text": row["chunk_text"],
                "heading": row["heading"] or "",
                "heading_ancestry": row["heading_ancestry"] or "",
                "similarity_score": round(similarity, 4),
                "char_start": row["char_start"],
                "char_end": row["char_end"],
            })

        # Sort by similarity descending (already ordered by distance ascending
        # from sqlite-vec, but source_filter may have removed some)
        results.sort(key=lambda r: r["similarity_score"], reverse=True)

        return results


# ─── Doc Index JSON Rebuild ───────────────────────────────────────────────────


def _derive_subtopic_name(filename: str, slug: str) -> str:
    """Derive a human-readable subtopic name from a filename.

    Strips the ``.md`` extension, handles special cases like ``README``,
    and converts kebab-case / snake_case to Title Case.

    Examples::

        "README.md"           → "Overview"
        "data-flow.md"        → "Data Flow"
        "agents-developer-guide.md" → "Agents Developer Guide"
        "system-manager-guide.md"  → "System Manager Guide"
        "2026-03-30_foo.md"         → "Foo"
    """
    name = filename.replace(".md", "")

    # Known special mappings
    special = {"README": "Overview"}
    if name in special:
        return special[name]

    # Remove leading date stamps like "2026-03-30_"
    name_clean = re.sub(r"^\d{4}-\d{2}-\d{2}[_-]?", "", name)
    # Remove trailing dates
    name_clean = re.sub(r"[_-]\d{4}-\d{2}-\d{2}", "", name_clean)
    # Also remove any remaining 4-digit year orphan suffix
    name_clean = re.sub(r"\s+\d{4}-\d{2}-\d{2}(?:-\d{2})?", "", name_clean)

    if not name_clean.strip():
        return slug.replace("-", " ").title()

    # kebab-case / snake_case → Title Case
    return name_clean.replace("-", " ").replace("_", " ").strip().title()


def _build_topic_tree(paths: List[str]) -> Dict[str, Any]:
    """Build a topic tree from indexed source paths.

    Maps paths like ``docs/architecture/data-flow.md`` to topic slug
    ``"architecture"`` with a subtopic derived from the filename.
    Grouping is done by the first path segment after ``docs/``.

    Returns a dict matching the ``topics`` schema of ``data/.doc_index.json``::

        {
            "architecture": {
                "title": "System Architecture",
                "description": "...",
                "subtopics": {
                    "Data Flow": {
                        "description": "...",
                        "paths": ["docs/architecture/data-flow.md"]
                    },
                    ...
                }
            },
            ...
        }
    """
    topics: Dict[str, Any] = {}

    # Human-readable topic metadata keyed by directory slug
    TOPIC_META: Dict[str, Dict[str, str]] = {
        "architecture": {
            "title": "System Architecture",
            "description": "System architecture documentation, decision records, and data flow diagrams.",
        },
        "atlas": {
            "title": "Application Atlas Documentation",
            "description": "Application Atlas feature documentation and guides.",
        },
        "cognitive-architecture": {
            "title": "Cognitive Architecture",
            "description": "Cognitive hub and system architecture.",
        },
        "dev_notes": {
            "title": "Developer Notes",
            "description": "Detailed developer guides covering agents, workflows, tools, tracing, sessions, configuration, and more.",
        },
    }

    for path in paths:
        # Only consider paths under the ingestion roots (wiki/entities,
        # wiki/dev-notes — former docs/ layout)
        parts = path.split("/")
        if len(parts) < 2:
            continue
        if parts[0] == "wiki":
            if len(parts) < 3 or parts[1] not in ("entities", "dev-notes"):
                continue
            slug = parts[2]
        elif parts[0] == "docs":
            slug = parts[1]
        else:
            continue

        # Derive topic metadata
        meta = TOPIC_META.get(slug)
        if meta is None:
            meta = {
                "title": slug.replace("-", " ").title(),
                "description": f"Documentation for {slug.replace('-', ' ')}.",
            }

        if slug not in topics:
            topics[slug] = {
                "title": meta["title"],
                "description": meta["description"],
                "subtopics": {},
            }

        # Build subtopic from the filename
        filename = parts[-1]
        subtopic_name = _derive_subtopic_name(filename, slug)

        if subtopic_name not in topics[slug]["subtopics"]:
            topics[slug]["subtopics"][subtopic_name] = {
                "description": f"Documents related to {subtopic_name.lower()}.",
                "paths": [],
            }

        if path not in topics[slug]["subtopics"][subtopic_name]["paths"]:
            topics[slug]["subtopics"][subtopic_name]["paths"].append(path)

    return topics


def _rebuild_doc_index_json(db_path: str, project_root: Path) -> None:
    """Query the vector index and regenerate ``data/.doc_index.json``.

    This function:
    1. Queries all distinct ``source_path`` values from ``doc_chunks``.
    2. Groups them by their parent directory slug.
    3. Builds a topic tree following the same schema as the doc-index file.
    4. Reads the current file's ``version`` field and increments it.
    5. Writes the result atomically (write to temp file, then rename).

    Parameters
    ----------
    db_path:
        Absolute path to the sqlite-vec database file.
    project_root:
        Root directory of the project (parent of the ``docs/`` folder).
    """
    # 1. Query all distinct source_paths from doc_chunks
    if not os.path.isfile(db_path):
        logger.warning("Doc index DB not found at %s — skipping rebuild", db_path)
        return

    paths: List[str] = []
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT DISTINCT source_path FROM doc_chunks")
        paths = [row[0] for row in cursor.fetchall()]
        conn.close()
    except sqlite3.OperationalError as exc:
        logger.warning("Cannot query doc_chunks table: %s — skipping rebuild", exc)
        return

    # 2. Build topic tree from paths
    topics = _build_topic_tree(paths)

    # 3. Read existing version
    index_path = project_root / "data" / ".doc_index.json"
    version = 1
    if index_path.exists():
        try:
            with open(index_path, encoding="utf-8") as f:
                existing = json.load(f)
                version = existing.get("version", 1) + 1
        except (json.JSONDecodeError, OSError):
            version = 1

    # 4. Write atomically (temp file + rename)
    data = {"version": version, "topics": topics}
    fd, tmp = tempfile.mkstemp(
        suffix=".json",
        prefix=".doc_index_",
        dir=str(index_path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, str(index_path))
        logger.info("Regenerated data/.doc_index.json (version %d, %d topics)", version, len(topics))
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
