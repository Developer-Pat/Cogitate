"""
Documentation Reader Tool Handler.

Sandboxed markdown file reader for the System Guide mode.
Reads documentation files from whitelisted paths with
path traversal protection.

Supports ``semantic_search`` operation powered by ``sqlite-vec``
for finding documentation by meaning rather than keyword match,
and ``code_search`` for finding source code by meaning.
"""

from __future__ import annotations

import fnmatch
import logging
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, cast

from app.core.config import Paths

if TYPE_CHECKING:
    # The annotation only: the import is deferred inside `_embedding_service` (this module is
    # imported early by the tool registry, and `app.domain.providers.embeddings` pulls the ORM).
    from app.domain.providers.embeddings import EmbeddingService


logger = logging.getLogger(__name__)

# Project root — resolve relative to this file's location.
# __file__ = backend/app/domain/tools/builtin/doc_reader.py
# 5 levels up = project root
_PROJECT_ROOT = Paths.root

# Whitelisted base directories (relative to project root)
#
# ⚠️ COUPLING WARNING ⚠️
# This list controls which directories the doc-reader tool can read from via
# its ``read`` / ``search`` operations.  However, ``semantic_search`` queries
# the vector index, which is built only from the directories listed in
# ``rag/service.py:INGESTION_DIRS``.
#
# If you add a directory here but NOT to ``INGESTION_DIRS``, the RAG system will be
# able to read files from it (via ``read`` / ``search``) but NOT find them
# via ``semantic_search``.  Conversely, if you add a directory to
# ``INGESTION_DIRS`` but NOT here, the RAG system will find it via semantic search
# but may fail to read the actual file.
#
# When modifying this list, also consider updating ``INGESTION_DIRS`` in
# ``backend/app/domain/rag/service.py`` to keep the two in sync.
ALLOWED_BASE_DIRS: List[str] = [
    "wiki/entities",
    "wiki/dev-notes",
    "plans",
    "exports",
    "DEVME.md",
    "README.md",
    "backend/app",
    "frontend/src",
]

# Denied path patterns (even within allowed dirs)
DENIED_PATTERNS: List[str] = [
    ".env",
    ".venv",
    "node_modules",
    "__pycache__",
    "*.db",
    "*.sqlite",
    "*.log",
]

# Deny patterns as compiled regex for efficiency
_DENIED_REGEX: re.Pattern = re.compile(
    "|".join(fnmatch.translate(p) for p in DENIED_PATTERNS),
    re.IGNORECASE,
)

# File extensions allowed for reading
ALLOWED_EXTENSIONS: Set[str] = {".md", ".txt", ".rst", ".json", ".yaml", ".yml", ".toml", ".py", ".ts", ".tsx"}


class DocReaderTool:
    """
    Documentation Reader tool for reading project documentation.

    Tags:
        - op:read
        - purpose:development
        - source:local-file
        - safe
        - text

    Operations:
        - read: Read a documentation file by path
        - search: Search for docs by filename or content
        - list: List available docs in a directory
        - semantic_search: Find docs by meaning (vector similarity search
          powered by sqlite-vec). Requires ``query`` text; optionally
          accepts ``top_k``, ``min_score``, and ``source_filter``.
        - code_search: Search source code files by meaning (vector similarity
          search powered by sqlite-vec). Requires ``query`` text; optionally
          accepts ``language`` filter and ``max_results``.
    """

    name = "Documentation Reader"
    slug = "doc-reader"
    capability = "doc-lookup"
    description = (
        "Read markdown documentation files from the project. "
        "Supports THREE search modes: (1) keyword 'search' — finds files by "
        "filename or content match, (2) 'semantic_search' — finds "
        "relevant document sections by meaning using vector similarity, "
        "even when exact keywords don't match, and (3) 'code_search' — finds "
        "relevant source code by meaning using vector similarity. "
        "Use semantic_search when the user asks a conceptual question "
        "about the project (e.g., 'how does tool integration work?') — it "
        "returns results ranked by relevance with similarity scores. "
        "Use code_search when the user asks how something is implemented "
        "in code (e.g., 'how is tool execution handled?') — it returns "
        "relevant source code chunks. Use keyword search when the user "
        "wants to find a specific file or known term."
    )
    tags = [
        "op:read",
        "purpose:development",
        "purpose:documentation",
        "source:local-file",
        "safe",
        "text",
    ]
    icon = "book-open"
    color = "#4A90D9"  # Blue

    config_schema = {
        "type": "object",
        "properties": {
            "max_file_size": {
                "type": "integer",
                "default": 102400,
                "minimum": 1024,
                "maximum": 1048576,
                "description": "Maximum file size in bytes that can be read (default: 100KB)",
            },
            "max_search_results": {
                "type": "integer",
                "default": 20,
                "minimum": 1,
                "maximum": 100,
                "description": "Maximum number of search results to return",
            },
        },
    }

    arguments_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative path to the documentation file (e.g., 'docs/README.md') or directory for list operation",
            },
            "search": {
                "type": "string",
                "description": "Search term to find relevant docs by filename or content (requires search operation)",
            },
            "operation": {
                "type": "string",
                "enum": ["read", "search", "list", "semantic_search", "code_search"],
                "description": "Operation to perform. Defaults to 'read' if path points to a file, 'list' if path points to a directory.",
            },
            "query": {
                "type": "string",
                "description": "Natural language query for semantic search or code search (requires semantic_search or code_search operation)",
            },
            "top_k": {
                "type": "integer",
                "default": 10,
                "minimum": 1,
                "maximum": 20,
                "description": "Maximum number of semantic search or code search results to return",
            },
            "min_score": {
                "type": "number",
                "default": 0.0,
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Minimum similarity score threshold (0.0-1.0). Higher values return only closer matches.",
            },
            "source_filter": {
                "type": "string",
                "description": "Optional source path prefix filter (e.g. 'docs/atlas/%' to restrict to atlas docs)",
            },
            "language": {
                "type": "string",
                "description": "Optional language filter for code_search (e.g. 'python', 'typescript'). Only returns results from matching language.",
            },
            "max_results": {
                "type": "integer",
                "default": 5,
                "minimum": 1,
                "maximum": 20,
                "description": "Maximum number of code_search results to return",
            },
        },
        "required": [],
    }

    def __init__(self):
        self._project_root = _PROJECT_ROOT

    async def _embedding_service(self) -> "EmbeddingService":
        """The install's ONE embedding answer — *(address, model, dims)* from the `embeddings` capability.

        This tool is a TOOL HANDLER: the runner calls ``execute(config, **arguments)`` and hands it no
        database session, so one is opened here for the length of the resolution, read-only. What the
        tool may NOT do is carry an answer of its own — which is exactly what it did: it read
        ``embedding_provider`` / ``embedding_model`` / ``embedding_dimensions`` off a
        ``SystemManagerConfig`` it never had (`self._system_manager_config` was assigned ``None`` and
        never anything else, so every ``getattr`` fell through to its literal), and ``_code_search``
        OVERRODE even those with ``nomic-embed-text``/``768`` whenever the (nonexistent) provider was
        not ``ollama``. Four literals in one file, one of them overruling configuration that could not
        exist (the service-literals arc's model half, 2026-10-10).
        """
        from app.core.database import AsyncSessionLocal
        from app.domain.providers.embeddings import resolve_embedding_service

        async with AsyncSessionLocal() as session:
            return await resolve_embedding_service(session)

    async def execute(self, config: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Execute a documentation reader operation.

        Args:
            config: Tool configuration
            **kwargs: Tool arguments (path, search, operation, query, top_k,
                       min_score, source_filter, language, max_results)

        Returns:
            Dictionary with success status and result
        """
        path = kwargs.get("path", "").strip()
        search_term = kwargs.get("search", "").strip()
        query = kwargs.get("query", "").strip()
        operation = kwargs.get("operation", "").strip().lower() or "read"
        max_file_size = config.get("max_file_size", 102400)
        max_search_results = config.get("max_search_results", 20)

        # Auto-detect operation: if path is a directory, switch to list
        if path:
            resolved = self._resolve_path(path)
            if resolved and resolved.is_dir() and operation == "read":
                operation = "list"

        try:
            if operation == "read":
                if not path:
                    return {
                        "success": False,
                        "error": "No path provided. Please specify a file or directory path.",
                        "error_type": "ValidationError",
                    }
                return await self._read(path, max_file_size)
            elif operation == "search":
                if not path:
                    return {
                        "success": False,
                        "error": "No path provided. Please specify a file or directory path.",
                        "error_type": "ValidationError",
                    }
                return await self._search(path, search_term, max_search_results)
            elif operation == "list":
                if not path:
                    return {
                        "success": False,
                        "error": "No path provided. Please specify a file or directory path.",
                        "error_type": "ValidationError",
                    }
                return await self._list(path)
            elif operation == "semantic_search":
                top_k = kwargs.get("top_k", 10)
                min_score = kwargs.get("min_score", 0.0)
                source_filter = kwargs.get("source_filter")
                return await self._semantic_search(
                    query=query,
                    top_k=top_k,
                    min_score=min_score,
                    source_filter=source_filter,
                )
            elif operation == "code_search":
                language = kwargs.get("language")
                max_results = kwargs.get("max_results", 5)
                return await self._code_search(
                    query=query,
                    language=language,
                    max_results=max_results,
                )
            else:
                return {
                    "success": False,
                    "error": f"Unknown operation: {operation}",
                    "error_type": "ValidationError",
                }
        except Exception as e:
            logger.error(f"Doc reader tool error: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "error_type": "InternalError",
            }

    def _resolve_path(self, path: str) -> Optional[Path]:
        """Resolve a relative path to an absolute path, validating against whitelist."""
        # Normalize path — strip leading slash, prevent traversal
        clean_path = path.lstrip("/")
        resolved = (self._project_root / clean_path).resolve()

        # Prevent path traversal outside project root
        try:
            resolved.relative_to(self._project_root)
        except ValueError:
            logger.warning(f"Path traversal blocked: {path} -> {resolved}")
            return None

        return cast(Optional[Path], resolved)

    def _validate_path(self, resolved: Path) -> Optional[str]:
        """
        Validate a resolved path against the whitelist and deny list.

        Returns:
            Error message string if invalid, None if valid.
        """
        # Check if path is within an allowed base directory
        allowed = False
        rel_path = resolved.relative_to(self._project_root)
        rel_str = str(rel_path)

        # Allow the project root itself (".") — useful for listing top-level
        # documentation directories.  Individual child entries are validated
        # independently by the caller (e.g. ``_list`` validates each entry
        # at line 572), so security is maintained.
        if rel_str == ".":
            allowed = True

        if not allowed:
            for allowed_dir in ALLOWED_BASE_DIRS:
                if rel_str == allowed_dir or rel_str.startswith(allowed_dir + "/") or rel_str.startswith(allowed_dir + os.sep):
                    allowed = True
                    break

        if not allowed:
            return (
                f"Access denied: '{rel_str}' is not in an allowed documentation directory. "
                f"Allowed locations: {', '.join(ALLOWED_BASE_DIRS)}"
            )

        # Check denied patterns
        if _DENIED_REGEX.search(rel_str):
            return f"Access denied: '{rel_str}' matches a denied pattern."

        return None

    async def _read(self, path: str, max_file_size: int) -> Dict[str, Any]:
        """Read a documentation file."""
        resolved = self._resolve_path(path)
        if resolved is None:
            return {
                "success": False,
                "error": f"Invalid path: '{path}'. Path must be within the project directory.",
                "error_type": "PathError",
            }

        # Validate path
        error = self._validate_path(resolved)
        if error:
            return {
                "success": False,
                "error": error,
                "error_type": "SecurityError",
            }

        if not resolved.exists():
            return {
                "success": False,
                "error": f"File not found: '{path}'",
                "error_type": "NotFoundError",
            }

        if resolved.is_dir():
            return {
                "success": False,
                "error": f"'{path}' is a directory. Use the 'list' operation to see contents.",
                "error_type": "ValidationError",
            }

        # Check file extension
        ext = resolved.suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            return {
                "success": False,
                "error": f"Unsupported file type: '{ext}'. Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
                "error_type": "ValidationError",
            }

        # Check file size
        file_size = resolved.stat().st_size
        if file_size > max_file_size:
            return {
                "success": False,
                "error": f"File too large: {file_size} bytes (max: {max_file_size} bytes). "
                         f"Consider searching for specific content instead.",
                "error_type": "SizeError",
                "file_size": file_size,
                "max_file_size": max_file_size,
            }

        try:
            content = resolved.read_text(encoding="utf-8")
            rel_path = str(resolved.relative_to(self._project_root))
            line_count = content.count("\n") + 1

            return {
                "success": True,
                "operation": "read",
                "path": rel_path,
                "file_name": resolved.name,
                "file_size": file_size,
                "content": content,
                "line_count": line_count,
                "summary": f"Read {rel_path} ({file_size} bytes, {line_count} lines)",
            }
        except Exception as e:
            logger.error(f"Failed to read file '{path}': {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to read file: {str(e)}",
                "error_type": "ReadError",
            }

    async def _search(self, path: str, search_term: str, max_results: int) -> Dict[str, Any]:
        """Search for documentation files by filename or content."""
        resolved = self._resolve_path(path)
        if resolved is None:
            return {
                "success": False,
                "error": f"Invalid path: '{path}'.",
                "error_type": "PathError",
            }

        if not resolved.exists():
            return {
                "success": False,
                "error": f"Path not found: '{path}'",
                "error_type": "NotFoundError",
            }

        if not resolved.is_dir():
            # Search in a single file
            error = self._validate_path(resolved)
            if error:
                return {
                    "success": False,
                    "error": error,
                    "error_type": "SecurityError",
                }

            ext = resolved.suffix.lower()
            if ext not in ALLOWED_EXTENSIONS:
                return {
                    "success": False,
                    "error": f"Cannot search in file type: '{ext}'.",
                    "error_type": "ValidationError",
                }

            try:
                content = resolved.read_text(encoding="utf-8")
                lines = content.split("\n")
                matching_lines = [
                    {"line_number": i + 1, "content": line.strip()}
                    for i, line in enumerate(lines)
                    if search_term.lower() in line.lower()
                ][:max_results]

                rel_path = str(resolved.relative_to(self._project_root))
                match_count = len(matching_lines)
                return {
                    "success": True,
                    "operation": "search",
                    "path": rel_path,
                    "search_term": search_term,
                    "match_count": match_count,
                    "matches": matching_lines,
                    "summary": f"Searched {rel_path} for '{search_term}' — found {match_count} matches",
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Search failed: {str(e)}",
                    "error_type": "SearchError",
                }

        # Validate directory is allowed
        error = self._validate_path(resolved)
        if error:
            return {
                "success": False,
                "error": error,
                "error_type": "SecurityError",
            }

        # Search in directory for matching files
        results: List[Dict[str, Any]] = []
        for file_path in resolved.rglob("*"):
            if not file_path.is_file():
                continue
            ext = file_path.suffix.lower()
            if ext not in ALLOWED_EXTENSIONS:
                continue

            # Validate each file against whitelist
            try:
                file_rel = file_path.relative_to(self._project_root)
                file_error = self._validate_path(file_path)
                if file_error:
                    continue
            except ValueError:
                continue

            # Check filename match
            rel_str = str(file_rel)
            if search_term.lower() in file_path.stem.lower():
                results.append({
                    "path": rel_str,
                    "file_name": file_path.name,
                    "match_type": "filename",
                })
                if len(results) >= max_results:
                    break
                continue

            # Check content match (limit to first few KB for performance)
            try:
                if file_path.stat().st_size > 51200:  # Skip large files for content search
                    continue
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                if search_term.lower() in content.lower():
                    # Find context snippet
                    lines = content.split("\n")
                    snippet_lines = [
                        i + 1 for i, line in enumerate(lines)
                        if search_term.lower() in line.lower()
                    ]
                    results.append({
                        "path": rel_str,
                        "file_name": file_path.name,
                        "match_type": "content",
                        "match_lines": snippet_lines[:5],
                        "match_count": len(snippet_lines),
                    })
                    if len(results) >= max_results:
                        break
            except Exception:
                continue

        result_count = len(results)
        return {
            "success": True,
            "operation": "search",
            "path": str(resolved.relative_to(self._project_root)),
            "search_term": search_term,
            "result_count": result_count,
            "results": results,
            "summary": f"Searched {str(resolved.relative_to(self._project_root))} for '{search_term}' — found {result_count} matching files",
        }

    async def _list(self, path: str) -> Dict[str, Any]:
        """List available documentation files in a directory."""
        resolved = self._resolve_path(path)
        if resolved is None:
            return {
                "success": False,
                "error": f"Invalid path: '{path}'.",
                "error_type": "PathError",
            }

        if not resolved.exists():
            return {
                "success": False,
                "error": f"Path not found: '{path}'",
                "error_type": "NotFoundError",
            }

        if not resolved.is_dir():
            return {
                "success": False,
                "error": f"'{path}' is not a directory.",
                "error_type": "ValidationError",
            }

        error = self._validate_path(resolved)
        if error:
            return {
                "success": False,
                "error": error,
                "error_type": "SecurityError",
            }

        items: List[Dict[str, Any]] = []
        for entry in sorted(resolved.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            # Skip hidden files
            if entry.name.startswith("."):
                continue

            # Validate child entries
            try:
                child_error = self._validate_path(entry)
                if child_error:
                    continue
            except ValueError:
                continue

            if entry.is_dir():
                items.append({
                    "name": entry.name,
                    "type": "directory",
                    "path": str(entry.relative_to(self._project_root)),
                })
            elif entry.is_file() and entry.suffix.lower() in ALLOWED_EXTENSIONS:
                items.append({
                    "name": entry.name,
                    "type": "file",
                    "path": str(entry.relative_to(self._project_root)),
                    "size": entry.stat().st_size,
                })

        count = len(items)
        directories_count = sum(1 for i in items if i["type"] == "directory")
        files_count = sum(1 for i in items if i["type"] == "file")
        return {
            "success": True,
            "operation": "list",
            "path": str(resolved.relative_to(self._project_root)),
            "items": items,
            "count": count,
            "directories": directories_count,
            "files": files_count,
            "summary": f"Listed {str(resolved.relative_to(self._project_root))} — {count} items ({directories_count} dirs, {files_count} files)",
        }

    async def _semantic_search(
        self,
        query: str,
        top_k: int = 10,
        min_score: float = 0.0,
        source_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Find documentation by meaning using vector similarity search.

        Uses the ``DocVectorStore`` singleton (``sqlite-vec`` + Ollama
        embeddings).  Gracefully degrades if the embedding service is
        unreachable — returns empty results with an explanatory message.

        Parameters
        ----------
        query:
            Natural language query string.
        top_k:
            Maximum number of results (clamped by vector store to 20).
        min_score:
            Minimum similarity threshold (0.0–1.0).
        source_filter:
            Optional path prefix to restrict results (e.g. ``"docs/atlas"``).
            Validated against the whitelist for security.
        """
        if not query:
            return {
                "success": True,
                "operation": "semantic_search",
                "query": query,
                "result_count": 0,
                "results": [],
                "summary": "No query provided — returning empty results. Please provide a 'query' string for semantic search.",
            }

        # ── Resolve source_filter against whitelist ──────────────────────────
        resolved_source_filter: Optional[str] = None
        if source_filter:
            resolved = self._resolve_path(source_filter)
            if resolved is None:
                return {
                    "success": False,
                    "error": f"Invalid source_filter path: '{source_filter}'.",
                    "error_type": "PathError",
                }
            error = self._validate_path(resolved)
            if error:
                return {
                    "success": False,
                    "error": f"source_filter access denied: {error}",
                    "error_type": "SecurityError",
                }
            # Convert to a LIKE pattern
            rel = str(resolved.relative_to(self._project_root))
            if resolved.is_dir():
                resolved_source_filter = f"{rel}/%"
            else:
                resolved_source_filter = rel

        # ── Lazy imports to avoid circular deps ──────────────────────────────
        from app.domain.tools.builtin.doc_vector_store import DocVectorStore

        # ── The embedding service — the `embeddings` capability, resolved ────
        # An install that configured no embedding model cannot search an index, and says so in the
        # capability's own wording rather than searching with a default.
        embedding_service = await self._embedding_service()
        if not embedding_service.resolved:
            return {
                "success": True,
                "operation": "semantic_search",
                "query": query,
                "result_count": 0,
                "results": [],
                "summary": embedding_service.report(),
                "note": "embedding_unconfigured",
            }

        from app.core.config import Paths as _Paths
        doc_index = str(_Paths.rag_index_path)

        # ── Resolve doc_index_path relative to project root ──────────────────
        doc_index_abs = str((self._project_root / doc_index).resolve())

        # ── Get or create vector store singleton ─────────────────────────────
        store = DocVectorStore.get_instance(
            db_path=doc_index_abs,
            embedding=embedding_service,
        )

        # ── Ensure DB is initialized (tables exist) ──────────────────────────
        store.init_db()

        # ── Embed query ──────────────────────────────────────────────────────
        embedding = store.embed_query(query)
        if embedding is None:
            return {
                "success": True,
                "operation": "semantic_search",
                "query": query,
                "result_count": 0,
                "results": [],
                "summary": (
                    "Semantic search is currently unavailable — the embedding "
                    "service (Ollama) could not be reached. Please ensure Ollama "
                    "is running and try again. Keyword-based search is still "
                    "available via the 'search' operation."
                ),
                "note": "embedding_service_unavailable",
            }

        # ── Search ───────────────────────────────────────────────────────────
        raw_results = store.search(
            embedding=embedding,
            top_k=top_k,
            min_score=min_score,
            source_filter=resolved_source_filter,
        )

        # ── Format results ───────────────────────────────────────────────────
        results = []
        for r in raw_results:
            results.append({
                "source_path": r["source_path"],
                "chunk_text": r["chunk_text"],
                "heading": r["heading"],
                "heading_ancestry": r["heading_ancestry"],
                "similarity_score": r["similarity_score"],
            })

        count = len(results)
        return {
            "success": True,
            "operation": "semantic_search",
            "query": query,
            "top_k": top_k,
            "min_score": min_score,
            "source_filter": source_filter,
            "result_count": count,
            "results": results,
            "summary": (
                f"Semantic search for '{query}' — found {count} relevant "
                f"document section{'s' if count != 1 else ''}"
                + (f" (min score: {min_score})" if min_score > 0.0 else "")
            ),
        }

    async def _code_search(
        self,
        query: str,
        language: Optional[str] = None,
        max_results: int = 5,
    ) -> Dict[str, Any]:
        """Find source code by meaning using vector similarity search.

        Uses the ``CodeVectorStore`` singleton (``sqlite-vec`` + Ollama
        embeddings).  Gracefully degrades if the embedding service is
        unreachable — returns empty results with an explanatory message.

        Parameters
        ----------
        query:
            Natural language query describing the code to find.
        language:
            Optional language filter (e.g. ``"python"``, ``"typescript"``).
        max_results:
            Maximum number of results (clamped to 20).
        """
        if not query:
            return {
                "success": True,
                "operation": "code_search",
                "query": query,
                "result_count": 0,
                "results": [],
                "summary": "No query provided — returning empty results. Please provide a 'query' string for code search.",
            }

        # ── Lazy imports to avoid circular deps ──────────────────────────────
        from app.domain.tools.builtin.code_vector_store import CodeVectorStore

        # ── The embedding service — the `embeddings` capability, resolved ────
        # No local defaults, and no branch that overrules configuration: this used to force
        # `nomic-embed-text`/`768` whenever `embedding_provider` was not `ollama` — a value read off a
        # config object that was always None.
        embedding_service = await self._embedding_service()
        if not embedding_service.resolved:
            return {
                "success": True,
                "operation": "code_search",
                "query": query,
                "result_count": 0,
                "results": [],
                "summary": embedding_service.report(),
                "note": "embedding_unconfigured",
            }

        # Code index path — always ``data/system_code_vector.db`` relative to project root
        from app.core.config import Paths as _Paths
        code_index = str(_Paths.code_vector_path)
        code_index_abs = str((self._project_root / code_index).resolve())

        # ── Get or create vector store singleton ─────────────────────────────
        store = CodeVectorStore.get_instance(
            db_path=code_index_abs,
            embedding=embedding_service,
        )

        # ── Ensure DB is initialized (tables exist) ──────────────────────────
        store.init_db()

        # ── Search ───────────────────────────────────────────────────────────
        raw_results = store.semantic_search(
            query=query,
            top_k=max_results,
            language_filter=language,
        )

        # ── Format results ───────────────────────────────────────────────────
        results = []
        for r in raw_results:
            results.append({
                "file_path": r["file_path"],
                "language": r["language"],
                "symbol_name": r["symbol_name"],
                "chunk_type": r["chunk_type"],
                "content": r["content"],
                "similarity": r["similarity"],
                "line_start": r["line_start"],
                "line_end": r["line_end"],
            })

        if not results:
            # Check if the embedding service is available
            embedding = store.embed_query(query)
            if embedding is None:
                return {
                    "success": True,
                    "operation": "code_search",
                    "query": query,
                    "result_count": 0,
                    "results": [],
                    "summary": (
                        "Code search is currently unavailable — the embedding "
                        "service (Ollama) could not be reached. Please ensure Ollama "
                        "is running and try again."
                    ),
                    "note": "embedding_service_unavailable",
                }

        count = len(results)
        lang_info = f" in {language}" if language else ""
        return {
            "success": True,
            "operation": "code_search",
            "query": query,
            "language": language,
            "max_results": max_results,
            "result_count": count,
            "results": results,
            "summary": (
                f"Code search for '{query}'{lang_info} — found {count} "
                f"relevant code section{'s' if count != 1 else ''}"
            ),
        }
