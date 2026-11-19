"""
LLM tool-schema helpers.

A single authoritative place for converting a Tool database record into the
OpenAI function-calling format expected by LiteLLM / the LLM providers.

Previously this logic was copy-pasted in three locations:
  - backend/app/api/v1/chat/context.py
  - backend/app/api/v1/agent_chat/router.py  (_resolve_tools)
  - backend/app/api/v1/chat/router.py        (delegate endpoint)

Any change to the credential-stripping list or schema-selection priority
now only needs to be made here.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Fields that must never appear in the 'required' list sent to the LLM.
# The LLM cannot supply secrets, so we strip them to prevent confusing
# "missing required field" errors when the LLM tries to call the tool.
_CREDENTIAL_FIELDS = frozenset({"api_key", "search_engine_id", "token", "password"})


def tool_to_llm_schema(tool: Any) -> Optional[Dict[str, Any]]:
    """Convert a Tool ORM record into an OpenAI function-calling dict.

    Prefers ``arguments_schema`` over ``config_schema``.  Strips credential
    fields from the ``required`` list so the LLM is not asked to supply
    values it cannot know.

    Args:
        tool: A ``Tool`` ORM instance (``app.domain.tools.models.Tool``).

    Returns:
        A dict of the form::

            {
                "type": "function",
                "function": {
                    "name": "<slug>",
                    "description": "...",
                    "parameters": { ... },
                }
            }

        Returns ``None`` if ``tool`` is falsy.
    """
    if not tool:
        return None

    # --- Schema selection ------------------------------------------------
    schema: Dict[str, Any] = {}
    if tool.arguments_schema:
        schema = (
            tool.arguments_schema.copy()
            if isinstance(tool.arguments_schema, dict)
            else {}
        )
    elif tool.config_schema:
        schema = (
            tool.config_schema.copy()
            if isinstance(tool.config_schema, dict)
            else {}
        )
        logger.warning(
            "Tool %s has no arguments_schema; falling back to config_schema",
            tool.slug,
        )

    # --- Strip credential fields from 'required' -------------------------
    if "required" in schema:
        filtered = [
            f for f in schema.get("required", [])
            if f not in _CREDENTIAL_FIELDS
        ]
        if filtered:
            schema["required"] = filtered
        else:
            schema.pop("required", None)

    return {
        "type": "function",
        "function": {
            "name": tool.slug,
            "description": tool.description or f"Execute the {tool.name} tool",
            "parameters": schema,
        },
    }
