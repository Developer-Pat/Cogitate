"""
Publish Tool Handler (Phase D, 2026-08-24).

Agents become PUBLISHERS through the standard surface: they
announce events ("batch 3 done, 12 rows", "finding X", progress)
onto the app's event bus. The SSE stream (Phase B) carries the
events to the frontend; monitors/consumers can subscribe.

GRAS (announce-only): publishing an event is a side-effect-free
write to the bus — no read surface, no tool grants needed. The
topic conventions live in the messaging domain (namespace:sub:event).

The payload is validated: the topic must be a string matching the
convention (namespace:...), the payload a JSON-serializable dict.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

# the allowed topic namespaces (an agent must not publish anywhere)
_ALLOWED_NAMESPACES = ("workflow:", "batch:", "agent:", "the_boss:", "notify:", "system:")


class PublishTool:
    """
    Publish an event onto the application's event bus.

    Tags:
        - op:write
        - purpose:system
        - safe
        - text

    Operations:
        - publish: emit {topic, payload} onto the bus
    """

    name = "Publish"
    slug = "publish"
    capability = "event-publish"
    description = (
        "Publish an event onto the application's event bus. Agents use "
        "this to announce progress, findings, or status to subscribers "
        "(the SSE stream, monitors, the toaster). Topics follow the "
        "namespace:sub:event convention (e.g. 'batch:3:done', "
        "'agent:7:published', 'notify:task-complete'). The payload is "
        "a JSON-serializable object."
    )
    tags = [
        "op:write",
        "purpose:system",
        "safe",
        "text",
    ]
    icon = "publish"
    color = "#6C63FF"

    arguments_schema = {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "The event topic (namespace:sub:event).",
            },
            "payload": {
                "type": "object",
                "description": "The event payload (JSON-serializable).",
            },
        },
        "required": ["topic"],
    }

    config_schema = {"type": "object", "properties": {}}

    async def execute(self, config: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        try:
            args = kwargs.get("arguments") or kwargs.get("args") or {}
            topic = str(args.get("topic", "")).strip()
            payload = args.get("payload") or {}

            if not topic:
                return {"success": False, "error": "topic is required"}
            if not topic.startswith(_ALLOWED_NAMESPACES):
                return {
                    "success": False,
                    "error": (
                        f"topic must start with one of {_ALLOWED_NAMESPACES} "
                        f"(got {topic!r})"
                    ),
                }
            if not isinstance(payload, dict):
                return {"success": False, "error": "payload must be a dict"}
            # JSON-serializability check (announce-only — no silent drops)
            json.dumps(payload)

            from app.domain.messaging.services import publish

            publish(topic, payload)
            logger.info(f"  📤 Publish tool: {topic}")
            return {"success": True, "topic": topic}
        except Exception as e:
            logger.error(f"  ❌ Publish tool failed: {e}")
            return {"success": False, "error": str(e)[:300]}
