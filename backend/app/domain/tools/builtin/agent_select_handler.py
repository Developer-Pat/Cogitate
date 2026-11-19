"""Agent Select Tool — the ARM's read surface (Phase B).

Exa calls this to choose agents when composing orchestration
workflows. Wraps POST /agents/select (the selection service).
GRAS tier — selection is information; access is the grant
(the tooling upgrade's Phase C). This tool never grants.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)


class AgentSelectTool:
    """Select agents from the pool by criteria (the yellow pages)."""

    name = "Agent Select"
    slug = "agent-select"
    capability = "agent-admin"
    access_tier = "gras"  # read-only selection — the capability's
    # keyed default is overridden (selection is information)
    description = (
        "Select agents from the pool by criteria (capability, role, "
        "domain, depth, provider, spec, collective, min_tools) — the "
        "resource manager's way to choose agents for a job. Returns "
        "ranked matching agents with their capabilities and skills. "
        "Read-only: never grants or modifies agents."
    )
    config_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "base_url": {
                "type": "string",
                "description": "Backend API base URL",
                "default": "http://localhost:8000/api/v1",
            },
        },
    }
    arguments_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "capability": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Any-of required tool capabilities (e.g. ['web-search'])",
            },
            "role": {
                "type": "string",
                "description": "Curated role: writer, researcher, coder, analyst, designer, prompt-engineer, system-ops, generalist",
            },
            "domain": {
                "type": "string",
                "description": "Curated domain: fiction, nonfiction, math, physics, software, finance, art, research, engineering, general",
            },
            "depth": {
                "type": "string",
                "enum": ["deep", "shallow", "balanced"],
                "description": "Cognitive profile family",
            },
            "provider": {"type": "string", "description": "Provider name"},
            "spec": {
                "type": "string",
                "enum": ["local", "cloud"],
                "description": "Where the agent runs",
            },
            "collective": {
                "type": "string",
                "description": "Collective (group) name — narrows the pool, never routes",
            },
            "min_tools": {
                "type": "integer",
                "description": "Minimum enabled tool count",
            },
        },
        # all criteria are optional — empty = the whole pool
        # (discovery); explicit [] satisfies the contract audit
        "required": [],
    }
    icon = "magnifying-glass"
    color = "#3B82F6"
    tags = ["arm", "selection", "resource-manager"]

    async def execute(
        self, config: Dict[str, Any] | None = None, **kwargs: Any
    ) -> Dict[str, Any]:
        """Call the selection endpoint with the criteria."""
        base_url = (config or {}).get("base_url", "http://localhost:8000/api/v1")
        criteria = {
            k: v for k, v in kwargs.items()
            if v is not None and k not in ("config",)
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{base_url}/agents/select", json=criteria
                )
                resp.raise_for_status()
                data = resp.json()
            agents = data.get("agents", [])
            return {
                "success": True,
                "total": data.get("total", len(agents)),
                "agents": [
                    {k: v for k, v in a.items() if not k.startswith("_")}
                    for a in agents
                ],
            }
        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "error": f"Selection failed: {e.response.status_code} {e.response.text[:200]}",
            }
        except Exception as e:
            return {"success": False, "error": f"Selection failed: {str(e)}"}
