"""
Workflow Manager Tool — CRUD operations for workflows.
"""

from __future__ import annotations
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class WorkflowManagerTool:
    name = "Workflow Manager"
    slug = "workflow-manager"
    capability = "workflow-admin"
    description = "Create, read, update, delete, and manage workflows in the system."
    tags = ["op:write", "op:read", "purpose:admin", "system", "safe"]

    config_schema = {"type": "object", "properties": {}}

    arguments_schema = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["list", "get", "create", "update", "delete", "activate", "deactivate"],
                "description": "Operation to perform on workflows",
            },
            "workflow_id": {
                "type": "integer",
                "description": "Workflow ID (required for get/update/delete/activate/deactivate)",
            },
            "name": {
                "type": "string",
                "description": "Workflow name (required for create/update)",
            },
            "description": {
                "type": "string",
                "description": "Workflow description",
            },
        },
        "required": ["operation"],
    }

    async def execute(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Execute a workflow management operation."""
        import httpx
        base = "http://localhost:8000/api/v1/workflows"

        try:
            if operation == "list":
                async with httpx.AsyncClient() as c:
                    resp = await c.get(base, timeout=10)
                    return {"success": True, "data": resp.json()}

            elif operation == "get":
                wid = kwargs.get("workflow_id")
                if not wid:
                    return {"success": False, "error": "workflow_id required"}
                async with httpx.AsyncClient() as c:
                    resp = await c.get(f"{base}/{wid}", timeout=10)
                    return {"success": resp.status_code == 200, "data": resp.json() if resp.status_code == 200 else resp.text}

            elif operation == "create":
                payload = {"name": kwargs.get("name"), "description": kwargs.get("description", "")}
                async with httpx.AsyncClient() as c:
                    resp = await c.post(base, json=payload, timeout=10)
                    return {"success": resp.status_code == 201, "data": resp.json() if resp.status_code == 201 else resp.text}

            elif operation == "update":
                wid = kwargs.get("workflow_id")
                if not wid:
                    return {"success": False, "error": "workflow_id required"}
                payload = {k: v for k, v in kwargs.items() if k in ("name", "description") and v is not None}
                async with httpx.AsyncClient() as c:
                    resp = await c.put(f"{base}/{wid}", json=payload, timeout=10)
                    return {"success": resp.status_code == 200, "data": resp.json() if resp.status_code == 200 else resp.text}

            elif operation == "delete":
                wid = kwargs.get("workflow_id")
                if not wid:
                    return {"success": False, "error": "workflow_id required"}
                async with httpx.AsyncClient() as c:
                    resp = await c.delete(f"{base}/{wid}", timeout=10)
                    return {"success": resp.status_code == 204}

            elif operation in ("activate", "deactivate"):
                wid = kwargs.get("workflow_id")
                if not wid:
                    return {"success": False, "error": "workflow_id required"}
                is_active = operation == "activate"
                async with httpx.AsyncClient() as c:
                    resp = await c.patch(f"{base}/{wid}", json={"is_active": is_active}, timeout=10)
                    return {"success": resp.status_code == 200, "data": resp.json() if resp.status_code == 200 else resp.text}

            return {"success": False, "error": f"Unknown operation: {operation}"}

        except Exception as e:
            logger.error("Workflow manager error: %s", e)
            return {"success": False, "error": str(e)}
