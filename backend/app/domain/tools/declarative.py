"""The declarative tool tier — tools defined by a database row, executed over HTTP.

THE TWO STORES. `registry.py` holds executable HANDLERS, registered in code.
The `tools` table holds DESCRIPTORS. Until this module, a descriptor could not be
executed: `registry.execute_tool` raised `KeyError` for any slug without a handler.
A tool row was a catalog entry and nothing more.

WHAT THIS ADDS. A tool whose `type` is a declarative kind carries an `endpoint`,
and is executed by calling it. The logic lives OUTSIDE this process — nothing new
is loaded into it. That is the whole design: **pluggable wiring, not pluggable
code.**

WHAT IT DELIBERATELY DOES NOT DO. There is no field for "here is a module", no
loader, and no placeholder for one. A tool that runs code in-process is a
different feature with a different trust problem (sandboxing), and is explicitly
unbuilt. See `local/tools/tool-extension-tier-design.md` §5.

THE TRUST RULE (design §6). An installed declarative tool may NOT reach the keyed
tier. Installation is wiring, not authority. `restart-backend` is keyed because it
is dangerous; a tool that arrives as a database row must not inherit that power.
This is enforced in `is_declarative()` / the executor's caller, not merely
documented.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

# The `type` value for a tool whose handler is registered in code. Every seeded
# row carries it (measured: 45/45). Anything else that is non-empty and not a
# known alias is treated as declarative — the discriminator already exists in the
# data, so no migration is needed.
BUILTIN_TYPE = "builtin"

# The declarative kinds we accept. Deliberately a small, explicit set: an unknown
# `type` is a configuration error, not a licence to guess.
DECLARATIVE_TYPES = frozenset({"http", "declarative", "endpoint", "webhook"})

DEFAULT_TIMEOUT_MS = 30_000
MAX_TIMEOUT_MS = 300_000


def is_declarative(tool_type: Optional[str]) -> bool:
    """True if this tool's `type` names a declarative (endpoint) tool."""
    if not tool_type:
        return False
    return tool_type.strip().lower() in DECLARATIVE_TYPES


def _resolve_timeout_ms(raw: Any) -> int:
    """The timeout in ms, bounded. A bad value falls back, loudly."""
    try:
        value = int(raw) if raw is not None else DEFAULT_TIMEOUT_MS
    except (TypeError, ValueError):
        logger.warning(
            "Declarative tool has a non-numeric timeout_ms (%r) — using %dms",
            raw,
            DEFAULT_TIMEOUT_MS,
        )
        return DEFAULT_TIMEOUT_MS
    if value <= 0:
        logger.warning(
            "Declarative tool has a non-positive timeout_ms (%r) — using %dms",
            raw,
            DEFAULT_TIMEOUT_MS,
        )
        return DEFAULT_TIMEOUT_MS
    if value > MAX_TIMEOUT_MS:
        logger.warning(
            "Declarative tool timeout_ms %d exceeds the cap — clamping to %dms",
            value,
            MAX_TIMEOUT_MS,
        )
        return MAX_TIMEOUT_MS
    return value


def _auth_headers(tool: Any, config: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """Build the auth headers for a declarative tool.

    `requires_auth` says the endpoint needs a credential. WHERE that credential
    comes from is deliberately minimal here (design §8 defers the auth mechanics):
    the resolved tool config first, then the environment. An endpoint that
    requires auth and has no credential is a configuration error — we do not
    attempt the call.
    """
    if not getattr(tool, "requires_auth", False):
        return {}

    config = config or {}
    token = (
        config.get("api_key")
        or config.get("token")
        or config.get("auth_token")
    )
    if token:
        return {"Authorization": f"Bearer {token}"}

    header_name = config.get("auth_header")
    header_value = config.get("auth_value") or config.get("api_key")
    if header_name and header_value:
        return {str(header_name): str(header_value)}

    import os

    env_token = os.environ.get("COGITATE_DECLARATIVE_TOOL_TOKEN")
    if env_token:
        return {"Authorization": f"Bearer {env_token}"}

    return {}


class DeclarativeToolError(Exception):
    """A declarative tool could not be executed. Never raised for control flow."""


async def execute_declarative_tool(
    *,
    tool: Any,
    arguments: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute a declarative tool by calling its endpoint.

    Returns the SAME shape a handler returns — a dict. Errors are returned as
    `{"success": False, "error": ..., "error_type": ...}` rather than raised, so
    the caller's existing wrapping applies unchanged and a failing endpoint never
    escapes as an exception into a chat turn.

    Args:
        tool: the `Tool` row (needs `endpoint`, `requires_auth`, `timeout_ms`).
        arguments: the tool arguments, sent as the JSON body.
        config: the resolved tool config (may carry the credential).

    Returns:
        The endpoint's JSON response as a dict, or a structured error dict.
    """
    endpoint = (getattr(tool, "endpoint", None) or "").strip()
    if not endpoint:
        return {
            "success": False,
            "error": f"Declarative tool '{getattr(tool, 'slug', '?')}' has no endpoint configured.",
            "error_type": "missing_endpoint",
        }

    if getattr(tool, "requires_auth", False):
        headers = _auth_headers(tool, config)
        if not headers:
            return {
                "success": False,
                "error": (
                    f"Declarative tool '{getattr(tool, 'slug', '?')}' requires auth "
                    "but no credential was resolved."
                ),
                "error_type": "missing_credential",
            }
    else:
        headers = {}

    timeout_ms = _resolve_timeout_ms(getattr(tool, "timeout_ms", None))
    timeout_s = timeout_ms / 1000.0

    # The method is not yet a column (design §8 defers it): POST is the shape that
    # carries arguments, so it is the default and the only one implemented.
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            response = await client.post(endpoint, json=arguments, headers=headers)
    except httpx.TimeoutException:
        logger.warning("Declarative tool '%s' timed out after %dms", tool.slug, timeout_ms)
        return {
            "success": False,
            "error": f"Endpoint did not respond within {timeout_ms}ms.",
            "error_type": "timeout",
        }
    except httpx.HTTPError as exc:
        logger.warning("Declarative tool '%s' transport error: %s", tool.slug, exc)
        return {
            "success": False,
            "error": f"Could not reach the endpoint: {exc}",
            "error_type": "unreachable",
        }

    if response.status_code >= 400:
        logger.warning(
            "Declarative tool '%s' returned HTTP %d", tool.slug, response.status_code
        )
        return {
            "success": False,
            "error": f"Endpoint returned HTTP {response.status_code}: {response.text[:300]}",
            "error_type": "http_error",
        }

    try:
        payload = response.json()
    except ValueError:
        return {
            "success": False,
            "error": f"Endpoint returned non-JSON content: {response.text[:300]}",
            "error_type": "bad_response",
        }

    # A handler returns a dict; an endpoint may return anything JSON. Wrap a
    # non-dict so callers always see the same shape.
    if not isinstance(payload, dict):
        return {"success": True, "result": payload}
    return payload
