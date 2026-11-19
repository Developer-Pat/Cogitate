"""
File Info Tool Handler.

Provides file and directory information operations.
"""

from __future__ import annotations

import fnmatch
import logging
import os
import re
from pathlib import Path
from app.core.config import Paths
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class FileInfoTool:
    """
    File Info tool for reading file metadata.

    Tags:
        - op:read
        - purpose:development, purpose:system
        - source:local-file
        - safe
        - text

    Operations:
        - exists: Check if file exists
        - info: Get file metadata (size, modified, type)
        - list: List directory contents
        - read: Read a text file's content (capped)
        - search: Regex-search file contents inside the workspace
    """

    name = "File Info"
    slug = "file-info"
    capability = "file-read"
    # THE WORKSPACE SANDBOX (2026-09-09): the execution service injects
    # the agent's own workspace as the config base_path (needs_workspace,
    # the same mechanism the skill-reader/run-python use). All operations
    # resolve against that base — an agent reads its own workspace, not
    # the whole project. The project-root remains the fallback only when
    # no workspace exists (the non-agent/system-manager path). Agents
    # that legitimately need project-wide reads get an explicit
    # agent_tools config base_path (which wins over the injection).
    needs_workspace = True
    description = (
        "Utility for the agent's own workspace: checking file existence, "
        "getting file metadata (size, modified time, type), listing "
        "directory contents, reading file contents, and searching file "
        "contents by regex. operation='search' greps the workspace for a "
        "pattern (optionally filtered by a filename glob, case-insensitive, "
        "with an explicit result cap that reports truncation) and returns "
        "{file, line, text} matches; read any matched file with "
        "operation='read'. All paths are confined to the agent's workspace. "
        "For semantic questions about the system, prefer doc-reader with "
        "semantic_search instead."
    )
    tags = [
        "op:read",
        "purpose:development",
        "purpose:system",
        "source:local-file",
        "safe",
        "text",
    ]
    icon = "file-info"
    color = "#6F42C1"

    # SEARCH BOUNDS (2026-09-10): every cap below is surfaced explicitly in
    # the result — a bounded search must never read as a complete one (the
    # standing silent-failure doctrine). A runaway regex over a huge
    # workspace must not hang the agent, and one unreadable or binary file
    # must never abort the walk.
    _SEARCH_MAX_FILE_BYTES = 2 * 1024 * 1024  # 2 MB scanned per file
    _SEARCH_MAX_FILES_WALKED = 5000  # total candidates walked
    _SEARCH_DEFAULT_MAX_RESULTS = 50
    _SEARCH_HARD_MAX_RESULTS = 200
    _SEARCH_MAX_LINE_CHARS = 500  # per-match snippet bound

    arguments_schema = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["exists", "info", "list", "read", "search"],
                "default": "info",
                "description": "File operation to perform",
            },
            "path": {
                "type": "string",
                "default": ".",
                "description": "Path to file or directory. For operation='search' this is the file or directory to search within (default: the whole workspace).",
            },
            "show_hidden": {
                "type": "boolean",
                "default": False,
                "description": "Include hidden files when listing directory (only used with operation='list')",
            },
            "pattern": {
                "type": "string",
                "description": "Regex searched in file contents (required for operation='search')",
            },
            "glob": {
                "type": "string",
                "description": "Restrict candidate files by filename glob, e.g. '*.md' or '*.json' (only used with operation='search')",
            },
            "ignore_case": {
                "type": "boolean",
                "default": False,
                "description": "Case-insensitive matching (only used with operation='search')",
            },
            "max_results": {
                "type": "integer",
                "default": 50,
                "minimum": 1,
                "maximum": 200,
                "description": "Maximum number of matches returned for operation='search' (hard cap 200); when hit, the result sets 'truncated': true",
            },
        },
        "required": [],
    }

    config_schema = {
        "type": "object",
        "properties": {
            "base_path": {
                "type": "string",
                "description": "Base path for file operations (empty = the agent's own workspace, injected at execution; set explicitly to grant project-wide reads)"
            },
            "allow_symlinks": {
                "type": "boolean",
                "default": True,
                "description": "Allow following symbolic links"
            },
            "max_depth": {
                "type": "integer",
                "default": 3,
                "minimum": 1,
                "maximum": 10,
                "description": "Maximum directory traversal depth"
            }
        },
    }

    async def execute(self, config: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Execute file info operation.

        Args:
            config: Tool configuration
            **kwargs: Tool arguments (operation, path, etc.)

        Returns:
            Dictionary with success status and result
        """
        operation = kwargs.get("operation", "info")
        path = kwargs.get("path", config.get("base_path", "."))

        try:
            resolved = self._resolve_sandbox_path(config, path)
            if resolved is None:
                base = config.get("base_path") or str(Paths.root)
                return {
                    "success": False,
                    "error": f"Path outside the sandbox ({base}): {path}",
                }
            if operation == "exists":
                return await self._exists(str(resolved))
            elif operation == "info":
                return await self._info(str(resolved))
            elif operation == "list":
                show_hidden = kwargs.get("show_hidden", False)
                return await self._list(str(resolved), show_hidden)
            elif operation == "read":
                max_chars = int(kwargs.get("max_chars", 20000))
                return await self._read(str(resolved), max_chars)
            elif operation == "search":
                return await self._search(
                    str(resolved),
                    kwargs.get("pattern", ""),
                    config,
                    glob=kwargs.get("glob"),
                    ignore_case=bool(kwargs.get("ignore_case", False)),
                    max_results=kwargs.get(
                        "max_results", self._SEARCH_DEFAULT_MAX_RESULTS
                    ),
                )
            else:
                return {
                    "success": False,
                    "error": f"Unknown operation: {operation}",
                }
        except Exception as e:
            logger.error(f"File info tool error: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }

    def _resolve_sandbox_path(self, config: Dict[str, Any], path: str):
        """Resolve a path against the sandbox base (the workspace).

        Relative paths resolve inside the base; absolute paths must
        stay inside it. Returns the resolved Path, or None when the
        path escapes the sandbox. The base is the injected workspace
        (needs_workspace) or an explicit agent_tools config
        base_path; the project-root remains the fallback only when
        no base exists (the non-agent path).
        """
        base = config.get("base_path")
        base_p = Path(base).expanduser() if base else Paths.root
        try:
            base_p = base_p.resolve()
        except Exception:
            pass
        raw = Path(path).expanduser()
        if not raw.is_absolute():
            raw = base_p / raw
        try:
            resolved = raw.resolve()
        except Exception:
            resolved = raw.absolute()
        try:
            resolved.relative_to(base_p)
        except ValueError:
            return None
        return resolved

    def _sandbox_base(self, config: Dict[str, Any]) -> Path:
        """Resolve the sandbox base (the agent's injected workspace).

        Mirrors the base resolution in _resolve_sandbox_path so the
        search walk can re-verify every candidate file against the same
        base — a symlink inside the workspace that points outside it is
        rejected rather than followed out.
        """
        base = config.get("base_path")
        base_p = Path(base).expanduser() if base else Paths.root
        try:
            return base_p.resolve()
        except Exception:
            return base_p

    async def _read(self, path: str, max_chars: int = 20000) -> Dict[str, Any]:
        """Read a file's content (THE DEEP-AGENT READ GAP, 2026-08-22).

        The tag-layer-sweeper smoke test proved the agents could list
        files but never READ them — file-info had exists/info/list but
        no read, despite its declared capability 'file-read'. The agent
        improvised (sqlite-query, the failing jina_reader) and never
        saw the wiki frontmatter.

        Sandboxed to the project root; capped at max_chars (the
        silent-failure doctrine: an explicit cap + a flag, not a
        truncated-looking success). Text files only.
        """
        p = Path(path).expanduser()
        try:
            p = p.resolve()
        except Exception:
            p = Path(path)
        project_root = Paths.root
        try:
            p.relative_to(project_root)
        except ValueError:
            return {"success": False, "error": f"Path outside the project: {path}", "operation": "read"}
        if not p.is_file():
            return {"success": False, "error": f"Not a file: {path}", "operation": "read"}
        try:
            data = p.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return {"success": False, "error": f"Read failed: {e}", "operation": "read"}
        truncated = len(data) > max_chars
        return {
            "success": True,
            "operation": "read",
            "path": str(p),
            "content": data[:max_chars],
            "truncated": truncated,
            "chars": len(data),
        }

    async def _search(
        self,
        path: str,
        pattern: str,
        config: Dict[str, Any],
        glob: str | None = None,
        ignore_case: bool = False,
        max_results: int = 50,
    ) -> Dict[str, Any]:
        """Regex-search file contents inside the sandbox (2026-09-10).

        THE WORKSPACE-SEARCH GAP: agents are confined to their own
        workspace but had no way to grep it — the only search surface
        (doc-reader semantic_search) answers questions about the SYSTEM,
        not about the files an agent just wrote to its own workspace.
        Agents improvised with run-python walking the tree and pasting
        matches by hand. This gives them a first-class, sandboxed grep.

        PURE PYTHON BY DESIGN: re + os.walk + Path.read_bytes, never a
        subprocess. No system `grep` dependency, the sandbox containment
        holds, and there is no command-injection surface.

        The silent-failure doctrine holds throughout: the result cap
        sets `truncated`, oversized/unreadable/binary files are skipped
        and COUNTED, and the walk cap is reported — a bounded search
        never looks like a complete one.
        """
        if not pattern:
            return {
                "success": False,
                "operation": "search",
                "error": "Missing required parameter: pattern",
            }
        try:
            regex = re.compile(pattern, re.IGNORECASE if ignore_case else 0)
        except re.error as e:
            return {
                "success": False,
                "operation": "search",
                "error": f"Invalid regex: {e}",
            }

        try:
            max_results = int(max_results)
        except (TypeError, ValueError):
            max_results = self._SEARCH_DEFAULT_MAX_RESULTS
        max_results = max(1, min(max_results, self._SEARCH_HARD_MAX_RESULTS))

        target = Path(path)
        if not target.exists():
            return {
                "success": False,
                "operation": "search",
                "error": f"Path does not exist: {path}",
            }

        base = self._sandbox_base(config)

        matches: List[Dict[str, Any]] = []
        skipped_binary = 0
        skipped_unreadable = 0
        skipped_large = 0
        skipped_outside = 0
        files_walked = 0
        files_scanned = 0
        walk_capped = False
        truncated = False

        if target.is_file():
            candidates = iter([target])
        else:
            candidates = (
                Path(root) / name
                for root, _dirs, files in os.walk(target, followlinks=False)
                for name in files
            )

        for fp in candidates:
            if files_walked >= self._SEARCH_MAX_FILES_WALKED:
                walk_capped = True
                break
            files_walked += 1

            if glob and not fnmatch.fnmatch(fp.name, glob):
                continue

            # SYMLINK / CONTAINMENT GUARD: resolve and re-check against the
            # base, so a symlink inside the workspace cannot pull a file in
            # from outside it. os.walk(followlinks=False) already refuses to
            # descend symlinked directories.
            try:
                rp = fp.resolve()
            except Exception:
                skipped_unreadable += 1
                continue
            try:
                rp.relative_to(base)
            except ValueError:
                skipped_outside += 1
                continue
            if not rp.is_file():
                continue

            try:
                if rp.stat().st_size > self._SEARCH_MAX_FILE_BYTES:
                    skipped_large += 1
                    continue
                raw = rp.read_bytes()
            except (OSError, PermissionError):
                skipped_unreadable += 1
                continue

            # NUL byte ⇒ binary; skip it and report, never let it abort.
            if b"\x00" in raw:
                skipped_binary += 1
                continue

            files_scanned += 1
            text = raw.decode("utf-8", errors="replace")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if not regex.search(line):
                    continue
                if len(matches) >= max_results:
                    truncated = True
                    break
                snippet = line
                if len(snippet) > self._SEARCH_MAX_LINE_CHARS:
                    snippet = snippet[: self._SEARCH_MAX_LINE_CHARS]
                matches.append({"file": str(rp), "line": lineno, "text": snippet})
            if truncated:
                break

        notes: List[str] = []
        if truncated:
            notes.append(
                f"Result cap hit: showing the first {max_results} matches; more exist. "
                "Narrow the pattern/glob/path or raise max_results."
            )
        if walk_capped:
            notes.append(
                f"File-walk cap hit at {self._SEARCH_MAX_FILES_WALKED} files; "
                "the workspace was not fully searched."
            )
        if skipped_binary or skipped_unreadable or skipped_large or skipped_outside:
            notes.append(
                "Skipped files — binary: "
                f"{skipped_binary}, unreadable: {skipped_unreadable}, "
                f"over {self._SEARCH_MAX_FILE_BYTES} bytes: {skipped_large}, "
                f"outside sandbox: {skipped_outside}."
            )

        result: Dict[str, Any] = {
            "success": True,
            "operation": "search",
            "path": str(target),
            "pattern": pattern,
            "matches": matches,
            "count": len(matches),
            "truncated": truncated,
            "max_results": max_results,
            "files_scanned": files_scanned,
            "files_walked": files_walked,
            "skipped_binary": skipped_binary,
            "skipped_unreadable": skipped_unreadable,
            "skipped_large": skipped_large,
            "skipped_outside_sandbox": skipped_outside,
        }
        if notes:
            result["note"] = " ".join(notes)
        return result

    async def _exists(self, path: str) -> Dict[str, Any]:
        """Check if a file or directory exists."""
        p = Path(path)
        exists = p.exists()

        return {
            "success": True,
            "operation": "exists",
            "path": str(p.absolute()),
            "exists": exists,
            "is_file": p.is_file() if exists else False,
            "is_directory": p.is_dir() if exists else False,
        }

    async def _info(self, path: str) -> Dict[str, Any]:
        """Get file/directory metadata."""
        p = Path(path)

        if not p.exists():
            return {
                "success": False,
                "error": f"Path does not exist: {path}",
            }

        try:
            stat_info = p.stat()
            abs_path = p.absolute()

            # Get file type
            file_type = "unknown"
            if p.is_file():
                file_type = "file"
                # Try to determine extension
                ext = p.suffix.lower()
                if ext in [".py", ".js", ".ts", ".tsx", ".jsx"]:
                    file_type = "source_code"
                elif ext in [".txt", ".md", ".rst"]:
                    file_type = "text"
                elif ext in [".json", ".yaml", ".yml", ".toml", ".xml"]:
                    file_type = "config"
                elif ext in [".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp"]:
                    file_type = "image"
                elif ext in [".mp3", ".wav", ".ogg", ".flac"]:
                    file_type = "audio"
                elif ext in [".mp4", ".avi", ".mkv", ".webm"]:
                    file_type = "video"
                elif ext in [".zip", ".tar", ".gz", ".rar", ".7z"]:
                    file_type = "archive"
            elif p.is_dir():
                file_type = "directory"

            # Get modification times
            modified = datetime.fromtimestamp(stat_info.st_mtime)
            created = datetime.fromtimestamp(stat_info.st_ctime)
            accessed = datetime.fromtimestamp(stat_info.st_atime)

            return {
                "success": True,
                "operation": "info",
                "path": str(abs_path),
                "type": file_type,
                "size": stat_info.st_size,
                "size_human": self._format_size(stat_info.st_size),
                "modified": modified.isoformat(),
                "modified_human": modified.strftime("%Y-%m-%d %H:%M:%S"),
                "created": created.isoformat(),
                "created_human": created.strftime("%Y-%m-%d %H:%M:%S"),
                "accessed": accessed.isoformat(),
                "is_readable": os.access(p, os.R_OK),
                "is_writable": os.access(p, os.W_OK),
                "is_executable": os.access(p, os.X_OK),
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to get file info: {str(e)}",
            }

    async def _list(self, path: str, show_hidden: bool = False) -> Dict[str, Any]:
        """List directory contents."""
        p = Path(path)

        if not p.exists():
            return {
                "success": False,
                "error": f"Path does not exist: {path}",
            }

        if not p.is_dir():
            return {
                "success": False,
                "error": f"Path is not a directory: {path}",
            }

        try:
            items: List[Dict[str, Any]] = []
            abs_path = p.absolute()

            for item in p.iterdir():
                # Skip hidden files unless requested
                if not show_hidden and item.name.startswith("."):
                    continue

                try:
                    stat_info = item.stat()
                    item_info = {
                        "name": item.name,
                        "path": str(item.absolute()),
                        "is_file": item.is_file(),
                        "is_directory": item.is_dir(),
                        "is_symlink": item.is_symlink(),
                        "size": stat_info.st_size if item.is_file() else 0,
                        "size_human": self._format_size(stat_info.st_size) if item.is_file() else "0 B",
                        "modified": datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                    }
                    items.append(item_info)
                except (PermissionError, OSError) as e:
                    items.append({
                        "name": item.name,
                        "path": str(item.absolute()),
                        "error": f"Cannot access: {str(e)}",
                    })

            # Sort: directories first, then files, alphabetically
            items.sort(key=lambda x: (not x.get("is_directory", False), x["name"].lower()))

            return {
                "success": True,
                "operation": "list",
                "path": str(abs_path),
                "items": items,
                "count": len(items),
                "directories": sum(1 for i in items if i.get("is_directory", False)),
                "files": sum(1 for i in items if i.get("is_file", False)),
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to list directory: {str(e)}",
            }

    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        if size_bytes == 0:
            return "0 B"

        units = ["B", "KB", "MB", "GB", "TB"]
        size = float(size_bytes)
        unit_index = 0

        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1

        return f"{size:.2f} {units[unit_index]}"
