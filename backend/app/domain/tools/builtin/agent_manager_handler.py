"""Agent Manager Tool — dedicated agent CRUD operations for the system manager.

Handles all agent operations directly.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

AGENT_ENDPOINTS = {
    "agent": "/agents",
    "agent-template": "/agents/templates",
    "agent-list": "/agent-lists",
    "agent-chat": "/chat",
}


class AgentManagerTool:
    """Dedicated agent management tool for the system manager."""

    name = "Agent Manager"
    slug = "agent-manager"
    capability = "agent-admin"
    description = (
        "Create, read, update, delete, list, search agents, agent templates, "
        "and agent lists. This is the SINGLE tool for all agent operations. "
        "Manage agents directly with this tool."
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
                    "member-list", "member-add", "member-remove",
                    "tool-add", "tool-remove", "tool-list",
                ],
                "description": "Operation to perform",
            },
            "domain": {
                "type": "string",
                "enum": ["agent", "agent-template", "agent-list", "agent-chat"],
                "description": "Entity type: agent, agent-template, agent-list, or agent-chat",
            },
            "id": {
                "type": ["string", "integer"],
                "description": "Entity ID (required for read/update/delete)",
            },
            "data": {
                "type": "object",
                "description": "Entity data (required for create/update)",
            },
            "query": {
                "type": "string",
                "description": "Search query text",
            },
            "target_agent_id": {
                "type": "integer",
                "description": "Target agent ID for delegation",
            },
            "task": {
                "type": "string",
                "description": "Task description for delegation",
            },
        },
        "required": ["action", "domain"],
    }
    icon = "bot"
    color = "#10B981"
    tags = ["agents", "templates", "agent-lists", "crud"]

    @classmethod
    async def execute(cls, config: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        """Execute an agent operation."""
        base_url = config.get("base_url", "http://localhost:8000/api/v1")
        action = kwargs.get("action", "")
        domain = kwargs.get("domain", "")
        entity_id = kwargs.get("id")
        data = kwargs.get("data")
        query = kwargs.get("query", "")
        target_agent_id = kwargs.get("target_agent_id")
        task = kwargs.get("task")

        if domain not in AGENT_ENDPOINTS:
            return {"success": False, "error": f"Unknown domain '{domain}'. This tool handles: agent, agent-template, agent-list, agent-chat. For meta-topic or macro-set operations, use macro-manager."}

        endpoint_base = AGENT_ENDPOINTS[domain]

        try:
            async with httpx.AsyncClient(timeout=60.0, base_url=base_url) as client:

                # LIST
                if action == "list":
                    response = await client.get(endpoint_base)
                    return cls._handle_response(response)

                # READ
                if action == "read":
                    if not entity_id:
                        return {"success": False, "error": "id is required for read"}
                    response = await client.get(f"{endpoint_base}/{entity_id}")
                    return cls._handle_response(response)

                # CREATE
                if action == "create":
                    if not data:
                        return {"success": False, "error": "data is required for create"}
                    response = await client.post(endpoint_base, json=data)
                    return cls._handle_response(response)

                # UPDATE
                if action == "update":
                    if not entity_id:
                        return {"success": False, "error": "id is required for update"}
                    if not data:
                        return {"success": False, "error": "data is required for update"}
                    response = await client.put(f"{endpoint_base}/{entity_id}", json=data)
                    return cls._handle_response(response)

                # DELETE
                if action == "delete":
                    if not entity_id:
                        return {"success": False, "error": "id is required for delete"}
                    response = await client.delete(f"{endpoint_base}/{entity_id}")
                    return cls._handle_response(response)

                # SEARCH
                if action == "search":
                    params = {"q": query} if query else {}
                    response = await client.get(f"{endpoint_base}", params=params)
                    return cls._handle_response(response)

                # AGENT-LIST sub-ops
                if domain == "agent-list":
                    if action == "member-list":
                        return cls._handle_response(await client.get(f"{endpoint_base}/{entity_id}/members"))
                    if action == "member-add":
                        return cls._handle_response(await client.post(f"{endpoint_base}/{entity_id}/members", json=data))
                    if action == "member-remove":
                        return cls._handle_response(await client.delete(f"{endpoint_base}/{entity_id}/members/{entity_id}"))

                # TOOL sub-ops
                if domain == "agent":
                    if action == "tool-list":
                        return cls._handle_response(await client.get(f"{endpoint_base}/{entity_id}/tools"))
                    if action == "tool-add":
                        return cls._handle_response(await client.post(f"{endpoint_base}/{entity_id}/tools", json=data))
                    if action == "tool-remove":
                        return cls._handle_response(await client.delete(f"{endpoint_base}/{entity_id}/tools/{entity_id}"))

                # DELEGATION
                if domain == "agent-chat" and action == "delegate":
                    if not target_agent_id:
                        return {"success": False, "error": "target_agent_id is required for delegation"}
                    payload = {"agent_id": target_agent_id, "task": task or "No task specified"}
                    response = await client.post("/chat", json=payload)
                    return cls._handle_response(response)

            return {"success": False, "error": f"Unknown action '{action}' for domain '{domain}'"}

        except httpx.ConnectError:
            return {"success": False, "error": f"Cannot connect to backend at {base_url}"}
        except Exception as e:
            logger.error(f"Agent Manager error: {e}")
            return {"success": False, "error": str(e)}

    @classmethod
    def _handle_response(cls, response: httpx.Response) -> dict:
        if response.status_code >= 200 and response.status_code < 300:
            try:
                return {"success": True, "data": response.json(), "status_code": response.status_code}
            except Exception:
                return {"success": True, "data": response.text, "status_code": response.status_code}
        else:
            try:
                detail = response.json()
            except Exception:
                detail = response.text
            return {"success": False, "error": f"API error {response.status_code}: {detail}", "status_code": response.status_code}
