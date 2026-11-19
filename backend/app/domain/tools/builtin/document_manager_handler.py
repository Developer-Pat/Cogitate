"""Document Manager Tool — dedicated document CRUD for the system manager.

Handles document create, read, update, delete.
For reading documentation files, use doc-reader instead.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DOC_ENDPOINT = "/documents"


class DocumentManagerTool:
    """Dedicated document management tool for the system manager."""

    name = "Document Manager"
    slug = "document-manager"
    capability = "doc-admin"
    description = (
        "Create, read, update, delete, and list documentation entries. "
        "For reading documentation file content, use doc-reader instead."
    )
    config_schema = {
        "type": "object",
        "properties": {
            "base_url": {
                "type": "string",
                "description": "Backend API base URL",
                "default": "http://localhost:8000/api/v1",
            },
        },
    }
    arguments_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "read", "create", "update", "delete", "search"],
                "description": "Operation to perform",
            },
            "id": {
                "type": ["string", "integer"],
                "description": "Document ID (required for read/update/delete)",
            },
            "data": {
                "type": "object",
                "description": "Document data (required for create/update)",
            },
            "query": {
                "type": "string",
                "description": "Search query text",
            },
        },
        "required": ["action"],
    }
    icon = "file-text"
    color = "#F59E0B"
    tags = ["documents", "crud"]

    @classmethod
    async def execute(cls, config: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        base_url = config.get("base_url", "http://localhost:8000/api/v1")
        action = kwargs.get("action", "")
        entity_id = kwargs.get("id")
        data = kwargs.get("data")
        query = kwargs.get("query", "")

        try:
            async with httpx.AsyncClient(timeout=60.0, base_url=base_url) as client:

                if action == "list":
                    return cls._resp(await client.get(DOC_ENDPOINT))
                if action == "read":
                    if not entity_id: return {"success": False, "error": "id is required"}
                    return cls._resp(await client.get(f"{DOC_ENDPOINT}/{entity_id}"))
                if action == "create":
                    if not data: return {"success": False, "error": "data is required"}
                    return cls._resp(await client.post(DOC_ENDPOINT, json=data))
                if action == "update":
                    if not entity_id: return {"success": False, "error": "id is required"}
                    if not data: return {"success": False, "error": "data is required"}
                    return cls._resp(await client.put(f"{DOC_ENDPOINT}/{entity_id}", json=data))
                if action == "delete":
                    if not entity_id: return {"success": False, "error": "id is required"}
                    return cls._resp(await client.delete(f"{DOC_ENDPOINT}/{entity_id}"))
                if action == "search":
                    return cls._resp(await client.get(DOC_ENDPOINT, params={"q": query}))

            return {"success": False, "error": f"Unknown action '{action}'"}

        except httpx.ConnectError:
            return {"success": False, "error": f"Cannot connect to backend at {base_url}"}
        except Exception as e:
            logger.error(f"Document Manager error: {e}")
            return {"success": False, "error": str(e)}

    @classmethod
    def _resp(cls, response: httpx.Response) -> dict:
        if response.status_code >= 200 and response.status_code < 300:
            try:
                return {"success": True, "data": response.json(), "status_code": response.status_code}
            except Exception:
                return {"success": True, "data": response.text, "status_code": response.status_code}
        else:
            try: detail = response.json()
            except: detail = response.text
            return {"success": False, "error": f"API error {response.status_code}: {detail}", "status_code": response.status_code}
