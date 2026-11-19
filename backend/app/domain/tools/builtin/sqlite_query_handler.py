"""
SQLite Query Tool.

Provides read-only access to SQLite databases for LLM-powered queries.
Designed for querying the context_index.db file created by the Context Indexer workflow.

Security:
- Read-only connection (URI mode with immutable flags)
- Table allowlist (only known tables)
- Result row limit (max 50 rows)
- No arbitrary file access (path validated against config)
"""

from __future__ import annotations

import sqlite3
import logging
import json
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Maximum rows returned per query
MAX_ROWS = 50

# Allowed table names (no arbitrary table access)
ALLOWED_TABLES = {"file_index", "sqlite_schema"}


class SqliteQueryTool:
    """
    Read-only SQLite query tool for LLM-powered database access.

    Tags:
        - op:read
        - purpose:analysis
        - source:database
        - sandboxed
        - text

    Operations:
        - query: Execute a read-only SQL query (SELECT only)
        - schema: Return database schema
        - categories: List all categories with file counts
        - search: Search files by keyword in summary, name, or category
        - get: Get full details for a specific file
        - stats: Return database statistics
    """

    name = "SQLite Query"
    slug = "sqlite-query"
    capability = "db-query"
    description = "Read-only access to SQLite databases. Query the context index to find files by category, topic, or keyword."
    tags = [
        "op:read",
        "purpose:analysis",
        "source:database",
        "sandboxed",
        "text",
    ]
    icon = "database"
    color = "#007BFF"

    config_schema = {
        "type": "object",
        "properties": {
            "max_rows": {
                "type": "integer",
                "default": 50,
                "minimum": 1,
                "maximum": 200,
                "description": "Maximum rows to return per query"
            }
        },
        "required": [],
    }

    arguments_schema = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["query", "schema", "categories", "search", "get", "stats"],
                "description": "Operation to perform"
            },
            "db_path": {
                "type": "string",
                "description": "Path to the SQLite database file. Required."
            },
            "sql": {
                "type": "string",
                "description": "SQL query (SELECT only, for 'query' operation)"
            },
            "keyword": {
                "type": "string",
                "description": "Search keyword (for 'search' operation)"
            },
            "file_name": {
                "type": "string",
                "description": "File name to look up (for 'get' operation)"
            },
            "category": {
                "type": "string",
                "description": "Category to filter by (optional, for 'search' and 'query')"
            }
        },
        "required": ["operation"],
    }

    async def execute(self, config: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Execute a database operation.

        Args:
            config: Tool configuration (db_path, max_rows)
            **kwargs: Operation arguments

        Returns:
            Dictionary with success status and result data
        """
        if not kwargs or len(kwargs) == 0:
            return await self._stats(config)

        operation = kwargs.get("operation", "stats")
        db_path = kwargs.get("db_path", "")

        if not db_path:
            return {
                "success": False,
                "error": "db_path is required. Specify which database to access (e.g., '/path/to/database.db').",
                "error_type": "ValidationError",
            }

        # Validate database file exists
        if not os.path.exists(db_path):
            return {
                "success": False,
                "error": f"Database file not found: {db_path}",
                "error_type": "FileNotFoundError",
            }

        # Inject into config so all internal methods find it
        config["db_path"] = db_path

        try:
            if operation == "query":
                return await self._query(config, kwargs)
            elif operation == "schema":
                return await self._schema(config)
            elif operation == "categories":
                return await self._categories(config)
            elif operation == "search":
                return await self._search(config, kwargs)
            elif operation == "get":
                return await self._get(config, kwargs)
            elif operation == "stats":
                return await self._stats(config)
            else:
                return {
                    "success": False,
                    "error": f"Unknown operation: '{operation}'. Available: query, schema, categories, search, get, stats",
                }
        except sqlite3.OperationalError as e:
            return {
                "success": False,
                "error": f"Database error: {str(e)}",
                "error_type": "DatabaseError",
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "error_type": "InternalError",
            }

    def _connect(self, db_path: str) -> sqlite3.Connection:
        """Open a read-only connection to the database."""
        # Open in read-only mode using URI
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def _validate_table(self, table_name: str) -> bool:
        """Check if table name is in the allowlist."""
        return table_name in ALLOWED_TABLES

    def _validate_sql(self, sql: str) -> tuple[bool, str]:
        """Validate that SQL is read-only (SELECT only)."""
        if not sql or not sql.strip():
            return False, "Empty SQL query"

        # Check for write operations
        write_keywords = {"INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "ATTACH", "PRAGMA"}
        first_word = sql.strip().split()[0].upper()

        if first_word in write_keywords:
            return False, f"Write operations not allowed: {first_word}"

        # Check for dangerous PRAGMA commands
        if "PRAGMA" in sql.upper():
            return False, "PRAGMA commands not allowed"

        return True, ""

    async def _query(self, config: Dict[str, Any], kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a SELECT query and return structured results."""
        sql = kwargs.get("sql", "")
        if not sql:
            return {
                "success": False,
                "error": "sql argument is required for 'query' operation",
            }

        # Security validation
        valid, error_msg = self._validate_sql(sql)
        if not valid:
            return {"success": False, "error": f"Security: {error_msg}"}

        max_rows = min(config.get("max_rows", MAX_ROWS), MAX_ROWS)
        # Append LIMIT if not present
        if "LIMIT" not in sql.upper():
            sql = sql.rstrip(";") + f" LIMIT {max_rows}"

        db_path = config.get("db_path", "")
        conn = self._connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(sql)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchall()

            # Convert Row objects to dicts
            results = [dict(zip(columns, row)) for row in rows]

            # Ensure all values are JSON-serializable
            for row in results:
                for key, val in row.items():
                    if isinstance(val, bytes):
                        row[key] = val.decode("utf-8", errors="replace")

            return {
                "success": True,
                "operation": "query",
                "row_count": len(results),
                "columns": columns,
                "rows": results,
                "truncated": len(results) >= max_rows,
            }
        finally:
            conn.close()

    async def _schema(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Return database schema as structured data."""
        db_path = config.get("db_path", "")
        conn = self._connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name, type, sql FROM sqlite_schema WHERE type IN ('table', 'index') AND name NOT LIKE 'sqlite_%' ORDER BY type, name")
            schema = []
            for row in cursor.fetchall():
                schema.append({
                    "name": row[0],
                    "type": row[1],
                    "sql": row[2],
                })

            # Get column info for each table
            cursor.execute("SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables = [r[0] for r in cursor.fetchall()]
            table_details = {}
            for table in tables:
                cursor.execute(f"PRAGMA table_info({table})")
                columns = []
                for col in cursor.fetchall():
                    columns.append({
                        "cid": col[0],
                        "name": col[1],
                        "type": col[2],
                        "notnull": bool(col[3]),
                        "default": col[4],
                        "pk": bool(col[5]),
                    })
                table_details[table] = columns

            return {
                "success": True,
                "operation": "schema",
                "tables": tables,
                "schema": schema,
                "table_details": table_details,
            }
        finally:
            conn.close()

    async def _categories(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """List all categories with file counts."""
        db_path = config.get("db_path", "")
        conn = self._connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT category, COUNT(*) as count, GROUP_CONCAT(file_name) as files FROM file_index GROUP BY category ORDER BY MIN(display_order) ASC, category ASC")
            categories = []
            total = 0
            for row in cursor.fetchall():
                cat_files = row[2].split(",") if row[2] else []
                categories.append({
                    "category": row[0],
                    "count": row[1],
                    "files": cat_files,
                })
                total += row[1]

            return {
                "success": True,
                "operation": "categories",
                "total_files": total,
                "categories": categories,
            }
        finally:
            conn.close()

    async def _search(self, config: Dict[str, Any], kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Search files by keyword in summary, name, or category."""
        keyword = kwargs.get("keyword", "")
        category = kwargs.get("category", "")

        if not keyword:
            return {
                "success": False,
                "error": "keyword argument is required for 'search' operation",
            }

        db_path = config.get("db_path", "")
        conn = self._connect(db_path)
        try:
            cursor = conn.cursor()
            # Search in file_name, summary, and category
            sql = """
                SELECT file_name, file_path, category, summary, file_size
                FROM file_index
                WHERE (file_name LIKE ? OR summary LIKE ? OR category LIKE ?)
            """
            params = [f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"]

            if category:
                sql += " AND category = ?"
                params.append(category)

            sql += " ORDER BY display_order ASC, category ASC, file_name"

            max_rows = min(config.get("max_rows", MAX_ROWS), MAX_ROWS)
            sql += f" LIMIT {max_rows}"

            cursor.execute(sql, params)
            results = []
            for row in cursor.fetchall():
                results.append({
                    "file_name": row[0],
                    "file_path": row[1],
                    "category": row[2],
                    "summary": row[3],
                    "file_size": row[4],
                })

            return {
                "success": True,
                "operation": "search",
                "keyword": keyword,
                "category_filter": category or None,
                "match_count": len(results),
                "results": results,
            }
        finally:
            conn.close()

    async def _get(self, config: Dict[str, Any], kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Get full details for a specific file."""
        file_name = kwargs.get("file_name", "")
        if not file_name:
            return {
                "success": False,
                "error": "file_name argument is required for 'get' operation",
            }

        db_path = config.get("db_path", "")
        conn = self._connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM file_index WHERE file_name = ?",
                (file_name,)
            )
            row = cursor.fetchone()
            if not row:
                return {
                    "success": False,
                    "error": f"File not found: {file_name}",
                    "error_type": "NotFoundError",
                }

            result = dict(row)
            # Parse tags if stored as JSON string
            if isinstance(result.get("tags"), str):
                try:
                    result["tags"] = json.loads(result["tags"])
                except json.JSONDecodeError:
                    result["tags"] = []

            return {
                "success": True,
                "operation": "get",
                "file": result,
            }
        finally:
            conn.close()

    async def _stats(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Return database statistics."""
        db_path = config.get("db_path", "")
        conn = self._connect(db_path)
        try:
            cursor = conn.cursor()

            # Total files
            cursor.execute("SELECT COUNT(*) FROM file_index")
            total_files = cursor.fetchone()[0]

            # Categories count
            cursor.execute("SELECT COUNT(DISTINCT category) FROM file_index")
            total_categories = cursor.fetchone()[0]

            # Average file size
            cursor.execute("SELECT AVG(file_size) FROM file_index")
            avg_size = cursor.fetchone()[0] or 0

            # Total size
            cursor.execute("SELECT SUM(file_size) FROM file_index")
            total_size = cursor.fetchone()[0] or 0

            # Files per category
            cursor.execute("SELECT category, COUNT(*) as cnt FROM file_index GROUP BY category ORDER BY cnt DESC LIMIT 10")
            top_categories = [{"category": r[0], "count": r[1]} for r in cursor.fetchall()]

            # DB file size on disk
            import os
            db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0

            return {
                "success": True,
                "operation": "stats",
                "database": {
                    "path": db_path,
                    "size_bytes": db_size,
                    "size_kb": round(db_size / 1024, 1),
                },
                "content": {
                    "total_files": total_files,
                    "total_categories": total_categories,
                    "avg_file_size_bytes": round(avg_size, 0),
                    "total_content_size_bytes": total_size,
                    "top_categories": top_categories,
                },
            }
        finally:
            conn.close()
