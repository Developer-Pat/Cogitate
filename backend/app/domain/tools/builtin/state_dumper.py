"""
State Dumper Tool Handler.

Provides access to the system manager's own previous conversation context and state
for introspection/debug mode. Can read session metadata, mode history,
tool usage, and optionally full message history.
Read-only — no write or delete capabilities.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.infrastructure.database.models import ChatSession

logger = logging.getLogger(__name__)


class StateDumperTool:
    """
    State Dumper tool for inspecting conversation sessions.

    Tags:
        - op:read
        - purpose:debug
        - source:session-database
        - safe
        - introspection

    Retrieves:
        - Session metadata (title, agent_id, timestamps)
        - Mode and tools associated with the session
        - Optionally, full message history
    """

    name = "State Dumper"
    slug = "state-dumper"
    capability = "system-diag"
    description = "Dump conversation session state, mode, tools used, and message history"
    tags = [
        "op:read",
        "purpose:debug",
        "source:session-database",
        "safe",
        "introspection",
    ]
    icon = "bug"
    color = "#FFC107"

    config_schema = {
        "type": "object",
        "properties": {},
    }

    arguments_schema = {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "Session ID to inspect (required)",
            },
            "include_messages": {
                "type": "boolean",
                "description": "Include full conversation message history",
                "default": False,
            },
        },
        "required": ["session_id"],
    }

    async def execute(self, config: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Execute state dump operation.

        Args:
            config: Tool configuration
            **kwargs: Tool arguments (session_id, include_messages)

        Returns:
            Dictionary with success status and session state data
        """
        session_id = kwargs.get("session_id")
        include_messages = kwargs.get("include_messages", False)

        if not session_id:
            return {
                "success": False,
                "error": "Missing required argument: 'session_id'. Provide a session ID to inspect.",
            }

        # Validate session_id is a positive integer
        try:
            session_id_int = int(session_id)
        except (ValueError, TypeError):
            return {
                "success": False,
                "error": f"Invalid session_id: '{session_id}'. Session ID must be an integer.",
            }

        try:
            async with AsyncSessionLocal() as db:
                query = select(ChatSession).where(ChatSession.id == session_id_int)
                result = await db.execute(query)
                session = result.scalar_one_or_none()

            if session is None:
                return {
                    "success": False,
                    "error": f"Session not found: {session_id_int}",
                }

            return await self._format_session(session, include_messages)

        except Exception as e:
            logger.error(f"State dumper tool error: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to dump session state: {str(e)}",
            }

    async def _format_session(
        self,
        session: ChatSession,
        include_messages: bool,
    ) -> Dict[str, Any]:
        """Format session data into structured response."""
        result: Dict[str, Any] = {
            "success": True,
            "session": {
                "id": session.id,
                "title": session.title or "Untitled",
                "agent_id": session.agent_id,
                "is_active": session.is_active,
                "created_at": str(session.created_at) if session.created_at else None,
                "updated_at": str(session.updated_at) if session.updated_at else None,
                "message_count": len(session.messages) if session.messages else 0,
            },
        }

        # Add message details if available
        if session.messages:
            # Summarize message roles present
            roles_present: Dict[str, int] = {}
            for msg in session.messages:
                role = msg.role or "unknown"
                roles_present[role] = roles_present.get(role, 0) + 1
            result["session"]["roles_present"] = roles_present

            # Show first and last message timestamps
            if len(session.messages) > 0:
                result["session"]["first_message_at"] = str(session.messages[0].created_at) if session.messages[0].created_at else None
                result["session"]["last_message_at"] = str(session.messages[-1].created_at) if session.messages[-1].created_at else None

        # Include full message history if requested
        if include_messages and session.messages:
            messages = []
            for msg in session.messages:
                message_entry = {
                    "id": msg.id,
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": str(msg.created_at) if msg.created_at else None,
                }
                if msg.model:
                    message_entry["model"] = msg.model
                if msg.provider:
                    message_entry["provider"] = msg.provider
                if msg.token_count is not None:
                    message_entry["token_count"] = msg.token_count
                if msg.total_time_ms is not None:
                    message_entry["total_time_ms"] = msg.total_time_ms
                messages.append(message_entry)

            result["messages"] = messages
            result["message_count"] = len(messages)

        return result
