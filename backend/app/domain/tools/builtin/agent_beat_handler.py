"""The agent's beat-sheet tools (2026-09-10, the News Team arc).

One write tool that lets an agent edit ITS OWN beat sheet in its
workspace (`agents/<key>/news-beats/<name>.md`) while the user talks:

    user: add Janet Yellen to the people of interest
    user: let's drop economics from the subjects
    user: add this outlet to the sources

THE SANDBOX: needs_workspace=True — the execution service injects the
AGENT'S OWN workspace as config["base_path"] (the workspace-grant
mechanism, same as update-state / update-sources). A missing/empty
base_path means the agent has no workspace yet → the tool says so (no
silent fallback).

Every call returns the VERIFIED read-back of the list it touched, read
back from disk — the agent must confirm what it reports matches, and a
remove that matches nothing is a loud error rather than a quiet no-op.
"""
from __future__ import annotations

from typing import Any, Dict, Optional


def _store(config: Dict[str, Any]):
    from app.domain.agents.agent_beats import AgentBeatStore
    base = config.get("base_path") or ""
    if not base:
        raise ValueError(
            "This agent has no workspace yet — provision it first "
            "(the write tools need the agent's own folder)."
        )
    # the injected base_path IS the agent's folder — pass it directly
    # (authoritative; never re-resolved elsewhere)
    return AgentBeatStore(base_dir=base)


class UpdateBeatTool:
    """update-beat — the agent co-authors its own beat sheet."""

    name = "Update Beat"
    slug = "update-beat"
    capability = "file-write"
    needs_workspace = True
    description = (
        "Edit YOUR OWN beat sheet — the news beat you report from "
        "(news-beats/ in your workspace). Use it the moment the user "
        "asks you to change your beat: 'add <someone> to the people of "
        "interest', 'drop <topic> from the subjects', 'add this outlet "
        "to my sources'. list: subjects | people | places | sources; "
        "action: add | remove; items: the text to add or remove. A "
        "remove is an EXACT match — if it matches nothing the tool "
        "refuses, so never report a change that was not confirmed. "
        "Always returns the VERIFIED list read back from disk."
    )
    icon = "list"
    color = "#F59E0B"
    tags = ["op:write", "purpose:self-state", "source:workspace", "sandboxed", "stateful"]
    config_schema: Dict[str, Any] = {"type": "object", "properties": {}, "required": []}
    arguments_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "beat": {
                "type": "string",
                "description": (
                    "Which beat sheet (its name, e.g. 'middle-east-vox'). "
                    "Optional when you have exactly one."
                ),
            },
            "list": {
                "type": "string",
                "enum": ["subjects", "people", "places", "sources"],
                "description": "Which list to edit (subjects/people/places are the interests)",
            },
            "action": {
                "type": "string",
                "enum": ["add", "remove"],
                "description": "add the given items, or remove them",
            },
            "items": {
                "type": "array",
                "items": {"type": "string"},
                "description": "The items to add or remove (exact text for a remove)",
            },
        },
        "required": ["list", "action", "items"],
    }

    def __init__(self) -> None:
        pass

    async def execute(self, config: Optional[dict] = None, **kwargs: Any) -> dict[str, Any]:
        config = config or {}
        list_name = str(kwargs.get("list") or "").strip().lower()
        action = str(kwargs.get("action") or "").strip().lower()
        items = kwargs.get("items") or []
        beat = kwargs.get("beat") or None

        if not isinstance(items, list) or not items:
            return {
                "success": False,
                "error": "items must be a non-empty list of strings",
                "error_type": "validation",
            }
        if action not in ("add", "remove"):
            return {
                "success": False,
                "error": f"Unknown action: {action!r} (add|remove)",
                "error_type": "validation",
            }

        try:
            store = _store(config)
            if action == "add":
                result = store.add_items(beat, list_name, items)
            else:
                result = store.remove_items(beat, list_name, items)
        except ValueError as e:
            return {"success": False, "error": str(e), "error_type": "validation"}

        # the VERIFIED read-back (the verify-pattern: what IS on disk now)
        return {
            "success": True,
            "beat": result["beat"],
            "list": result["list"],
            "action": result["action"],
            **{k: v for k, v in result.items() if k in ("items", "sources", "count")},
            "verified": result["verified"],
        }
