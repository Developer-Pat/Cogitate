"""
Workspace Search Tool Handler.

A thin, findable-by-name front door for the workspace grep. The search
IMPLEMENTATION lives in FileInfoTool._search (one copy); this tool only
resolves the sandbox and delegates to it.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.domain.tools.builtin.file_info_handler import FileInfoTool

logger = logging.getLogger(__name__)


class WorkspaceSearchTool:
    """
    Search tool for grepping the agent's own workspace by regex.

    Tags:
        - op:read
        - purpose:development, purpose:system
        - source:local-file
        - safe
        - text

    THE DISCOVERABILITY GAP (2026-09-10): search shipped as an operation
    on File Info, which is the economical place for it — one tool, one
    capability, no new surface. But an agent perceives its tools as a
    LIST OF NAMES, and adding an operation does not change any name. An
    agent asked to search its workspace listed its tools, saw nothing
    called search, and correctly reported that the capability was not
    there. It was, and it could not be found.

    So this tool exists for the NAME. It carries no logic of its own:
    it resolves the sandbox exactly as File Info does and delegates to
    the same implementation, so the two surfaces cannot drift.
    """

    name = "Search"
    slug = "search"
    # file-read is GRAS (default-on) — the same tier as File Info, so
    # this reaches every agent without a kit change. Search only READS.
    capability = "file-read"
    # the agent's own workspace is the sandbox (the execution service
    # injects it as config['base_path']); see FileInfoTool's note.
    needs_workspace = True
    icon = "M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"  # magnifier
    color = "#0D6EFD"
    description = (
        "Search YOUR OWN workspace for text by regex — grep the files you "
        "have written (notes, beat sheets, reports, state, skills). Returns "
        "{file, line, text} matches with a count; a capped result sets "
        "truncated=true rather than looking complete. Filter by filename "
        "with glob (e.g. '*.md'), match case-insensitively with "
        "ignore_case. All paths stay inside your workspace. Use this to "
        "find where something is or what you wrote before; use file-info "
        "operation='read' to read a matched file, and doc-reader for "
        "semantic questions about the SYSTEM rather than your own files."
    )
    tags = [
        "op:read",
        "purpose:development",
        "purpose:system",
        "source:local-file",
        "safe",
        "text",
    ]
    # every schema param is declared: an undeclared param is one the
    # model will guess at and silently fail to send (the file-manager
    # `content` incident).
    arguments_schema = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Regex searched in file contents (required)",
            },
            "path": {
                "type": "string",
                "default": ".",
                "description": (
                    "File or directory to search within, relative to your "
                    "workspace (default: the whole workspace)"
                ),
            },
            "glob": {
                "type": "string",
                "description": "Restrict candidate files by filename glob, e.g. '*.md' or '*.json'",
            },
            "ignore_case": {
                "type": "boolean",
                "default": False,
                "description": "Case-insensitive matching",
            },
            "max_results": {
                "type": "integer",
                "default": 50,
                "minimum": 1,
                "maximum": 200,
                "description": "Maximum matches to return (hard cap 200); when hit, the result sets 'truncated': true",
            },
        },
        "required": ["pattern"],
    }
    config_schema = {
        "type": "object",
        "properties": {
            "base_path": {
                "type": "string",
                "description": (
                    "Sandbox root — all searches resolve within this path. "
                    "Injected from the agent's workspace at execution; set "
                    "explicitly only to grant project-wide reads."
                ),
            },
        },
    }

    def __init__(self) -> None:
        # the implementation lives in FileInfoTool — one copy, no drift
        self._impl = FileInfoTool()

    async def execute(self, config: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Resolve the sandbox, then delegate to the shared search.

        Args:
            config: Tool configuration (carries the injected base_path)
            **kwargs: pattern (required), path, glob, ignore_case,
                max_results

        Returns:
            The shared implementation's result — {success, matches,
            count, truncated, ...} — or a clean refusal when the path
            escapes the sandbox.
        """
        pattern = kwargs.get("pattern")
        if not pattern:
            return {
                "success": False,
                "operation": "search",
                "error": "Missing required parameter: pattern",
            }
        path = kwargs.get("path") or config.get("base_path") or "."

        try:
            # THE SAME SANDBOX RESOLUTION as every File Info operation —
            # a relative path stays inside the base, an absolute path or
            # a symlink escaping it is refused.
            resolved = self._impl._resolve_sandbox_path(config, str(path))
            if resolved is None:
                base = config.get("base_path") or "the workspace"
                return {
                    "success": False,
                    "operation": "search",
                    "error": f"Path outside the sandbox ({base}): {path}",
                }
            return await self._impl._search(
                str(resolved),
                str(pattern),
                config,
                glob=kwargs.get("glob"),
                ignore_case=bool(kwargs.get("ignore_case", False)),
                max_results=kwargs.get(
                    "max_results", FileInfoTool._SEARCH_DEFAULT_MAX_RESULTS
                ),
            )
        except Exception as e:
            logger.error(f"Workspace search tool error: {e}", exc_info=True)
            return {"success": False, "operation": "search", "error": str(e)}
