"""
System Diagnostics Tool — Health checks, logs, and system status.
"""

from __future__ import annotations
import logging
from typing import Any, Dict

# The canonical root — imported from config (never recomputed; the
# pathing discipline 2026-08-17).

logger = logging.getLogger(__name__)


class SystemDiagnosticsTool:
    name = "System Diagnostics"
    slug = "system-diagnostics"
    capability = "system-diag"
    description = "Check system health, view logs, and get diagnostics information."
    tags = ["op:read", "purpose:admin", "system", "safe"]

    config_schema = {"type": "object", "properties": {}}

    arguments_schema = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["health", "logs", "stats", "check-provider"],
                "description": "Diagnostic operation to perform",
            },
            "provider_id": {
                "type": "integer",
                "description": "Provider ID for check-provider operation",
            },
            "limit": {
                "type": "integer",
                "default": 20,
                "description": "Number of log lines to return (logs operation only)",
            },
        },
        "required": ["operation"],
    }

    async def execute(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Execute a diagnostic operation."""
        import httpx

        try:
            if operation == "health":
                async with httpx.AsyncClient() as c:
                    resp = await c.get("http://localhost:8000/api/v1/health", timeout=10)
                    return {"success": True, "data": resp.json()}

            elif operation == "logs":
                limit = kwargs.get("limit", 20)
                from app.core.config import Paths, get_settings

                log_path = str(Paths.from_settings(get_settings()).logs_dir / "app.log")
                try:
                    with open(log_path) as f:
                        lines = f.readlines()[-limit:]
                    return {"success": True, "data": {"lines": lines, "file": log_path, "count": len(lines)}}
                except Exception as e:
                    return {"success": False, "error": f"Failed to read logs: {e}"}

            elif operation == "stats":
                import sqlite3
                from app.core.config import Paths, get_settings
                db_path = str(Paths.from_settings(get_settings()).shared_db)
                stats = {}
                try:
                    conn = sqlite3.connect(db_path)
                    for table in ["agents", "chat_sessions", "tools", "workflows", "providers"]:
                        try:
                            cur = conn.execute(f"SELECT COUNT(*) FROM {table}")
                            stats[table] = cur.fetchone()[0]
                        except Exception:
                            stats[table] = "N/A"
                    conn.close()
                    return {"success": True, "data": stats}
                except Exception as e:
                    return {"success": False, "error": f"Failed to get stats: {e}"}

            elif operation == "check-provider":
                pid = kwargs.get("provider_id")
                if not pid:
                    return {"success": False, "error": "provider_id required"}
                async with httpx.AsyncClient() as c:
                    resp = await c.post(f"http://localhost:8000/api/v1/providers/config/{pid}/test", timeout=30)
                    return {"success": resp.status_code == 200, "data": resp.json() if resp.status_code == 200 else resp.text}

            return {"success": False, "error": f"Unknown operation: {operation}"}

        except Exception as e:
            logger.error("System diagnostics error: %s", e)
            return {"success": False, "error": str(e)}
