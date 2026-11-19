"""The agent self-state tools (2026-09-02, the shallow-agent build).

Two keyed write tools that let an agent maintain ITS OWN personal
state inside its workspace (agents/<key>/state.json — the per-agent
store, NOT central cogitate.db):

- update-sources — add/remove the agent's curated sources (URL-ish,
  validated), returns the VERIFIED new list read-back.
- update-state   — store a personal fact (location, timezone, …) with
  the source-of-truth note, returns the VERIFIED fact read-back.

THE SANDBOX: both tools declare needs_workspace=True — the execution
service injects the AGENT'S OWN workspace as config["base_path"] (the
2026-08-24 workspace-grant mechanism). Writes land in agents/<key>/,
never outside. A missing/empty base_path = the agent has no workspace
yet → the tool says so (provision first) — no silent fallback.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional


def _workspace_key(config: Dict[str, Any]) -> Optional[str]:
    """The workspace key from the injected base_path (the execution
    service's needs_workspace grant puts agents/<key> in base_path)."""
    base = config.get("base_path") or ""
    if not base:
        return None
    return Path(base).name


def _store(config: Dict[str, Any]):
    from app.domain.agents.agent_state import AgentStateStore
    base = config.get("base_path") or ""
    if not base:
        raise ValueError(
            "This agent has no workspace yet — provision it first "
            "(the write tools need the agent's own folder)."
        )
    # the injected base_path IS the agent's folder — pass it
    # directly (authoritative; never re-resolved elsewhere)
    return AgentStateStore(base_dir=base)


class UpdateSourcesTool:
    """update-sources — the agent maintains its own curated sources."""

    name = "Update Sources"
    slug = "update-sources"
    capability = "file-write"
    needs_workspace = True
    description = (
        "Add or remove sources from YOUR OWN curated sources list "
        "(stored in your workspace — the beat you report from). "
        "add: one or more URLs. remove: existing URLs. The tool "
        "validates URL-ish entries and returns the VERIFIED new list "
        "read-back — always confirm the returned list matches what "
        "you intended."
    )
    icon = "list"
    color = "#0EA5E9"
    tags = ["op:write", "purpose:self-state", "source:workspace", "sandboxed", "stateful"]
    config_schema: Dict[str, Any] = {"type": "object", "properties": {}, "required": []}
    arguments_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "remove"],
                "description": "add or remove the given sources",
            },
            "sources": {
                "type": "array",
                "items": {"type": "string"},
                "description": "The source URLs (scheme://host) to add or remove",
            },
        },
        "required": ["action", "sources"],
    }

    def __init__(self) -> None:
        pass

    async def execute(self, config: Optional[dict] = None, **kwargs: Any) -> dict[str, Any]:
        config = config or {}
        action = str(kwargs.get("action") or "").strip().lower()
        sources = kwargs.get("sources") or []
        if not isinstance(sources, list) or not sources:
            return {"success": False, "error": "sources must be a non-empty list of URLs"}
        try:
            store = _store(config)
            if action == "add":
                result = store.update_sources(sources)
            elif action == "remove":
                result = store.remove_sources(sources)
            else:
                return {"success": False, "error": f"Unknown action: {action!r} (add|remove)"}
        except ValueError as e:
            return {"success": False, "error": str(e), "error_type": "validation"}
        # the VERIFIED read-back (the verify-pattern: what WAS written)
        return {
            "success": True,
            "action": action,
            "sources": result["sources"],
            "count": len(result["sources"]),
            "verified": result["sources"],
        }


class UpdateStateTool:
    """update-state — the agent stores a personal fact (location…)."""

    name = "Update State"
    slug = "update-state"
    capability = "file-write"
    needs_workspace = True
    description = (
        "Store or remove ONE personal fact in your own state (kept in "
        "your workspace — e.g. your location, timezone, working "
        "hours). action 'set' (default): keys are short lowercase "
        "identifiers (e.g. 'location'); the value is the fact; say "
        "what told you (source: 'user', or the method — e.g. "
        "'ip-geolocation'). action 'remove': deletes the key entirely "
        "(cleanup after a test or a fact that no longer holds) — no "
        "value needed. Always returns the VERIFIED read-back."
    )
    icon = "save"
    color = "#8B5CF6"
    tags = ["op:write", "purpose:self-state", "source:workspace", "sandboxed", "stateful"]
    config_schema: Dict[str, Any] = {"type": "object", "properties": {}, "required": []}
    arguments_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["set", "remove"],
                "description": "set (default): store the fact; remove: delete the key entirely",
            },
            "key": {
                "type": "string",
                "description": "The fact key (lowercase letters/digits/._- e.g. 'location')",
            },
            "value": {
                "type": "string",
                "description": "The fact value (e.g. 'Omaha, Nebraska') — required for set, not for remove",
            },
            "source": {
                "type": "string",
                "description": "How you know this (default 'user'): user, ip-geolocation, other",
            },
        },
        "required": ["key"],
    }

    def __init__(self) -> None:
        pass

    async def execute(self, config: Optional[dict] = None, **kwargs: Any) -> dict[str, Any]:
        config = config or {}
        key = str(kwargs.get("key") or "").strip()
        action = str(kwargs.get("action") or "set").strip().lower() or "set"
        try:
            store = _store(config)
            if action == "remove":
                result = store.remove_fact(key)
                removed = key.lower()
                return {
                    "success": True,
                    "action": "remove",
                    "removed": removed,
                    "verified": result["facts"],
                }
            if action != "set":
                return {
                    "success": False,
                    "error": f"Unknown action: {action!r} (set|remove)",
                    "error_type": "validation",
                }
            value = str(kwargs.get("value") or "").strip()
            source = str(kwargs.get("source") or "user").strip() or "user"
            stored = store.set_fact(key, value, source=source)
        except ValueError as e:
            return {"success": False, "error": str(e), "error_type": "validation"}
        (fact_key, record) = next(iter(stored.items()))
        return {
            "success": True,
            "action": "set",
            "fact": {fact_key: record["value"]},
            "source": record["source"],
            "updated_at": record["updated_at"],
            "verified": {fact_key: record["value"]},
        }
