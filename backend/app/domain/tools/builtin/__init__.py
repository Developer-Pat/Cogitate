"""
Built-in Tool Handlers.

This package contains handlers for built-in tools that execute locally
without external dependencies.
"""

from __future__ import annotations

__all__ = [
    "ClipboardTool",
    "DateTimeTool",
    "TodoListTool",
    "FileInfoTool",
    "FileManagerTool",
    "LineEditorTool",
    "TextToolsTool",
    "DuckDuckGoTool",
    "JinaReaderTool",
    "SummarizeLlmTool",
    "SqliteQueryTool",
    "LogReaderTool",
    "StateDumperTool",
    "DocReaderTool",
    "DocIndexTool",
    "ModeShifterTool",
    "SequentialThinkingTool",  # Sequential Thinking — reasoning scratchpad
    "RunPostTool",             # Power-On Self Test (POST)
    "AgentSelectTool",         # ARM — the yellow pages (select agents)
]

# Import tool classes for easy access
from app.domain.tools.builtin.datetime_handler import DateTimeTool
from app.domain.tools.builtin.file_info_handler import FileInfoTool
from app.domain.tools.builtin.file_manager_handler import FileManagerTool
from app.domain.tools.builtin.duckduckgo_handler import DuckDuckGoTool
from app.domain.tools.builtin.wikipedia_handler import WikipediaTool  # noqa: F401 — tool surface this package re-exports
from app.domain.tools.builtin.run_python_handler import RunPythonTool  # noqa: F401 — tool surface this package re-exports
from app.domain.tools.builtin.jina_reader_handler import JinaReaderTool
from app.domain.tools.builtin.sqlite_query_handler import SqliteQueryTool
from app.domain.tools.builtin.state_dumper import StateDumperTool
from app.domain.tools.builtin.doc_reader import DocReaderTool
from app.domain.tools.builtin.doc_index import DocIndexTool
from app.domain.tools.builtin.sequential_thinking_handler import SequentialThinkingTool
from app.domain.tools.builtin.run_post import RunPostTool
from app.domain.tools.builtin.agent_select_handler import AgentSelectTool
