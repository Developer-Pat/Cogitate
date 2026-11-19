"""Macro Manager Tool — dedicated macro CRUD operations for the system manager.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from app.core.config import Paths

logger = logging.getLogger(__name__)

# API endpoints for macro operations
MACRO_ENDPOINTS = {
    "macro-set": "/macros",
    "meta-topic": "/meta-topics",
}


class MacroManagerTool:
    """Dedicated macro management tool for the system manager."""

    name = "Macro Manager"
    slug = "macro-manager"
    capability = "macro-admin"
    description = (
        "Create, read, update, delete, list, and search meta-topics and "
        "macro-sets. This is the SINGLE tool for all macro operations. "
        "Manage macros directly with this tool."
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
                "enum": [
                    "list", "read", "create", "update", "delete", "search",
                    "get-expertise",
                ],
                "description": "Operation to perform",
            },
            "domain": {
                "type": "string",
                "enum": ["macro-set", "meta-topic"],
                "description": "Entity type: macro-set or meta-topic",
            },
            "id": {
                "type": ["string", "integer"],
                "description": "Entity ID (required for read/update/delete)",
            },
            "data": {
                "type": "object",
                "description": "Entity data (required for create/update)",
            },
            "filters": {
                "type": "object",
                "description": "Query filters for list/search",
            },
            "query": {
                "type": "string",
                "description": "Search query text",
            },
            "namespace": {
                "type": "string",
                "enum": ["system", "agent"],
                "description": "Namespace: system or agent",
            },
        },
        "required": ["action", "domain"],
    }
    icon = "keyboard"
    color = "#6366F1"
    tags = ["macros", "meta-topics", "macro-sets", "crud"]

    @classmethod
    async def execute(cls, config: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        """Execute a macro operation."""
        base_url = config.get("base_url", "http://localhost:8000/api/v1")
        action = kwargs.get("action", "")
        domain = kwargs.get("domain", "")
        entity_id = kwargs.get("id")
        data = kwargs.get("data")
        filters = kwargs.get("filters", {})
        query = kwargs.get("query", "")
        namespace = kwargs.get("namespace", "")

        # Handle get-expertise (returns the skill document)
        if action == "get-expertise":
            skill_path = (
                Paths.skills_dir
                / "system-manager" / "macro-manager-tool" / "SKILL.md"
            )
            if skill_path.exists():
                expertise = skill_path.read_text(encoding="utf-8")
                return {
                    "success": True,
                    "expertise": expertise,
                    "message": "Macro expertise document loaded. Use this tool directly for all macro operations.",
                }
            return {"success": False, "error": "Macro expertise document not found"}

        # Validate domain
        if domain not in MACRO_ENDPOINTS:
            return {"success": False, "error": f"Unknown domain '{domain}'. Use macro-set or meta-topic."}

        endpoint_base = MACRO_ENDPOINTS[domain]
        params = {}
        if namespace:
            params["namespace"] = namespace

        try:
            async with httpx.AsyncClient(timeout=60.0, base_url=base_url) as client:

                # LIST
                if action == "list":
                    if filters:
                        params.update(filters)
                    url = f"{endpoint_base}"
                    response = await client.get(url, params=params)
                    data = cls._handle_response(response)
                    logger.info(f"Macro Manager list {domain}: status={response.status_code}")
                    return data

                # READ
                if action == "read":
                    if not entity_id:
                        return {"success": False, "error": "id is required for read"}
                    url = f"{endpoint_base}/{entity_id}"
                    if namespace:
                        params["namespace"] = namespace
                    response = await client.get(url, params=params)
                    logger.info(f"Macro Manager read {domain} id={entity_id}: status={response.status_code}")
                    return cls._handle_response(response)

                # CREATE
                if action == "create":
                    if not data:
                        return {"success": False, "error": "data is required for create"}
                    url = f"{endpoint_base}"
                    if namespace:
                        data["namespace"] = namespace
                    response = await client.post(url, json=data)
                    logger.info(f"Macro Manager create {domain}: status={response.status_code}")
                    return cls._handle_response(response)

                # UPDATE
                if action == "update":
                    if not entity_id:
                        return {"success": False, "error": "id is required for update"}
                    if not data:
                        return {"success": False, "error": "data is required for update"}
                    url = f"{endpoint_base}/{entity_id}"
                    if namespace:
                        data["namespace"] = namespace
                    response = await client.put(url, json=data)
                    logger.info(f"Macro Manager update {domain} id={entity_id}: status={response.status_code}")
                    return cls._handle_response(response)

                # DELETE
                if action == "delete":
                    if not entity_id:
                        return {"success": False, "error": "id is required for delete"}
                    url = f"{endpoint_base}/{entity_id}"
                    if namespace:
                        params["namespace"] = namespace
                    response = await client.delete(url, params=params)
                    logger.info(f"Macro Manager delete {domain} id={entity_id}: status={response.status_code}")
                    return cls._handle_response(response)

                # SEARCH
                if action == "search":
                    url = f"{endpoint_base}/search"
                    if query:
                        params["q"] = query
                    response = await client.get(url, params=params)
                    logger.info(f"Macro Manager search {domain}: status={response.status_code}")
                    return cls._handle_response(response)

            return {"success": False, "error": f"Unknown action '{action}'"}

        except httpx.ConnectError:
            return {"success": False, "error": f"Cannot connect to backend at {base_url}"}
        except Exception as e:
            logger.error(f"Macro Manager error: {e}")
            return {"success": False, "error": str(e)}

    @classmethod
    def _handle_response(cls, response: httpx.Response) -> dict:
        """Parse an API response into the standard tool result format."""
        if response.status_code >= 200 and response.status_code < 300:
            try:
                result = response.json()
                return {
                    "success": True,
                    "data": result,
                    "status_code": response.status_code,
                }
            except Exception:
                return {
                    "success": True,
                    "data": response.text,
                    "status_code": response.status_code,
                }
        else:
            try:
                detail = response.json()
            except Exception:
                detail = response.text
            return {
                "success": False,
                "error": f"API error {response.status_code}: {detail}",
                "status_code": response.status_code,
            }
