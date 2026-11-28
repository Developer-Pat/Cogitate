"""
CodeVectorStore — sqlite-vec powered vector store for source code (Code RAG).

Provides a singleton-managed vector index backed by sqlite-vec, with:
  - AST-based chunking for Python (via ``ast`` module)
  - Regex-based chunking for TypeScript/TSX
  - Whole-file chunking for config files
  - Ollama HTTP API embeddings (primary, via ``httpx``)
  - ANN vector search via sqlite-vec ``vec0`` virtual table
  - Graceful degradation: embedding failures log errors and return empty results

Architecture
────────────
Two tables in ``data/system_code_vector.db``:

1. ``code_chunks`` — metadata table (source path, language, symbol name, chunk type, content)
2. ``vec_code`` — sqlite-vec virtual table (embeddings with cosine distance)

Usage
─────
    store = CodeVectorStore.get_instance()
    store.init_db()

    # Index a Python file
    store.add_document("backend/app/some/module.py", language="python")

    # Search
    results = store.semantic_search("tool execution flow", top_k=5)

    # Search with language filter
    results = store.semantic_search("query", top_k=5, language_filter="python")
"""

from __future__ import annotations

import ast
import hashlib
import logging
import os
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, cast

import httpx
import sqlite3

import sqlite_vec  # type: ignore[import-untyped]

from app.domain.providers.embeddings import (
    EmbeddingService,
    declared_width_of,
    max_embed_chars_for,
    width_mismatch_report,
)

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

DEFAULT_DB_PATH = "data/system_code_vector.db"  # fallback; the canonical
#   path is Paths.code_vector_path (Phase 4, 2026-08-18).
# NO ADDRESS, MODEL OR DIMS LIVE HERE (the service-literals arc's model half, 2026-10-10): this module
# used to carry `DEFAULT_OLLAMA_BASE`, `DEFAULT_EMBEDDING_MODEL` and `DEFAULT_EMBEDDING_DIMS`, the
# same three values the doc store and the cognitive store carried. They are not properties of this
# store — which server embeds, which model runs and how wide the vectors are is ONE decision, made in
# the `embeddings` capability — so the store receives the resolved `EmbeddingService` and writes
# nothing down.
DEFAULT_BATCH_SIZE = 16
DEFAULT_TOP_K = 10
MAX_TOP_K = 20
DEFAULT_MIN_SCORE = 0.0

# THE INPUT BUDGET IS THE MODEL'S (2026-11-26) — the same one-lookup the doc store uses
# (`embeddings.max_embed_chars_for`). Code is token-denser than prose, which is why the budget is
# conservative; what must not happen is a chunk the embedder then trims, which is what these two
# constants used to allow (4,000 cut here, 950 sent there).
MAX_CHUNK_CHARS = 2000

# Maximum text length (in characters) to send to the embedding model.
# nomic-embed-text has a ~2048 token limit but the runner process crashes
# on inputs over ~1020 chars with this model version.  Set safely at 950.
# retired: the input budget is the MODEL's (`max_embed_chars_for`), looked up in the store's
# constructor — a hardcoded 950 here meant the embedder trimmed three quarters of anything long.

# Language detection by file extension
EXTENSION_LANGUAGE_MAP: Dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".json": "config",
    ".toml": "config",
    ".yaml": "config",
    ".yml": "config",
    ".env.example": "config",
    ".cfg": "config",
    ".ini": "config",
}

# ─── Python AST Chunker ───────────────────────────────────────────────────────


def _get_source_segment_safe(
    source_lines: List[str],
    node: ast.AST,
) -> Optional[str]:
    """Safely extract source code segment for an AST node.

    Wraps :func:`ast.get_source_segment` in a try/except since it can fail
    on nodes spanning multiple lines or with positional information gaps.
    """
    try:
        return ast.get_source_segment("\n".join(source_lines), node)
    except (IndentationError, TypeError, ValueError):
        return None


def chunk_python_file(file_path: Path) -> List[Dict[str, Any]]:
    """Chunk a Python source file using AST-based extraction.

    Walks the AST and produces one chunk per:
      - Top-level function/async function definition
      - Top-level class definition (class as a whole)
      - Top-level assignment (module-level constants, config)
      - Top-level ``if __name__`` block

    Returns a list of chunk dicts with keys: ``source_path``, ``content``,
    ``language``, ``symbol_name``, ``chunk_type``, ``line_start``,
    ``line_end``, ``checksum``.
    """
    source_text = file_path.read_text(encoding="utf-8", errors="replace")
    source_lines = source_text.split("\n")

    try:
        tree = ast.parse(source_text, filename=str(file_path))
    except SyntaxError as exc:
        logger.warning("Syntax error in %s: %s — indexing as whole file", file_path, exc)
        # Fall back to whole-file chunk
        checksum = hashlib.md5(source_text.encode("utf-8")).hexdigest()
        return [{
            "source_path": str(file_path),
            "content": source_text.strip(),
            "language": "python",
            "symbol_name": file_path.stem,
            "chunk_type": "module",
            "line_start": 1,
            "line_end": len(source_lines),
            "checksum": checksum,
        }]

    chunks: List[Dict[str, Any]] = []
    seen_ranges: Set[Tuple[int, int]] = set()  # dedup overlapping nodes

    for node in ast.iter_child_nodes(tree):
        # iter_child_nodes() returns only direct children of the module,
        # so these are top-level by definition
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue

        if not hasattr(node, "lineno") or not hasattr(node, "end_lineno"):
            continue

        line_start: int = node.lineno  # type: ignore[assignment]
        line_end: int | None = node.end_lineno  # type: ignore[assignment]

        if line_end is None:
            continue

        # Deduplicate: skip if this range overlaps with a larger parent
        if any(s <= line_start and line_end <= e for s, e in seen_ranges):
            continue
        seen_ranges.add((line_start, line_end))

        # Extract source segment
        segment = _get_source_segment_safe(source_lines, node)
        if not segment:
            # Fall back to line-based extraction
            segment = "\n".join(source_lines[line_start - 1 : line_end])

        if isinstance(node, ast.ClassDef):
            symbol_name = node.name
            chunk_type = "class"
        elif isinstance(node, ast.AsyncFunctionDef):
            symbol_name = node.name
            chunk_type = "function"
        elif isinstance(node, ast.FunctionDef):
            symbol_name = node.name
            chunk_type = "function"
        else:
            continue

        checksum = hashlib.md5(segment.encode("utf-8")).hexdigest()

        # Also extract methods inside classes as separate chunks
        if isinstance(node, ast.ClassDef):
            for child_node in node.body:
                if isinstance(child_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not hasattr(child_node, "lineno") or not hasattr(child_node, "end_lineno"):
                        continue
                    m_start = child_node.lineno
                    m_end = child_node.end_lineno
                    m_segment = _get_source_segment_safe(source_lines, child_node)
                    if not m_segment:
                        m_segment = "\n".join(source_lines[m_start - 1 : m_end])
                    m_checksum = hashlib.md5(m_segment.encode("utf-8")).hexdigest()
                    chunks.append({
                        "source_path": str(file_path),
                        "content": m_segment.strip(),
                        "language": "python",
                        "symbol_name": f"{node.name}.{child_node.name}",
                        "chunk_type": "method",
                        "line_start": m_start,
                        "line_end": m_end,
                        "checksum": m_checksum,
                    })

        chunks.append({
            "source_path": str(file_path),
            "content": segment.strip(),
            "language": "python",
            "symbol_name": symbol_name,
            "chunk_type": chunk_type,
            "line_start": line_start,
            "line_end": line_end,
            "checksum": checksum,
        })

    # Extract top-level assignments (module-level constants, config objects)
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            if not hasattr(node, "lineno") or not hasattr(node, "end_lineno"):
                continue
            line_start = node.lineno
            line_end = node.end_lineno

            # Skip if already covered by a function/class range
            if any(s <= line_start and (line_end is not None and line_end <= e) for s, e in seen_ranges):
                continue

            # Only extract simple name assignments (e.g. ``SOME_CONST = ...``)
            targets = [t for t in node.targets if isinstance(t, ast.Name)]
            if not targets:
                continue

            segment = _get_source_segment_safe(source_lines, node)
            if not segment:
                segment = "\n".join(source_lines[line_start - 1 : line_end])

            if len(segment) > MAX_CHUNK_CHARS:
                segment = segment[:MAX_CHUNK_CHARS]

            if line_end is not None:
                seen_ranges.add((line_start, line_end))
            checksum = hashlib.md5(segment.encode("utf-8")).hexdigest()

            symbols = [t.id for t in targets if hasattr(t, "id")]
            for sym in symbols:
                chunks.append({
                    "source_path": str(file_path),
                    "content": segment.strip(),
                    "language": "python",
                    "symbol_name": sym,
                    "chunk_type": "assignment",
                    "line_start": line_start,
                    "line_end": line_end,
                    "checksum": checksum,
                })

    # If no chunks were extracted, fall back to whole-file chunk
    if not chunks:
        checksum = hashlib.md5(source_text.encode("utf-8")).hexdigest()
        chunks.append({
            "source_path": str(file_path),
            "content": source_text.strip()[:MAX_CHUNK_CHARS],
            "language": "python",
            "symbol_name": file_path.stem,
            "chunk_type": "module",
            "line_start": 1,
            "line_end": len(source_lines),
            "checksum": checksum,
        })

    return chunks


# ─── TypeScript / JavaScript Regex Chunker ────────────────────────────────────

# Pattern: ``export (default)? (function|class|const|interface|type) Name``
_TS_EXPORT_PATTERN = re.compile(
    r"^export\s+(default\s+)?"
    r"(?:(?:async\s+)?function\s+\*?\s*(?P<fn_name>\w+))"
    r"|(?:class\s+(?P<class_name>\w+))"
    r"|(?:interface\s+(?P<iface_name>\w+))"
    r"|(?:type\s+(?P<type_name>\w+))\s*="
    r"|(?:const\s+(?P<const_name>\w+)\s*[:=])",
    re.MULTILINE,
)

# Pattern to find closing brace matching a detected export.
# We track brace depth to determine the exact chunk boundary.
_BRACE_DEPTH_RE = re.compile(r"[{}]")


def _extract_until_balanced(lines: List[str], start_idx: int) -> int:
    """Given a starting line index, find the line where braces are balanced.

    Returns the end line index (inclusive).  If braces never balance (unlikely
    in valid code), returns ``len(lines) - 1``.
    """
    depth = 0
    for i in range(start_idx, len(lines)):
        for ch in lines[i]:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
        if depth <= 0 and i > start_idx:
            # Check if this line actually starts a brace block
            # If depth reached 0 and we've consumed content, we're done
            if depth == 0:
                return i
    return len(lines) - 1


def chunk_typescript_file(file_path: Path) -> List[Dict[str, Any]]:
    """Chunk a TypeScript/JavaScript file using regex-based extraction.

    Identifies top-level exports (function, class, const, interface, type)
    and extracts each as a separate chunk with balanced brace detection.

    Falls back to a whole-file chunk if no exports are found.
    """
    source_text = file_path.read_text(encoding="utf-8", errors="replace")
    source_lines = source_text.split("\n")

    chunks: List[Dict[str, Any]] = []
    seen_ranges: Set[Tuple[int, int]] = set()

    for match in _TS_EXPORT_PATTERN.finditer(source_text):
        line_start = source_text[: match.start()].count("\n") + 1  # 1-based
        groups = match.groupdict(default="")

        # Determine symbol name from whichever group matched
        symbol_name = (
            groups.get("fn_name")
            or groups.get("class_name")
            or groups.get("iface_name")
            or groups.get("type_name")
            or groups.get("const_name")
            or ""
        )
        if not symbol_name:
            continue

        # Determine chunk type
        if groups.get("fn_name"):
            chunk_type = "function"
        elif groups.get("class_name"):
            chunk_type = "class"
        elif groups.get("iface_name"):
            chunk_type = "interface"
        elif groups.get("type_name"):
            chunk_type = "type"
        elif groups.get("const_name"):
            chunk_type = "assignment"
        else:
            chunk_type = "module"

        # Find end line by brace balancing
        content_lines = source_lines[line_start - 1 :]
        end_line = _extract_until_balanced(content_lines, 0)
        line_end = line_start + end_line

        if end_line == 0 and chunk_type in ("assignment",):
            # Single-line const declaration without brace block
            line_end = line_start

        # Deduplicate
        if any(s <= line_start and line_end <= e for s, e in seen_ranges):
            continue
        seen_ranges.add((line_start, line_end))

        segment = "\n".join(source_lines[line_start - 1 : line_end]).strip()
        if not segment:
            continue

        checksum = hashlib.md5(segment.encode("utf-8")).hexdigest()
        chunks.append({
            "source_path": str(file_path),
            "content": segment,
            "language": "typescript",
            "symbol_name": symbol_name,
            "chunk_type": chunk_type,
            "line_start": line_start,
            "line_end": line_end,
            "checksum": checksum,
        })

    # Also extract non-exported top-level function declarations and classes
    # (for files that don't use ``export``)
    _NON_EXPORT_TOP_LEVEL = re.compile(
        r"^(?:(?:async\s+)?function\s+(?P<fn_name>\w+))"
        r"|(?:class\s+(?P<class_name>\w+))",
        re.MULTILINE,
    )
    for match in _NON_EXPORT_TOP_LEVEL.finditer(source_text):
        line_start = source_text[: match.start()].count("\n") + 1
        groups = match.groupdict(default="")
        symbol_name = groups.get("fn_name") or groups.get("class_name") or ""
        if not symbol_name:
            continue

        # Skip if this line is already inside an export chunk's range
        if any(s <= line_start <= e for s, e in seen_ranges):
            continue

        chunk_type = "function" if groups.get("fn_name") else "class"
        content_lines = source_lines[line_start - 1 :]
        end_line = _extract_until_balanced(content_lines, 0)
        line_end = line_start + end_line

        if any(s <= line_start and line_end <= e for s, e in seen_ranges):
            continue
        seen_ranges.add((line_start, line_end))

        segment = "\n".join(source_lines[line_start - 1 : line_end]).strip()
        if not segment:
            continue

        checksum = hashlib.md5(segment.encode("utf-8")).hexdigest()
        chunks.append({
            "source_path": str(file_path),
            "content": segment,
            "language": "typescript",
            "symbol_name": symbol_name,
            "chunk_type": chunk_type,
            "line_start": line_start,
            "line_end": line_end,
            "checksum": checksum,
        })

    # If no chunks were extracted, fall back to whole-file chunk
    if not chunks:
        checksum = hashlib.md5(source_text.encode("utf-8")).hexdigest()
        chunks.append({
            "source_path": str(file_path),
            "content": source_text.strip()[:MAX_CHUNK_CHARS],
            "language": "typescript",
            "symbol_name": file_path.stem,
            "chunk_type": "module",
            "line_start": 1,
            "line_end": len(source_lines),
            "checksum": checksum,
        })

    return chunks


# ─── Config-File Chunker ──────────────────────────────────────────────────────


def chunk_config_file(file_path: Path) -> List[Dict[str, Any]]:
    """Chunk a configuration file as a single whole-file chunk.

    Config files (``.toml``, ``.json``, ``.yaml``, ``.env.example``) don't
    benefit from structural chunking — the entire file is usually small and
    semantically atomic.
    """
    source_text = file_path.read_text(encoding="utf-8", errors="replace")
    if not source_text.strip():
        return []

    checksum = hashlib.md5(source_text.encode("utf-8")).hexdigest()
    source_lines = source_text.split("\n")

    return [{
        "source_path": str(file_path),
        "content": source_text.strip()[:MAX_CHUNK_CHARS],
        "language": "config",
        "symbol_name": file_path.stem,
        "chunk_type": "module",
        "line_start": 1,
        "line_end": len(source_lines),
        "checksum": checksum,
    }]


# ─── Language Dispatcher ──────────────────────────────────────────────────────


def chunk_file(file_path: Path, language: Optional[str] = None) -> List[Dict[str, Any]]:
    """Chunk a source file based on its language.

    Parameters
    ----------
    file_path:
        Path to the source file.
    language:
        Explicit language override.  If not provided, detected from file
        extension via :data:`EXTENSION_LANGUAGE_MAP`.

    Returns
    -------
    List of chunk dicts.  Empty list if the language is unsupported.
    """
    if language is None:
        ext = file_path.suffix.lower()
        language = EXTENSION_LANGUAGE_MAP.get(ext, "config")

    lang_lower = language.lower()

    if lang_lower == "python":
        return chunk_python_file(file_path)
    elif lang_lower in ("typescript", "javascript"):
        return chunk_typescript_file(file_path)
    elif lang_lower == "config":
        return chunk_config_file(file_path)
    else:
        # Unknown language — treat as config (whole-file)
        logger.warning("Unknown language '%s' for %s — treating as config", language, file_path)
        return chunk_config_file(file_path)


# ─── CodeVectorStore ──────────────────────────────────────────────────────────


class CodeVectorStore:
    """sqlite-vec powered vector store for source code chunks.

    Uses a lazy singleton pattern — call ``CodeVectorStore.get_instance()``
    to obtain the shared instance.
    """

    _instance: Optional["CodeVectorStore"] = None
    _lock = threading.Lock()
    # The vec table this store owns — named once, because two readers need it: `init_db` creates it and
    # `_declared_width` asks the index what width it was CREATED at (see the width guard below).
    VEC_TABLE = "vec_code"

    def __init__(
        self,
        db_path: str,
        embedding: "EmbeddingService",
        batch_size: int = DEFAULT_BATCH_SIZE,
    ):
        self.db_path = db_path
        # THE EMBEDDING SERVICE ARRIVES AS ONE ANSWER (see the constants block): the three values
        # below are read OFF it, and an UNRESOLVED service leaves them empty so every use refuses
        # loudly through `_refuse_unconfigured` rather than dialling a guessed address or a 768-wide
        # default.
        self.embedding = embedding
        self.ollama_base = (embedding.address or "").rstrip("/")
        self.embedding_model = embedding.model or ""
        self.embedding_dims = embedding.dims or 0
        self.batch_size = batch_size
        # The model's own input budget — the same lookup the doc store uses (see its note).
        self.max_embed_chars = max_embed_chars_for(embedding.model)
        self._db: Optional[sqlite3.Connection] = None
        self._initialized = False

    def _refuse_unconfigured(self) -> bool:
        """Refuse to work when the embedding service resolved to nothing — loudly, one wording.

        The vec table's WIDTH is the model's width, so an install with no embedding model has no table
        to create and no call to make: the store reports the gap (``EmbeddingService.report``, the
        same line `/rag/status` shows) instead of guessing.
        """
        if self.embedding.resolved:
            return False
        logger.error("CodeVectorStore unusable — %s", self.embedding.report())
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
            logger.warning("CodeVectorStore: could not read %s's declared width: %s", self.VEC_TABLE, exc)
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
            "CodeVectorStore unusable — %s", width_mismatch_report(declared, self.embedding)
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
    ) -> "CodeVectorStore":
        """Return the shared singleton instance.

        On first call the instance is created with the provided parameters;
        subsequent calls ignore parameters (singleton is already configured).

        **First-wins is safe while callers agree on the embedding service, and they do**: every caller
        resolves it from the SAME `embeddings` capability. What a caller may NOT do is build this store
        before the capability is configured and expect it to pick the model up later — the service is
        captured here, so a changed capability needs `reset_instance()`. **The write path does exactly
        that**: `capabilities.replace_chain` drops both stores when an `embeddings` chain changes
        (`close=False`, so a mid-flight ingest is not broken), which is what makes a saved model reach
        the running process.
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
        if self._db is None:
            db_dir = Path(self.db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)

            self._db = sqlite3.connect(self.db_path)
            self._db.row_factory = sqlite3.Row
            self._db.enable_load_extension(True)
            sqlite_vec.load(self._db)
            self._db.enable_load_extension(False)
            self._db.execute("PRAGMA journal_mode=WAL")
        return self._db

    def init_db(self) -> None:
        """Create tables if they don't exist.

        Creates:
        - ``code_chunks`` — metadata / content store
        - ``vec_code`` — sqlite-vec virtual table for ANN search
        """
        if self._refuse():
            return  # the width IS the model's; with no model there is no table to declare
        db = self._get_connection()

        # Metadata table
        db.execute("""
            CREATE TABLE IF NOT EXISTS code_chunks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                source_path TEXT    NOT NULL,
                content     TEXT    NOT NULL,
                language    TEXT    NOT NULL DEFAULT '',
                symbol_name TEXT    NOT NULL DEFAULT '',
                chunk_type  TEXT    NOT NULL DEFAULT '',
                line_start  INTEGER NOT NULL DEFAULT 0,
                line_end    INTEGER NOT NULL DEFAULT 0,
                checksum    TEXT    NOT NULL,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
                updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)

        # Index on source_path for fast listing / staleness checks
        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_code_chunks_source_path
            ON code_chunks(source_path)
        """)

        # Index on language for filtered searches
        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_code_chunks_language
            ON code_chunks(language)
        """)

        # Index on checksum for incremental detection
        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_code_chunks_checksum
            ON code_chunks(checksum)
        """)

        # sqlite-vec virtual table for embeddings
        db.execute(f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS {self.VEC_TABLE} USING vec0(
                embedding float[{self.embedding_dims}] distance_metric=cosine
            )
        """)

        self._initialized = True
        logger.info(
            "CodeVectorStore initialized: path=%s, dims=%d, model=%s",
            self.db_path, self.embedding_dims, self.embedding_model,
        )

    # ── Embedding ──────────────────────────────────────────────────────────

    def _call_ollama_embed(self, text: str) -> Optional[List[float]]:
        """Call the Ollama embeddings API for a single text.

        Truncates text to ``MAX_EMBED_CHARS`` (~1900 chars) to stay within the
        model's token limit (2048 tokens for ``nomic-embed-text``).  Longer
        prompts cause Ollama to return HTTP 500.

        Returns ``None`` on failure (logged, not raised).
        """
        if self._refuse():
            return None
        if len(text) > self.max_embed_chars:
            logger.error(
                "code chunk of %d chars exceeds the '%s' budget of %d — refusing to embed part of it",
                len(text),
                self.embedding_model,
                self.max_embed_chars,
            )
            return None

        # The deadline scales with the text and a transport failure is retried ONCE — the same rule
        # the doc store follows, for the same reason (a flat 30 s lost the heaviest chunks).
        deadline = max(30.0, len(text) * 0.025)

        for attempt in (1, 2):
            try:
                with httpx.Client(timeout=deadline) as client:
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
            except (httpx.TimeoutException, httpx.RequestError) as exc:
                if attempt == 1:
                    logger.warning(
                        "code embedding attempt 1 failed after %.0fs on %d chars (%s) — retrying",
                        deadline,
                        len(text),
                        type(exc).__name__,
                    )
                    continue
                logger.error(
                    "Ollama embedding request failed twice (%.0fs deadline, %d chars): %s",
                    deadline,
                    len(text),
                    exc,
                )
                return None
            except Exception as exc:
                logger.error("Unexpected error in Ollama embedding: %s", exc)
                return None
        return None

    def embed_query(self, text: str) -> Optional[List[float]]:
        """Embed a single query string.

        Returns a list of floats (the embedding vector) or ``None`` on failure.
        """
        return self._call_ollama_embed(text)

    def embed_chunks(self, chunks: List[str]) -> List[Optional[List[float]]]:
        """Embed a list of chunk texts in batches.

        Returns a parallel list where each element is either an embedding
        vector or ``None`` if that chunk's embedding failed.
        """
        results: List[Optional[List[float]]] = []
        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i : i + self.batch_size]
            for text in batch:
                emb = self._call_ollama_embed(text)
                results.append(emb)
        return results

    # ── Indexing ───────────────────────────────────────────────────────────

    def add_document(self, file_path: str, language: Optional[str] = None) -> int:
        """Chunk, embed, and index a source code file.

        Parameters
        ----------
        file_path:
            The file path of the source code (used as provenance).
        language:
            Explicit language override.  If not provided, detected from
            file extension.

        Returns
        -------
        Number of chunks indexed.  0 if embedding fails entirely or the
        file is empty.
        """
        if not self._initialized:
            self.init_db()

        path = Path(file_path)
        if not path.exists():
            logger.warning("File not found: %s", file_path)
            return 0

        if path.stat().st_size == 0:
            logger.info("Skipping empty file: %s", file_path)
            return 0

        chunks = chunk_file(path, language)
        if not chunks:
            return 0

        # Remove existing entries for this source path before re-indexing
        self._remove_document(file_path)

        texts = [c["content"] for c in chunks]
        embeddings = self.embed_chunks(texts)

        db = self._get_connection()
        inserted = 0

        for chunk, emb in zip(chunks, embeddings):
            if emb is None:
                logger.warning(
                    "Skipping chunk (embedding failed): %s symbol=%s",
                    file_path, chunk.get("symbol_name", ""),
                )
                continue

            # Insert metadata row
            cursor = db.execute(
                """
                INSERT INTO code_chunks
                    (source_path, content, language, symbol_name, chunk_type,
                     line_start, line_end, checksum)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk["source_path"],
                    chunk["content"],
                    chunk.get("language", ""),
                    chunk.get("symbol_name", ""),
                    chunk.get("chunk_type", ""),
                    chunk.get("line_start", 0),
                    chunk.get("line_end", 0),
                    chunk["checksum"],
                ),
            )
            chunk_id = cursor.lastrowid

            # Insert embedding into vec_code virtual table
            from sqlite_vec import serialize_float32

            db.execute(
                "INSERT INTO vec_code (rowid, embedding) VALUES (?, ?)",
                (chunk_id, serialize_float32(emb)),
            )
            inserted += 1

        db.commit()
        logger.info(
            "Indexed %d/%d chunks from %s",
            inserted, len(chunks), file_path,
        )
        return inserted

    def _remove_document(self, source_path: str) -> int:
        """Remove all chunks for a given source path.

        Returns the number of chunks removed.
        """
        if not self._initialized:
            self.init_db()

        db = self._get_connection()

        # Find chunk IDs for this source path
        cursor = db.execute(
            "SELECT id FROM code_chunks WHERE source_path = ?",
            (source_path,),
        )
        ids = [row["id"] for row in cursor.fetchall()]

        if not ids:
            return 0

        # Delete from vec_code (virtual table)
        for chunk_id in ids:
            try:
                db.execute("DELETE FROM vec_code WHERE rowid = ?", (chunk_id,))
            except Exception as exc:
                logger.warning(
                    "Failed to delete vec_code rowid=%d: %s", chunk_id, exc,
                )

        # Delete from metadata table
        db.execute(
            "DELETE FROM code_chunks WHERE source_path = ?",
            (source_path,),
        )
        db.commit()
        return len(ids)

    def remove_stale_documents(self, existing_paths: Set[str]) -> int:
        """Remove vector entries for source files that no longer exist.

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
        cursor = db.execute("SELECT DISTINCT source_path FROM code_chunks")
        indexed_paths = {row["source_path"] for row in cursor.fetchall()}

        stale = indexed_paths - existing_paths
        total_removed = 0
        for path in stale:
            removed = self._remove_document(path)
            total_removed += removed
            if removed:
                logger.info("Removed stale index for %s (%d chunks)", path, removed)

        return total_removed

    def get_stats(self) -> Dict[str, Any]:
        """Return count of indexed chunks and files.

        Returns a dict with keys: ``chunk_count``, ``file_count``,
        ``languages`` (dict of language → count).
        """
        if not self._initialized:
            self.init_db()

        db = self._get_connection()

        cursor = db.execute("SELECT COUNT(*) AS cnt FROM code_chunks")
        chunk_count = cursor.fetchone()["cnt"]

        cursor = db.execute("SELECT COUNT(DISTINCT source_path) AS cnt FROM code_chunks")
        file_count = cursor.fetchone()["cnt"]

        cursor = db.execute(
            "SELECT language, COUNT(*) AS cnt FROM code_chunks GROUP BY language",
        )
        languages = {row["language"]: row["cnt"] for row in cursor.fetchall()}

        return {
            "chunk_count": chunk_count,
            "file_count": file_count,
            "languages": languages,
        }

    # ── Search ─────────────────────────────────────────────────────────────

    def semantic_search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        min_score: float = DEFAULT_MIN_SCORE,
        language_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Perform ANN vector search over the code index.

        Parameters
        ----------
        query:
            Natural language query describing what code to find.
        top_k:
            Maximum number of results (clamped to ``MAX_TOP_K``).
        min_score:
            Minimum similarity score threshold (1.0 = perfect match,
            0.0 = orthogonal).  Results below this threshold are excluded.
        language_filter:
            Optional language string to restrict results (e.g. ``"python"``,
            ``"typescript"``).

        Returns
        -------
        List of result dicts with keys: ``file_path``, ``language``,
        ``symbol_name``, ``chunk_type``, ``content``, ``similarity``,
        ``line_start``, ``line_end``.
        """
        if not self._initialized:
            self.init_db()

        # First embed the query
        embedding = self.embed_query(query)
        if embedding is None:
            logger.error("semantic_search: query embedding failed")
            return []

        return self.search(
            embedding=embedding,
            top_k=top_k,
            min_score=min_score,
            language_filter=language_filter,
        )

    def search(
        self,
        embedding: List[float],
        top_k: int = DEFAULT_TOP_K,
        min_score: float = DEFAULT_MIN_SCORE,
        language_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Perform ANN vector search with a pre-computed embedding.

        Parameters
        ----------
        embedding:
            The query embedding vector.
        top_k:
            Maximum number of results (clamped to ``MAX_TOP_K``).
        min_score:
            Minimum similarity score threshold.
        language_filter:
            Optional language string to restrict results.

        Returns
        -------
        List of result dicts with keys: ``file_path``, ``language``,
        ``symbol_name``, ``chunk_type``, ``content``, ``similarity``,
        ``line_start``, ``line_end``.
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
                FROM vec_code
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
            SELECT id, source_path, content, language, symbol_name, chunk_type,
                   line_start, line_end
            FROM code_chunks
            WHERE id IN ({placeholders})
        """

        # Apply language filter if provided
        params: List[Any] = ids
        if language_filter:
            query += " AND language = ?"
            params.append(language_filter)

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
                "file_path": row["source_path"],
                "language": row["language"] or "",
                "symbol_name": row["symbol_name"] or "",
                "chunk_type": row["chunk_type"] or "",
                "content": row["content"],
                "similarity": round(similarity, 4),
                "line_start": row["line_start"],
                "line_end": row["line_end"],
            })

        # Sort by similarity descending
        results.sort(key=lambda r: r["similarity"], reverse=True)

        return results
