"""The send_notification tool (2026-08-30, the _23 F5 build).

Exa's purpose-built "send the user a message" affordance — the
wrapper around the messaging publish with the NOTIFICATION shape
(title, message, type, sticky): the toast + the center record + the
class-sound (the F4 per-class wavs — success plays the run-complete
bell, warning the alert, error the emergency; info stays silent;
sticky stays until dismissed + the sound cycles every 2s).

The general Publish tool is the hammer for arbitrary topics; this is
the announcement surface the agent reaches for to notify the user.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _safe_link(url: str) -> bool:
    """THE LINK GATE (2026-08-30, the user's 'talk to me' ask): the
    toast's action link must be an app route (starting with /) or an
    http(s) URL — no javascript: or other schemes."""
    u = url.strip()
    return u.startswith("/") or u.startswith(("http://", "https://"))


class SendNotificationTool:
    """The tool: send_notification(title, message?, type?, sticky?)."""

    name = "Send Notification"
    slug = "send_notification"
    description = (
        "Send a notification to the user: a toast appears (with the "
        "class-specific sound — success plays the run-complete bell, "
        "warning the alert, error the emergency) and the message is "
        "recorded in the message center. Use this to announce task "
        "completions, findings, or things the user should know — "
        "'the workflow finished', 'your report is ready', 'the sweep "
        "found issues'. A sticky notification stays on screen until "
        "dismissed and repeats its sound every 2 seconds (for the "
        "attention-critical cases)."
    )
    icon = "🔔"
    color = "#7c8cf8"
    tags = ["notify", "exa", "announcement"]
    capability = "event-publish"
    config_schema: Dict[str, Any] = {}
    arguments_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "The notification title (the toast's headline).",
            },
            "message": {
                "type": "string",
                "description": "The notification body (the toast's message).",
            },
            "type": {
                "type": "string",
                "enum": ["info", "success", "warning", "error"],
                "description": (
                    "The class: success plays the run-complete bell, "
                    "warning the alert, error the emergency; info stays "
                    "silent. Default: info."
                ),
            },
            "sticky": {
                "type": "boolean",
                "description": (
                    "Sticky: stays until dismissed + the sound cycles "
                    "every 2 seconds (the attention-critical cases). "
                    "Default: false."
                ),
            },
            "link": {
                "type": "string",
                "description": (
                    "An optional link the toast carries — clicking it "
                    "navigates the user there (e.g. '/exa' to bring "
                    "them to the Exa chat, or any app route / http(s) "
                    "URL). Pairs with link_label."
                ),
            },
            "link_label": {
                "type": "string",
                "description": (
                    "The link's label on the toast. Default: 'Open'. "
                    "The user's flavor: 'Talk to me', 'Please, talk "
                    "to me', 'Urgent'."
                ),
            },
        },
        "required": ["title"],
    }

    def __init__(self) -> None:
        pass

    async def execute(self, config: Optional[dict] = None, **kwargs: Any) -> dict[str, Any]:
        from app.domain.messaging.services import publish

        args = kwargs.get("arguments") or kwargs.get("args") or kwargs
        title = str(args.get("title") or "").strip()
        if not title:
            return {"success": False, "error": "title is required"}
        ntype = str(args.get("type") or "info")
        if ntype not in ("info", "success", "warning", "error"):
            return {"success": False, "error": "type must be info|success|warning|error"}
        sticky = bool(args.get("sticky"))
        link = str(args.get("link") or "").strip()
        if link and not _safe_link(link):
            return {"success": False, "error": "link must be an app route (/...) or an http(s) URL"}

        payload: dict[str, Any] = {
            "title": title,
            "message": str(args.get("message") or ""),
            "type": ntype,
            "from": "exa",
            "kind": "exa-notification",
            "sticky": sticky,
        }
        if link:
            payload["action"] = {
                "label": str(args.get("link_label") or "Open").strip() or "Open",
                "href": link,
            }
        publish("notify:exa", payload)
        logger.info(f"  📣 SendNotification tool: {title!r} ({ntype}, sticky={sticky}, link={link or '-'})")
        return {"success": True, "title": title, "type": ntype, "sticky": sticky, "link": link or None}


def register_send_notification_tool(registrar) -> None:
    """Register the send_notification tool (the idempotent pattern)."""
    tool = SendNotificationTool()
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
