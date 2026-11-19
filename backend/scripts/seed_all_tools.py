#!/usr/bin/env python3
"""
Master Tool Seeding Script — Consolidated from 9 individual scripts.

Replaces the following scripts (all deleted):
  - seed_builtin_tools.py       (6 builtin tools + SQLite Query + SQLite Manager)
  - seed_tools.py               (Calculator, Echo, Web Search, Wikipedia, File Reader, Time, Weather + categories)
  - seed_introspection_tools.py (5 introspection tools)
  - seed_guide_dev_tools.py     (3 guide-dev tools: doc-reader, doc-index)
  - add_duckduckgo_tool.py      (DuckDuckGo search)
  - add_jina_reader_tool.py     (Jina Reader)
  - add_tavily_tool.py          (Tavily search)
  - add_wikipedia_tool.py       (Wikipedia)
  - add_sqlite_manager_tool.py  (SQLite Manager)

Also replaces update_tool_arguments_schema.py and update_tavily_tool.py: tool
definitions (arguments and config included) live in the code registry and are
synced at boot, so neither needs a one-shot migration.

Usage:
    cd backend
    uv run python scripts/seed_all_tools.py

    # Seed only specific groups:
    uv run python scripts/seed_all_tools.py --groups builtin,web,introspection
"""

import argparse
import asyncio
import logging
import uuid

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.domain.tools.models import Tool, ToolCategory

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("seed_all_tools")


def _uuid() -> str:
    return uuid.uuid4().hex[:32]


async def _get_or_create_category(
    session: AsyncSessionLocal,
    name: str,
    slug: str,
    description: str,
    icon: str = "toolbox",
    sort_order: int = 0,
) -> ToolCategory:
    result = await session.execute(
        select(ToolCategory).where(ToolCategory.slug == slug)
    )
    cat = result.scalar_one_or_none()
    if cat:
        logger.info(f"  Found category: {cat.name} ({slug})")
        return cat
    cat = ToolCategory(
        id=_uuid(),
        name=name,
        slug=slug,
        description=description,
        icon=icon,
        sort_order=sort_order,
    )
    session.add(cat)
    await session.flush()
    logger.info(f"  Created category: {cat.name} ({slug})")
    return cat


async def _upsert_tool(session: AsyncSessionLocal, tool_def: dict) -> Tool:
    slug = tool_def["slug"]
    result = await session.execute(select(Tool).where(Tool.slug == slug))
    existing = result.scalar_one_or_none()
    if existing:
        logger.info(f"  Skipped {slug} -- already exists (id={existing.id})")
        return existing

    tool = Tool(
        id=_uuid(),
        name=tool_def["name"],
        slug=tool_def["slug"],
        description=tool_def["description"],
        version=tool_def.get("version", "1.0.0"),
        category_id=tool_def["category_id"],
        provider=tool_def.get("provider", "System"),
        type=tool_def.get("type", "builtin"),
        config_schema=tool_def.get("config_schema", {"type": "object", "properties": {}}),
        arguments_schema=tool_def.get("arguments_schema"),
        endpoint=tool_def.get("endpoint"),
        timeout_ms=tool_def.get("timeout_ms", 5000),
        requires_auth=tool_def.get("requires_auth", False),
        icon=tool_def.get("icon", "tool"),
        color=tool_def.get("color", "#6C757D"),
        tags=tool_def.get("tags", []),
        is_active=tool_def.get("is_active", True),
        is_builtin=tool_def.get("is_builtin", True),
    )
    session.add(tool)
    await session.flush()
    logger.info(f"  Created {slug} (id={tool.id})")
    return tool

# ==============================================================================
# Tool Definitions
# ==============================================================================

CATEGORIES = [
    {"name": "Math & Calculation", "slug": "math-calculation",
     "description": "Mathematical and calculation tools", "icon": "calculator", "sort_order": 1},
    {"name": "Communication", "slug": "communication",
     "description": "Communication and messaging tools", "icon": "message", "sort_order": 2},
    {"name": "Web & Internet", "slug": "web-internet",
     "description": "Web browsing and internet tools", "icon": "globe", "sort_order": 3},
    {"name": "File Operations", "slug": "file-operations",
     "description": "File reading and manipulation tools", "icon": "file", "sort_order": 4},
    {"name": "System Information", "slug": "system-information",
     "description": "System monitoring and information tools", "icon": "server", "sort_order": 5},
    {"name": "Utilities", "slug": "utilities",
     "description": "General utility tools", "icon": "toolbox", "sort_order": 6},
    {"name": "Search & Discovery", "slug": "search-discovery",
     "description": "Search and discovery tools", "icon": "search", "sort_order": 7},
]

BUILTIN_TOOLS = [
    {
        "name": "Clipboard", "slug": "clipboard",
        "description": "Read and write to system clipboard",
        "category_slug": "utilities", "provider": "System",
        "config_schema": {"type": "object", "properties": {
            "operation": {"type": "string", "enum": ["read", "write"], "description": "Operation to perform"},
            "content": {"type": "string", "description": "Content to write (required for write operation)"},
        }, "required": ["operation"]},
        "arguments_schema": {"type": "object", "properties": {
            "operation": {"type": "string", "enum": ["read", "write"], "description": "Operation to perform"},
            "content": {"type": "string", "description": "Content to write (required for write operation)"},
        }, "required": ["operation"]},
        "timeout_ms": 5000, "icon": "clipboard", "color": "#17A2B8",
        "tags": ["op:read", "op:write", "purpose:productivity", "source:clipboard", "safe", "text"],
    },
    {
        "name": "DateTime", "slug": "datetime",
        "description": "Get current date/time and perform date operations",
        "category_slug": "system-information", "provider": "System",
        "config_schema": {"type": "object", "properties": {
            "timezone": {"type": "string", "default": "UTC", "description": "Timezone for operations"},
            "default_format": {"type": "string", "default": "iso",
                               "enum": ["iso", "human", "timestamp", "date", "time"],
                               "description": "Default output format"},
        }},
        "timeout_ms": 3000, "icon": "clock", "color": "#FD7E14",
        "tags": ["op:read", "op:execute", "purpose:productivity", "source:system", "safe", "text"],
    },
    {
        "name": "Todo List", "slug": "todo-list",
        "description": "Manage todo lists with full CRUD operations",
        "category_slug": "utilities", "provider": "System",
        "config_schema": {"type": "object", "properties": {
            "max_todos": {"type": "integer", "default": 100, "minimum": 1, "maximum": 1000,
                          "description": "Maximum number of todos"},
            "default_priority": {"type": "string", "default": "medium",
                                 "enum": ["low", "medium", "high", "urgent"],
                                 "description": "Default priority for new todos"},
        }},
        "timeout_ms": 5000, "icon": "check-square", "color": "#28A745",
        "tags": ["op:read", "op:write", "op:create", "op:delete",
                 "purpose:productivity", "purpose:organization",
                 "source:memory", "stateful", "structured"],
    },
    {
        "name": "File Info", "slug": "file-info",
        "description": "Utility for checking file existence, getting file metadata (size, modified time, type), and listing directory contents.",
        "category_slug": "file-operations", "provider": "System",
        "config_schema": {"type": "object", "properties": {
            "base_path": {"type": "string", "default": ".", "description": "Base path for file operations"},
            "allow_symlinks": {"type": "boolean", "default": True, "description": "Allow following symbolic links"},
            "max_depth": {"type": "integer", "default": 3, "minimum": 1, "maximum": 10,
                          "description": "Maximum directory traversal depth"},
        }},
        "timeout_ms": 5000, "icon": "file-info", "color": "#6F42C1",
        "tags": ["op:read", "purpose:development", "purpose:system", "source:local-file", "safe", "text"],
    },
    {
        "name": "Line Editor", "slug": "line-editor",
        "description": "Read and modify files line-by-line",
        "category_slug": "file-operations", "provider": "System",
        "config_schema": {"type": "object", "properties": {
            "default_encoding": {"type": "string", "default": "utf-8",
                                 "enum": ["utf-8", "ascii", "latin-1"],
                                 "description": "Default file encoding"},
            "create_backup": {"type": "boolean", "default": True, "description": "Create backup before modifications"},
            "max_line_length": {"type": "integer", "default": 10000, "minimum": 100, "maximum": 100000,
                                "description": "Maximum line length to process"},
        }},
        "timeout_ms": 10000, "icon": "edit", "color": "#E83E8C",
        "tags": ["op:read", "op:write", "op:insert", "op:replace", "op:delete",
                 "purpose:development", "source:local-file", "side-effects", "destructive", "text"],
    },
    {
        "name": "Text Tools", "slug": "text-tools",
        "description": "Text transformation and manipulation utilities",
        "category_slug": "utilities", "provider": "System",
        "config_schema": {"type": "object", "properties": {
            "default_operation": {"type": "string", "default": "uppercase",
                                  "enum": ["uppercase", "lowercase", "trim", "count",
                                           "format-json", "reverse", "title-case", "sentence-case"],
                                  "description": "Default transformation operation"},
            "preserve_whitespace": {"type": "boolean", "default": False,
                                    "description": "Preserve original whitespace in output"},
        }},
        "timeout_ms": 3000, "icon": "text", "color": "#6610F2",
        "tags": ["op:transform", "purpose:productivity", "purpose:development", "safe", "text"],
    },
    {
        "name": "SQLite Query", "slug": "sqlite-query",
        "description": "Read-only access to SQLite databases. Query the context index to find files by category, topic, or keyword.",
        "category_slug": "utilities", "provider": "System",
        "config_schema": {"type": "object", "properties": {
            "db_path": {"type": "string", "default": "/tmp/boss-agent-test/context_index.db",
                        "description": "Path to the SQLite database file"},
            "max_rows": {"type": "integer", "default": 50, "minimum": 1, "maximum": 200,
                         "description": "Maximum rows to return per query"},
        }, "required": ["db_path"]},
        "arguments_schema": {"type": "object", "properties": {
            "operation": {"type": "string", "enum": ["query", "schema", "categories", "search", "get", "stats"],
                          "description": "Operation to perform"},
            "sql": {"type": "string", "description": "SQL query (SELECT only)"},
            "keyword": {"type": "string", "description": "Search keyword"},
            "file_name": {"type": "string", "description": "File name to look up"},
            "category": {"type": "string", "description": "Category to filter by"},
        }, "required": ["operation"]},
        "timeout_ms": 30000, "icon": "database", "color": "#007BFF",
        "tags": ["op:read", "purpose:analysis", "source:database", "sandboxed", "text"],
    },
    {
        "name": "SQLite Manager", "slug": "sqlite-manager",
        "description": "Full CRUD SQLite database manager with safety controls. Insert, update, delete, and query data with audit logging.",
        "category_slug": "utilities", "provider": "System",
        "config_schema": {"type": "object", "properties": {
            "max_rows": {"type": "integer", "default": 50, "minimum": 1, "maximum": 500,
                         "description": "Maximum rows to return for read operations"},
            "max_affected_rows": {"type": "integer", "default": 100, "minimum": 1, "maximum": 1000,
                                  "description": "Maximum rows affected by write operations"},
            "require_where": {"type": "boolean", "default": True,
                              "description": "Reject UPDATE/DELETE without WHERE clause"},
            "blocked_tables": {"type": "array", "items": {"type": "string"}, "default": [],
                               "description": "Tables that cannot be modified"},
            "blocked_columns": {"type": "array", "items": {"type": "string"},
                                "default": ["password", "secret", "token", "api_key", "apikey", "key"],
                                "description": "Columns that cannot be written to"},
            "enable_audit_log": {"type": "boolean", "default": True,
                                 "description": "Enable audit logging for write operations"},
        }, "required": []},
        "arguments_schema": {"type": "object", "properties": {
            "operation": {"type": "string",
                          "enum": ["list_tables", "describe_table", "query", "search", "get",
                                   "stats", "insert", "update", "delete", "dry_run", "audit_log"],
                          "description": "Operation to perform"},
            "db_path": {"type": "string", "description": "Path to the SQLite database."},
            "sql": {"type": "string", "description": "Raw SQL for query, insert, update, delete, or dry_run"},
            "table": {"type": "string", "description": "Table name"},
            "keyword": {"type": "string", "description": "Search keyword"},
            "row_id": {"type": "integer", "description": "Row ID for get operation"},
            "values": {"type": "object", "description": "Key-value pairs for insert or update operations"},
            "where": {"type": "string", "description": "WHERE clause condition"},
            "limit": {"type": "integer", "description": "Result limit override"},
            "columns": {"type": "array", "items": {"type": "string"}, "description": "Column names for insert"},
        }, "required": ["operation"]},
        "timeout_ms": 30000, "icon": "database", "color": "#FF9800",
        "tags": ["op:read", "op:write", "purpose:database", "admin", "text"],
    },
]

SEED_TOOLS = [
    {
        "name": "Calculator", "slug": "calculator",
        "description": "Perform mathematical calculations and expressions",
        "category_slug": "math-calculation", "provider": "System",
        "config_schema": {"type": "object", "properties": {
            "precision": {"type": "integer", "default": 2, "minimum": 0, "maximum": 10,
                          "description": "Decimal precision for calculations"},
            "scientific_mode": {"type": "boolean", "default": False,
                                "description": "Enable scientific calculator functions"},
        }},
        "timeout_ms": 5000, "icon": "calculator", "color": "#28A745",
        "tags": ["math", "calculation", "utility"],
    },
    {
        "name": "Echo", "slug": "echo",
        "description": "Echo back input messages (useful for testing)",
        "category_slug": "communication", "provider": "System",
        "config_schema": {"type": "object", "properties": {
            "prefix": {"type": "string", "default": "Echo: ", "description": "Prefix to add before echoed message"},
            "uppercase": {"type": "boolean", "default": False, "description": "Convert message to uppercase"},
        }},
        "timeout_ms": 3000, "icon": "message", "color": "#17A2B8",
        "tags": ["communication", "test", "debug"],
    },
    {
        "name": "Web Search", "slug": "web-search",
        "description": "Search the web using search engine APIs",
        "category_slug": "web-internet", "provider": "Google", "type": "api",
        "config_schema": {"type": "object", "properties": {
            "api_key": {"type": "string", "format": "password", "description": "API key for search service"},
            "search_engine_id": {"type": "string", "description": "Custom search engine ID"},
            "max_results": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50,
                            "description": "Maximum number of results to return"},
            "safe_search": {"type": "boolean", "default": True, "description": "Enable safe search filtering"},
        }, "required": ["api_key", "search_engine_id"]},
        "endpoint": "https://www.googleapis.com/customsearch/v1",
        "timeout_ms": 30000, "requires_auth": True,
        "icon": "search", "color": "#4285F4",
        "tags": ["search", "web", "google", "api"],
        "is_builtin": False,
    },
    {
        "name": "File Reader", "slug": "file-reader",
        "description": "Read and analyze file contents",
        "category_slug": "file-operations", "provider": "System",
        "config_schema": {"type": "object", "properties": {
            "max_file_size": {"type": "integer", "default": 10485760, "minimum": 1024, "maximum": 104857600,
                              "description": "Maximum file size in bytes"},
            "allowed_extensions": {"type": "array", "items": {"type": "string"},
                                   "default": ["txt", "md", "json", "csv", "log"],
                                   "description": "Allowed file extensions"},
            "encoding": {"type": "string", "default": "utf-8", "enum": ["utf-8", "ascii", "latin-1"],
                         "description": "File encoding"},
        }},
        "timeout_ms": 10000, "icon": "file", "color": "#6F42C1",
        "tags": ["file", "read", "analysis"],
    },
    {
        "name": "Time", "slug": "time",
        "description": "Get current time and date information",
        "category_slug": "system-information", "provider": "System",
        "config_schema": {"type": "object", "properties": {
            "timezone": {"type": "string", "default": "UTC", "description": "Timezone for time display"},
            "format": {"type": "string", "default": "iso", "enum": ["iso", "human", "timestamp"],
                       "description": "Time format"},
            "include_date": {"type": "boolean", "default": True, "description": "Include date information"},
        }},
        "timeout_ms": 1000, "icon": "clock", "color": "#FD7E14",
        "tags": ["time", "date", "system"],
    },
    {
        "name": "Weather", "slug": "weather",
        "description": "Get weather information for locations",
        "category_slug": "utilities", "provider": "OpenWeatherMap", "type": "api",
        "config_schema": {"type": "object", "properties": {
            "api_key": {"type": "string", "format": "password", "description": "OpenWeatherMap API key"},
            "units": {"type": "string", "default": "metric", "enum": ["metric", "imperial", "standard"],
                      "description": "Temperature units"},
            "language": {"type": "string", "default": "en", "description": "Language for weather descriptions"},
        }, "required": ["api_key"]},
        "endpoint": "https://api.openweathermap.org/data/2.5/weather",
        "timeout_ms": 15000, "requires_auth": True,
        "icon": "cloud", "color": "#20C997",
        "tags": ["weather", "api", "location"],
        "is_builtin": False,
    },
]

INTROSPECTION_TOOLS = [
    {
        "name": "Log Reader", "slug": "log-reader",
        "description": "Read and analyze application logs with filtering and aggregation",
        "category_slug": "utilities", "provider": "system",
        "config_schema": {"type": "object", "properties": {
            "default_limit": {"type": "integer", "default": 100, "description": "Default number of logs to return"},
        }},
        "arguments_schema": {"type": "object", "properties": {
            "n": {"type": "integer", "default": 100, "description": "Number of recent logs to fetch (default: 100, max: 500)"},
            "level": {"type": "string", "enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                      "description": "Filter by log level"},
            "source": {"type": "string", "description": "Filter by log source"},
            "search": {"type": "string", "description": "Full-text search in log message"},
            "session_id": {"type": "string", "description": "Filter by session ID"},
            "analyze": {"type": "boolean", "default": False, "description": "Return analysis stats instead of raw logs"},
        }, "required": []},
        "icon": "search", "color": "#DC3545",
        "tags": ["op:read", "purpose:debug", "source:log-database", "safe", "introspection"],
    },
    {
        "name": "Config Inspector", "slug": "config-inspector",
        "description": "Inspect system manager configuration, modes, system state, and health",
        "category_slug": "system-information", "provider": "system",
        "config_schema": {"type": "object", "properties": {}},
        "arguments_schema": {"type": "object", "properties": {
            "target": {"type": "string", "enum": ["config", "config-history", "modes", "system-state", "health", "all"],
                       "description": "What to inspect"},
        }, "required": ["target"]},
        "icon": "settings", "color": "#007BFF",
        "tags": ["op:read", "purpose:debug", "source:system", "safe", "introspection"],
    },
    {
        "name": "State Dumper", "slug": "state-dumper",
        "description": "Dump session state including metadata, roles, timestamps, and optional message history",
        "category_slug": "system-information", "provider": "system",
        "config_schema": {"type": "object", "properties": {}},
        "arguments_schema": {"type": "object", "properties": {
            "session_id": {"type": "string", "description": "Session ID to dump state for"},
            "include_messages": {"type": "boolean", "default": False, "description": "Include full message history in dump"},
        }, "required": ["session_id"]},
        "icon": "database", "color": "#6F42C1",
        "tags": ["op:read", "purpose:debug", "source:session", "safe", "introspection"],
    },
    {
        "name": "Toggle Auto Diagnostics", "slug": "toggle-auto-diagnostics",
        "description": "Enable or disable the auto-diagnostics feature. When enabled, the system auto-triggers introspection mode on errors. Off by default to prevent recursive loops.",
        "category_slug": "system-information", "provider": "system",
        "config_schema": {"type": "object", "properties": {}},
        "arguments_schema": {"type": "object", "properties": {
            "enabled": {"type": "boolean", "description": "Set to true to enable auto-diagnostics, false to disable"},
        }, "required": ["enabled"]},
        "icon": "toggle-left", "color": "#28A745",
        "tags": ["op:write", "purpose:debug", "source:system", "introspection"],
    },
    {
        "name": "Run POST", "slug": "run-post",
        "description": "Run a Power-On Self Test (POST) to check system operational health across 10 checks in 4 tiers: connectivity, integrity, self-awareness, and peripheral systems. Returns structured PASS/WARN/FAIL results.",
        "category_slug": "system-information", "provider": "system",
        "config_schema": {"type": "object", "properties": {}},
        "arguments_schema": {"type": "object", "properties": {
            "checks": {
                "oneOf": [
                    {"type": "string", "enum": ["all", "connectivity", "self", "llm", "database", "api",
                                                "modes", "tools", "config", "tracker", "iterations", "auto-diag", "rag"]},
                    {"type": "array", "items": {"type": "string", "enum": ["all", "connectivity", "self", "llm",
                                                                           "database", "api", "modes", "tools",
                                                                           "config", "tracker", "iterations",
                                                                           "auto-diag", "rag"]}},
                ],
                "description": "Which checks to run. Use 'all' for all 10 checks. Default: 'all'.",
            },
        }},
        "icon": "activity", "color": "#28A745",
        "tags": ["op:read", "purpose:debug", "source:system", "safe", "introspection"],
    },
]

GUIDE_DEV_TOOLS = [
    {
        "name": "Documentation Reader", "slug": "doc-reader",
        "description": "Read markdown documentation files from the project. Supports TWO search modes: (1) keyword 'search' - finds files by filename or content match, and (2) 'semantic_search' - finds relevant document sections by meaning using vector similarity.",
        "category_slug": "file-operations", "provider": "System",
        "config_schema": {"type": "object", "properties": {
            "max_file_size": {"type": "integer", "default": 102400, "minimum": 1024, "maximum": 1048576,
                              "description": "Maximum file size in bytes (default: 100KB)"},
            "max_search_results": {"type": "integer", "default": 20, "minimum": 1, "maximum": 100,
                                   "description": "Maximum search results to return"},
            "embedding_provider": {"type": "string", "default": "ollama",
                                   "description": "Provider for generating embeddings"},
            "embedding_model": {"type": "string", "default": "nomic-embed-text",
                                "description": "Model name for generating embeddings"},
        }},
        "arguments_schema": {"type": "object", "properties": {
            "path": {"type": "string", "description": "Relative path to the documentation file"},
            "search": {"type": "string", "description": "Search term to find relevant docs"},
            "operation": {"type": "string", "enum": ["read", "search", "list", "semantic_search"],
                          "description": "Operation to perform"},
        }, "required": []},
        "timeout_ms": 30000, "icon": "book-open", "color": "#4A90D9",
        "tags": ["op:read", "purpose:development", "purpose:documentation", "source:local-file", "safe", "text"],
    },
    {
        "name": "Documentation Index", "slug": "doc-index",
        "description": "Quick lookup of available documentation topics by keyword. Returns a curated index of what topic areas exist.",
        "category_slug": "search-discovery", "provider": "System",
        "config_schema": {"type": "object", "properties": {
            "max_results": {"type": "integer", "default": 30, "minimum": 1, "maximum": 100,
                            "description": "Maximum number of results to return"},
        }},
        "arguments_schema": {"type": "object", "properties": {
            "topic": {"type": "string", "description": "Optional topic to filter by"},
            "search": {"type": "string", "description": "Optional search term across all topics"},
        }},
        "timeout_ms": 10000, "icon": "bookmark", "color": "#28A745",
        "tags": ["op:read", "purpose:development", "purpose:documentation", "safe", "text"],
    },
]

WEB_TOOLS = [
    {
        "name": "DuckDuckGo", "slug": "duckduckgo",
        "description": "Search the web for real-time information using DuckDuckGo (no API key needed)",
        "category_slug": "web-internet", "provider": "DuckDuckGo",
        "config_schema": {"type": "object", "properties": {
            "max_results": {"type": "integer", "default": 5, "minimum": 1, "maximum": 15,
                            "description": "Maximum number of search results to return"},
            "region": {"type": "string", "default": "wt-wt", "description": "Search region"},
            "time": {"type": "string", "enum": ["d", "w", "m", "y", ""], "default": "",
                     "description": "Time filter: day, week, month, year"},
            "safe_search": {"type": "string", "enum": ["on", "moderate", "off"], "default": "moderate",
                            "description": "Safe search level"},
        }, "required": []},
        "arguments_schema": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Search query string"},
            "max_results": {"type": "integer", "description": "Override max results for this request (1-15)"},
            "region": {"type": "string", "description": "Override region for this request"},
            "time": {"type": "string", "enum": ["d", "w", "m", "y", ""], "description": "Override time filter"},
        }, "required": ["query"]},
        "timeout_ms": 30000, "icon": "search", "color": "#DE5833",
        "tags": ["search", "web", "research", "duckduckgo", "free",
                 "op:read", "op:search", "purpose:research", "source:web", "safe", "text"],
    },
    {
        "name": "Jina Reader", "slug": "jina_reader",
        "description": "Fetch any URL and convert to LLM-friendly markdown (no API key needed)",
        "category_slug": "web-internet", "provider": "Jina AI",
        "config_schema": {"type": "object", "properties": {
            "format": {"type": "string", "enum": ["markdown", "text"], "default": "markdown",
                       "description": "Output format: 'markdown' (clean) or 'text' (plain)"},
        }, "required": []},
        "arguments_schema": {"type": "object", "properties": {
            "url": {"type": "string", "description": "The URL to fetch and extract content from"},
        }, "required": ["url"]},
        "timeout_ms": 30000, "icon": "globe", "color": "#4F46E5",
        "tags": ["fetch", "web", "extract", "reader", "jina", "free",
                 "op:read", "op:fetch", "purpose:research", "source:web", "safe", "text"],
    },
    {
        "name": "Tavily", "slug": "tavily",
        "description": "Search the web for real-time information using Tavily AI",
        "category_slug": "web-internet", "provider": "Tavily",
        "config_schema": {"type": "object", "properties": {
            "search_depth": {"type": "string", "enum": ["basic", "advanced"], "default": "basic",
                             "description": "Search depth: 'basic' for fast results, 'advanced' for comprehensive"},
            "max_results": {"type": "integer", "default": 5, "minimum": 1, "maximum": 10,
                            "description": "Maximum number of search results to return"},
            "include_images": {"type": "boolean", "default": False, "description": "Include image URLs in results"},
            "include_answer": {"type": "boolean", "default": False, "description": "Include AI-generated answer to query"},
            "include_domains": {"type": "array", "items": {"type": "string"}, "default": [],
                                "description": "Optional list of domains to include"},
            "exclude_domains": {"type": "array", "items": {"type": "string"}, "default": [],
                                "description": "Optional list of domains to exclude"},
        }, "required": []},
        "arguments_schema": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Search query string"},
            "search_depth": {"type": "string", "enum": ["basic", "advanced"],
                             "description": "Override search depth for this request"},
            "max_results": {"type": "integer", "description": "Override max results for this request (1-10)"},
        }, "required": ["query"]},
        "timeout_ms": 30000, "icon": "search", "color": "#3B82F6",
        "tags": ["search", "web", "research", "tavily", "api",
                 "op:read", "op:search", "purpose:research", "source:web", "safe", "text"],
    },
    {
        "name": "Wikipedia", "slug": "wikipedia",
        "description": "Search and retrieve Wikipedia articles",
        "category_slug": "web-internet", "provider": "Wikipedia",
        "config_schema": {"type": "object", "properties": {
            "language": {"type": "string", "default": "en", "description": "Wikipedia language code (e.g., 'en', 'es', 'fr')"},
            "max_results": {"type": "integer", "default": 5, "description": "Maximum search results to return"},
            "include_images": {"type": "boolean", "default": True, "description": "Include article thumbnails in results"},
        }},
        "arguments_schema": {"type": "object", "properties": {
            "operation": {"type": "string", "enum": ["search", "summary", "full", "random"],
                          "description": "Operation to perform: search, summary, full, or random"},
            "query": {"type": "string", "description": "Search query or article title"},
            "title": {"type": "string", "description": "Article title (for summary/full operations)"},
        }, "required": ["operation"]},
        "timeout_ms": 15000, "icon": "book-open", "color": "#000000",
        "tags": ["search", "research", "wikipedia", "knowledge",
                 "op:read", "op:search", "purpose:research", "source:wikipedia", "safe", "text"],
    },
]

# ==============================================================================
# Seeding Logic
# ==============================================================================

TOOL_GROUPS = {
    "builtin": {"categories": True, "tools": BUILTIN_TOOLS, "label": "Built-in Tools"},
    "seed": {"categories": True, "tools": SEED_TOOLS, "label": "Seed Tools"},
    "introspection": {"categories": False, "tools": INTROSPECTION_TOOLS, "label": "Introspection Tools"},
    "guide-dev": {"categories": False, "tools": GUIDE_DEV_TOOLS, "label": "Guide-Dev Tools"},
    "web": {"categories": False, "tools": WEB_TOOLS, "label": "Web Tools"},
}


async def seed_group(session: AsyncSessionLocal, group_name: str, group: dict) -> int:
    """Seed a group of tools. Returns count of tools created."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Seeding {group['label']}")
    logger.info(f"{'='*60}")

    # Build category lookup
    cat_slug_to_id = {}
    if group["categories"]:
        logger.info("\n1. Ensuring categories exist...")
        for cat_def in CATEGORIES:
            cat = await _get_or_create_category(session, **cat_def)
            cat_slug_to_id[cat.slug] = cat.id

    logger.info(f"\n2. Creating {group['label']} tools...")
    created = 0
    for tool_def in group["tools"]:
        # Resolve category_slug to category_id
        if "category_slug" in tool_def:
            slug = tool_def.pop("category_slug")

            if slug not in cat_slug_to_id:
                logger.warning(f"  Category '{slug}' not found for tool '{tool_def['slug']}'")
                continue
            tool_def["category_id"] = cat_slug_to_id[slug]

        tool = await _upsert_tool(session, tool_def)
        if tool:
            created += 1

    logger.info(f"\n  Created {created} new tool(s) in group '{group_name}'")
    return created


async def main():
    parser = argparse.ArgumentParser(description="Master tool seeding script")
    parser.add_argument(
        "--groups",
        default="all",
        help="Comma-separated list of groups to seed: builtin,seed,introspection,guide-dev,web (default: all)",
    )
    args = parser.parse_args()

    if args.groups == "all":
        groups_to_seed = list(TOOL_GROUPS.keys())
    else:
        groups_to_seed = [g.strip() for g in args.groups.split(",")]

    async with AsyncSessionLocal() as session:
        try:
            total_created = 0
            for group_name in groups_to_seed:
                if group_name not in TOOL_GROUPS:
                    logger.warning(f"Unknown group: {group_name}")
                    continue
                created = await seed_group(session, group_name, TOOL_GROUPS[group_name])
                total_created += created

            await session.commit()
            logger.info(f"\n{'='*60}")
            logger.info(f"Seeding Complete! Created {total_created} new tools total.")
            logger.info(f"{'='*60}")

        except Exception as e:
            await session.rollback()
            logger.error(f"Error during seeding: {e}")
            import traceback
            traceback.print_exc()
            raise


if __name__ == "__main__":
    asyncio.run(main())
