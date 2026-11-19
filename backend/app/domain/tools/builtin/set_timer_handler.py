"""The set_timer tool — the EXA-TIMER (2026-08-28).

Exa's harness tool: set a one-shot timer, launch the long process,
finish the turn — the timer fires later and the pickup surfaces as a
confirmable message (the 08-13 doctrine: NO auto-fire).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.domain.tools.registry import BuiltinToolRegistrar


class SetTimerTool:
    """The tool: set_timer(duration_seconds, context)."""

    name = "Set Timer"
    slug = "set_timer"
    description = (
        "Set a one-shot timer. Use when you launch a long-running process "
        "(tests, sweeps, research) and want to pick up the results when it "
        "finishes: set the timer with a context describing what to check, "
        "finish your turn, and the timer will fire later — the pickup "
        "surfaces as a confirmable message (the user confirms, or your next "
        "ask carries the context)."
    )
    icon = "⏰"
    color = "#7c8cf8"
    tags = ["timer", "exa", "long-running"]
    capability = "event-publish"  # the expiry publishes the timer:{id}:fired bus-event
    config_schema: Dict[str, Any] = {}
    arguments_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "duration_seconds": {
                "type": "integer",
                "description": "Seconds until the timer fires (e.g. 180 for a 3-minute test run).",
            },
            "context": {
                "type": "string",
                "description": "What to pick up when the timer fires (e.g. 'the newest test run under data/test-runs/<ts>/').",
            },
        },
        "required": ["duration_seconds", "context"],
    }

    def __init__(self) -> None:
        pass

    async def execute(self, config: Optional[dict] = None, **kwargs: Any) -> dict[str, Any]:
        from app.domain.external_agent.timer_service import set_timer

        duration = int(kwargs.get("duration_seconds") or 0)
        context = str(kwargs.get("context") or "")
        if duration <= 0:
            return {"error": "duration_seconds must be positive"}
        result = await set_timer(duration, context)
        result["ok"] = True
        return result


def register_set_timer_tool(registrar: BuiltinToolRegistrar) -> None:
    """Register the set_timer tool (the idempotent pattern)."""
    tool = SetTimerTool()
    registrar.register_builtin(
        name=tool.name,
        slug=tool.slug,
        description=tool.description,
        handler=tool.execute,
        config_schema=tool.config_schema,
        icon=tool.icon,
        color=tool.color,
        tags=tool.tags,
        arguments_schema=tool.arguments_schema,
    )
