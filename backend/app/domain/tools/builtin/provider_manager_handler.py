"""
Provider Manager Tool — provider configurations, and the curated model list.

TWO RESOURCES, ONE TOOL. Providers are what SERVE models; the curated list is the
human-owned record of which models we recommend, and it is where a newly-appearing
model is recorded. Both are administered here so the intake ritual — check the
provider, add the row, verify the row — is one sequence of logged tool calls
instead of a page of improvised HTTP (the finding that opened this work).

The vocabularies below are IMPORTED, not retyped: the model-facing enums and the
API's validation come from the same two tuples, so the tool cannot offer a value
the API refuses (`providers/curated_models_service.py`, `reasoning_support.py`).
"""

from __future__ import annotations
import logging
from typing import Any, Dict

from app.domain.providers.curated_models_service import (
    CURATED_CATEGORIES,
    MODEL_LOCATIONS,
)
from app.services.cognitive_pipeline.reasoning_support import THINKING_LEVELS

logger = logging.getLogger(__name__)

# The app's own API. This tool drives the SAME endpoints a person would, which is
# what makes the ritual auditable after the fact.
_API = "http://localhost:8000/api/v1"


def _detail(resp: Any) -> str:
    """The API's own refusal sentence, so the model learns WHY rather than retrying.

    FastAPI's 422 arrives as `{"detail": [{"msg": ...}]}`; a 400 carries a plain
    string `detail`. Falling back to the body keeps an unexpected shape visible
    instead of turning it into an empty error.
    """
    try:
        payload = resp.json()
    except Exception:
        return str(resp.text)
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, list) and detail:
            first = detail[0]
            if isinstance(first, dict):
                return str(first.get("msg") or first)
            return str(first)
        if detail:
            return str(detail)
    return str(resp.text)


def _json_result(resp: Any, expected: int = 200) -> Dict[str, Any]:
    """Success only at the expected status; otherwise the refusal, with its code."""
    if resp.status_code == expected:
        return {"success": True, "data": resp.json()}
    return {
        "success": False,
        "error": _detail(resp),
        "status": resp.status_code,
    }


class ProviderManagerTool:
    name = "Provider Manager"
    slug = "provider-manager"
    capability = "provider-admin"
    description = (
        "List, get, configure, test and sync provider configurations; list, add and "
        "verify curated models — the human-owned record of which models we recommend, "
        "and where a newly-appearing model is recorded."
    )
    tags = ["op:write", "op:read", "purpose:admin", "system", "safe"]

    config_schema = {"type": "object", "properties": {}}

    arguments_schema = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": [
                    "list", "get", "configure", "test", "sync-models",
                    "curated-list", "curated-add", "curated-verify",
                ],
                "description": "Operation to perform",
            },
            "provider_id": {
                "type": "integer",
                "description": "Provider config ID (required for get/configure/test/sync-models)",
            },
            "config": {
                "type": "object",
                "description": "Provider configuration (required for configure: api_key, base_url, etc.)",
            },
            "provider": {
                "type": "string",
                "description": (
                    "Provider NAME, e.g. 'openrouter' — required for curated-add, and an "
                    "optional filter for curated-list"
                ),
            },
            "model_id": {
                "type": "string",
                "description": (
                    "The model id as the PROVIDER spells it, e.g. "
                    "'stealth/space-bunny-alpha' (required for curated-add)"
                ),
            },
            "model_name": {
                "type": "string",
                "description": "Display name for the curated row (required for curated-add)",
            },
            "category": {
                "type": "string",
                "enum": sorted(CURATED_CATEGORIES),
                "description": "What the row is recommended FOR (curated-add)",
            },
            "context_length": {
                "type": "integer",
                "description": (
                    "The model's context window in tokens, when the provider's catalog "
                    "states one (curated-add). Verification adopts the provider's own "
                    "number later, so an unstated value is better than a guess."
                ),
            },
            "thinking": {
                "type": "string",
                "enum": list(THINKING_LEVELS),
                "description": (
                    "Declared thinking level (curated-add). The row is verified against "
                    "the provider's own cached claim as it is created, so a payload that "
                    "states reasoning WINS over this field (the disagreement is logged). "
                    "State a value for a driver whose payload says nothing. 'mandatory' "
                    "is not a degree of effort: it says the driver cannot be told not to "
                    "think. This floors the output budget, so a reasoning driver recorded "
                    "as 'none' gets a budget too small for thinking plus its answer."
                ),
            },
            "location": {
                "type": "string",
                "enum": list(MODEL_LOCATIONS),
                "description": (
                    "Where the model runs — 'local' for a server on this machine, "
                    "'cloud' for a provider (curated-add)"
                ),
            },
            "curated_id": {
                "type": "integer",
                "description": "The curated row's id (required for curated-verify)",
            },
            "refresh": {
                "type": "boolean",
                "description": (
                    "curated-verify: ask the provider for its catalog again before "
                    "comparing. Without it the check reads our own record, which is "
                    "dated — and the answer says so."
                ),
            },
        },
        "required": ["operation"],
    }

    async def execute(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Execute a provider or curated-model management operation."""
        import httpx
        base = f"{_API}/providers/config"
        curated = f"{_API}/curated-models"

        try:
            if operation == "list":
                async with httpx.AsyncClient() as c:
                    resp = await c.get(base, timeout=10)
                    return {"success": True, "data": resp.json()}

            elif operation == "get":
                pid = kwargs.get("provider_id")
                if not pid:
                    return {"success": False, "error": "provider_id required"}
                async with httpx.AsyncClient() as c:
                    resp = await c.get(f"{base}/{pid}", timeout=10)
                    return {"success": resp.status_code == 200, "data": resp.json() if resp.status_code == 200 else resp.text}

            elif operation == "configure":
                pid = kwargs.get("provider_id")
                config = kwargs.get("config", {})
                if not pid:
                    return {"success": False, "error": "provider_id required"}
                async with httpx.AsyncClient() as c:
                    resp = await c.put(f"{base}/{pid}", json=config, timeout=10)
                    return {"success": resp.status_code == 200, "data": resp.json() if resp.status_code == 200 else resp.text}

            elif operation == "test":
                pid = kwargs.get("provider_id")
                if not pid:
                    return {"success": False, "error": "provider_id required"}
                async with httpx.AsyncClient() as c:
                    resp = await c.post(f"{base}/{pid}/test", timeout=30)
                    return {"success": resp.status_code == 200, "data": resp.json() if resp.status_code == 200 else resp.text}

            elif operation == "sync-models":
                pid = kwargs.get("provider_id")
                if not pid:
                    return {"success": False, "error": "provider_id required"}
                async with httpx.AsyncClient() as c:
                    resp = await c.post(f"{base}/{pid}/sync?force_refresh=true", timeout=60)
                    return {"success": resp.status_code == 200, "data": resp.json() if resp.status_code == 200 else resp.text}

            elif operation == "curated-list":
                params = {}
                provider = str(kwargs.get("provider") or "").strip()
                if provider:
                    params["provider"] = provider
                async with httpx.AsyncClient() as c:
                    resp = await c.get(curated, params=params or None, timeout=10)
                    return _json_result(resp)

            elif operation == "curated-add":
                missing = [
                    key for key in ("provider", "model_id", "model_name")
                    if not str(kwargs.get(key) or "").strip()
                ]
                if missing:
                    return {
                        "success": False,
                        "error": f"{', '.join(missing)} required for curated-add",
                    }
                body: Dict[str, Any] = {
                    "provider": str(kwargs["provider"]).strip(),
                    "model_id": str(kwargs["model_id"]).strip(),
                    "model_name": str(kwargs["model_name"]).strip(),
                }
                # Only what the caller stated: an unstated field lets the row take
                # the shape the app already writes, rather than this tool inventing one.
                for key in ("category", "context_length", "thinking", "location"):
                    if kwargs.get(key) not in (None, ""):
                        body[key] = kwargs[key]
                async with httpx.AsyncClient() as c:
                    resp = await c.post(curated, json=body, timeout=15)
                    return _json_result(resp, expected=201)

            elif operation == "curated-verify":
                curated_id = kwargs.get("curated_id")
                if curated_id in (None, ""):
                    return {"success": False, "error": "curated_id required for curated-verify"}
                async with httpx.AsyncClient() as c:
                    resp = await c.post(
                        f"{curated}/{curated_id}/verify-window",
                        json={"refresh": bool(kwargs.get("refresh"))},
                        timeout=60,   # a refresh asks the provider, like sync-models
                    )
                    return _json_result(resp)

            return {"success": False, "error": f"Unknown operation: {operation}"}

        except Exception as e:
            logger.error("Provider manager error: %s", e)
            return {"success": False, "error": str(e)}
