"""The run-python meta-tool (2026-08-24, the tool-purge discussion).

THE USER'S CALL: build the Python runner FIRST, see it in action,
THEN decide how much liberty it needs. This is the CONSERVATIVE
sandbox: the compute/read class (calculator, text-tools, log
analysis, sqlite reads) absorbed into ONE general tool.

THE SANDBOX (version 1):
- exec() in a namespace with the SAFE modules preloaded (math,
  statistics, datetime, json, re, collections, ...)
- the builtins RESTRICTED to the compute/read set — no open, no
  __import__, no eval/exec/compile, no network modules
- a hard timeout (the worker thread join)
- an output cap (stdout + the result repr)
The liberty is DECIDED AFTER SEEING IT WORK — this is the tight
baseline.
"""

from __future__ import annotations

import io
import json
import logging
import collections
import math
import re
import statistics
import textwrap
import threading
import traceback
from contextlib import redirect_stdout
from datetime import datetime, date, timedelta, timezone
from typing import Any, Dict

logger = logging.getLogger(__name__)

# THE SAFE PRELOADS — the compute/read vocabulary. NO file, NO
# network, NO subprocess, NO import machinery.
SAFE_MODULES = {
    "math": math,
    "statistics": statistics,
    "datetime": datetime,
    "date": date,
    "timedelta": timedelta,
    "timezone": timezone,
    "json": json,
    "re": re,
    "collections": collections,
    "textwrap": textwrap,
}

# THE RESTRICTED BUILTINS — the compute/read set. No open,
# __import__, eval, exec, compile, input, or any dunder escape.
SAFE_BUILTINS = {
    "len": len, "range": range, "sum": sum, "min": min, "max": max,
    "abs": abs, "round": round, "sorted": sorted, "reversed": reversed,
    "enumerate": enumerate, "zip": zip, "map": map, "filter": filter,
    "any": any, "all": all, "str": str, "int": int, "float": float,
    "bool": bool, "list": list, "dict": dict, "set": set, "tuple": tuple,
    "format": format, "chr": chr, "ord": ord, "hex": hex, "oct": oct,
    "bin": bin, "isinstance": isinstance, "type": type, "repr": repr,
    "print": print, "True": True, "False": False,
    "None": None, "Exception": Exception, "ValueError": ValueError,
    "TypeError": TypeError, "ZeroDivisionError": ZeroDivisionError,
}

DEFAULT_TIMEOUT_SECONDS = 5.0
MAX_OUTPUT_CHARS = 8000


def _make_safe_readers(base_path: str):
    """The WORKSPACE-SCOPED READ GRANT (2026-08-24, the user's call):
    when the tool config carries a base_path (the agent's workspace,
    the same key file-manager uses), the sandbox gains read_file +
    list_dir SCOPED TO THAT ROOT. The path guard: every resolved
    path must stay under the base — the traversal is blocked.
    Without a base_path the sandbox stays fully closed.
    """
    import os as _os

    root = _os.path.realpath(base_path)

    def _resolve(path: str) -> str:
        p = _os.path.realpath(_os.path.join(root, path))
        if p != root and not p.startswith(root + _os.sep):
            raise PermissionError(f"path escapes the workspace: {path!r}")
        return p

    def read_file(path: str, max_chars: int = 20000) -> str:
        """Read a text file under the workspace (path-traversal
        guarded)."""
        with open(_resolve(path), encoding="utf-8", errors="replace") as fh:
            return fh.read()[:max_chars]

    def list_dir(path: str = ".") -> list:
        """List a directory under the workspace."""
        return sorted(_os.listdir(_resolve(path)))

    return {"read_file": read_file, "list_dir": list_dir}


class RunPythonTool:
    """The sandboxed Python runner (the compute meta-tool)."""

    name = "Run Python"
    slug = "run-python"
    capability = "code-execution"
    # THE WORKSPACE-READ GRANT: the execution service injects the
    # agent's own workspace as the base_path (the sandbox then gains
    # the scoped read_file/list_dir).
    needs_workspace = True
    description = (
        "Run a Python script in a sandbox: math, statistics, text "
        "processing, data analysis (the safe modules are preloaded). "
        "NO file access, NO network, NO imports — the sandbox is "
        "intentionally conservative."
    )
    tags = [
        "op:execute",
        "purpose:productivity",
        "source:system",
        "safe",
        "text",
    ]
    icon = "code"
    color = "#2563EB"

    arguments_schema = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "The Python script to run (the safe modules are preloaded: math, statistics, datetime, json, re, collections...)",
            },
        },
        "required": ["code"],
    }

    config_schema = {
        "type": "object",
        "properties": {
            "timeout_seconds": {
                "type": "number",
                "default": DEFAULT_TIMEOUT_SECONDS,
                "description": "The hard execution timeout",
            },
        },
        "required": [],
    }

    def __init__(self) -> None:
        self._result: Dict[str, Any] = {}
        self._error: str | None = None

    def _run(self, code: str, namespace: Dict[str, Any]) -> None:
        """Exec the code in the sandbox (the worker thread target)."""
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                exec(compile(code, "<run-python>", "exec"), namespace)
            self._result = {
                "success": True,
                "output": buf.getvalue()[:MAX_OUTPUT_CHARS],
                "truncated": len(buf.getvalue()) > MAX_OUTPUT_CHARS,
            }
        except Exception as e:  # noqa: BLE001
            self._error = traceback.format_exc(limit=3)

    async def execute(self, config: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Run the script with the guardrails: the safe namespace,
        the timeout, the output cap."""
        # the reset — the instance may be shared across runs
        self._result = {}
        self._error = None

        code = (kwargs.get("code") or "").strip()
        if not code:
            return {
                "success": False,
                "error": "No code provided.",
                "error_type": "ValidationError",
                "user_message": "Please provide a Python script to run.",
            }

        timeout = float(config.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS))
        namespace: Dict[str, Any] = dict(SAFE_MODULES)
        namespace["__builtins__"] = SAFE_BUILTINS
        # the result anchor: the script may assign 'result' to return a value
        namespace["result"] = None

        # THE WORKSPACE-READ GRANT: the base_path config enables the
        # scoped readers (the agent's own workspace); no base_path =
        # the fully closed sandbox.
        base_path = config.get("base_path")
        if base_path:
            namespace.update(_make_safe_readers(str(base_path)))
            namespace["workspace"] = str(base_path)

        worker = threading.Thread(
            target=self._run, args=(code, namespace), daemon=True
        )
        worker.start()
        worker.join(timeout=timeout)

        if worker.is_alive():
            return {
                "success": False,
                "error": f"The script exceeded the {timeout:g}s time limit.",
                "error_type": "TimeoutError",
                "user_message": "The script took too long — simplify it or reduce the work.",
            }

        if self._error:
            logger.warning("run-python script error: %s", self._error[:200])
            return {
                "success": False,
                "error": self._error,
                "error_type": "ScriptError",
                "user_message": "The script raised an error — check the traceback.",
            }

        result = self._result
        result["result"] = repr(namespace.get("result"))
        result["stdout"] = result.get("output", "")
        return result
