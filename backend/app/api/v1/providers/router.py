"""
Provider API endpoints.

Provides provider management and testing functionality.
"""

import logging
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db_session
from app.domain.providers.availability import read_availability_for, test_card
from app.domain.providers.provider_endpoints import canonical_endpoint, resolve_endpoint
from app.domain.providers.services import OllamaService
from app.domain.providers.schemas import OllamaModelListResponse, ModelDetail
from app.infrastructure.database.models import Provider

logger = logging.getLogger(__name__)


def _announce(event: str, payload: dict) -> None:
    """THE CROSS-WINDOW SYNC (2026-08-25, the roadmap Phase 7):
    provider:<name>:<event> — the frontend's sync reloads the open pages."""
    try:
        from app.domain.messaging.services import publish
        publish(f"provider:{payload.get('name')}:{event}", payload)
    except Exception as e:  # pragma: no cover
        logger.error(f"  ❌ provider:{event} publish failed: {e}")

router = APIRouter(prefix="/providers", tags=["providers"])


# Dependency injection
async def get_ollama_service(db: AsyncSession = Depends(get_db_session)) -> OllamaService:
    """The Ollama service, pointed at the address the `ollama` ROW declares.

    THE ROW IS THE DECISION (2026-10-10, the service-literals arc). This dependency used to build
    `OllamaService()` off a literal default, so every route below dialled `localhost:11434` whether
    or not anybody had configured it — the same "the app must not probe an address nobody
    configured" rule this module's own test route states. No row, or a row that resolves to
    nothing, is an ANSWER the caller is told, not a guessed address.
    """
    row = (
        await db.execute(select(Provider).where(Provider.name == "ollama"))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No 'ollama' provider row is configured",
        )
    endpoint = resolve_endpoint(row.provider_type or "ollama", row.base_url, row.name)
    if endpoint is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"The '{row.name}' provider row declares no endpoint",
        )
    return OllamaService(base_url=endpoint)


# Available LLM providers — THE CATALOG `GET /providers` serves. It lists provider TYPES for
# orientation (the install's real rows live at /providers/config), and its addresses are NOT a
# second copy of the registry (2026-10-12, option A, staged —
# `wiki/issues/resolved/embedded-service-literals/provider-addresses-registry-copies.md`): each
# `base_url` is READ from the registry wherever the registry answers. The two types the registry
# declines BY DESIGN (`openai`, `anthropic` — each names a hosted vendor AND any self-hosted
# OpenAI-compatible server, so the row has to declare it) keep a declared DISPLAY value here.
_DISPLAY_ADDRESS: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com",
}

_CATALOG_TYPES: dict[str, tuple[str, str]] = {
    "ollama": ("Ollama", "local"),
    "openai": ("OpenAI", "cloud"),
    "anthropic": ("Anthropic", "cloud"),
    "openrouter": ("OpenRouter", "cloud"),
    "deepseek": ("Deepseek", "cloud"),
}

PROVIDERS = {
    slug: {
        "name": name,
        "base_url": canonical_endpoint(slug) or _DISPLAY_ADDRESS[slug],
        "type": kind,
    }
    for slug, (name, kind) in _CATALOG_TYPES.items()
}


@router.get("")
async def list_providers(
    search: Annotated[Optional[str], Query(min_length=1, max_length=100, description="Filter providers by name or type (case-insensitive)")] = None,
    all: Annotated[bool, Query(description="Return all providers without pagination limits")] = False,
):
    """
    List available LLM providers.

    Supports optional search filtering by name or type, and an `all` flag
    to return the full list without pagination constraints.

    Args:
        search: Optional search string to filter providers by name or type
        all: If True, return all providers without pagination limits

    Returns:
        dict: List of providers with their configuration
    """
    settings = get_settings()

    providers: list[dict[str, Any]] = []
    for provider_id, provider_info in PROVIDERS.items():
        providers.append({
            "id": provider_id,
            "name": provider_info["name"],
            "type": provider_info["type"],
            "base_url": provider_info["base_url"],
            "configured": _is_provider_configured(provider_id, settings),
        })

    # Filter by search query if provided
    if search:
        search_lower = search.lower()
        providers = [
            p
            for p in providers
            if search_lower in p["name"].lower() or search_lower in p["type"].lower()
        ]

    return {
        "providers": providers,
        "total": len(providers),
    }


@router.get("/ollama/models", response_model=OllamaModelListResponse)
async def list_ollama_models(ollama: Annotated[OllamaService, Depends(get_ollama_service)]):
    """
    List available Ollama models.

    Returns:
        OllamaModelListResponse: List of available models with metadata
    """
    models = await ollama.list_models()
    
    return {
        "models": models,
        "total": len(models),
    }


@router.get("/ollama/models/{model_name}", response_model=ModelDetail)
async def get_ollama_model_info(
    model_name: str,
    ollama: Annotated[OllamaService, Depends(get_ollama_service)]
):
    """
    Get detailed information about a specific Ollama model.

    Args:
        model_name: Name of the model

    Returns:
        ModelDetail: Detailed model information
    """
    model_info = await ollama.get_model_info(model_name)
    
    if not model_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {model_name} not found",
        )
    
    return model_info


@router.get("/{provider_id}")
async def get_provider(provider_id: str):
    """
    Get provider details.

    Args:
        provider_id: Provider ID (ollama, openai, anthropic)

    Returns:
        dict: Provider details
    """
    if provider_id not in PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found",
        )

    settings = get_settings()
    provider_info = PROVIDERS[provider_id]

    return {
        "id": provider_id,
        "name": provider_info["name"],
        "type": provider_info["type"],
        "base_url": provider_info["base_url"],
        "configured": _is_provider_configured(provider_id, settings),
    }


@router.post("/{provider_id}/test")
async def test_provider(
    provider_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """Test provider connectivity — through the ONE availability read.

    THE SLUG VOCABULARY IS THIS ROUTE'S OWN, and it is kept — but the mapping is now to a ROW.
    `PROVIDERS` is a hardcoded dict keyed by slug (`ollama`, `openrouter`, …) and the EXTERNAL
    AGENT's skills are its consumers (Exa's `cogitate-api-surface` documents "test via
    `/providers/{id}/test`" and passes those slugs). Absorbed in phase 6, group 5: this was the
    third inline probe of "is this provider up?", and the card's vocabulary now lives once
    (`availability.test_card`).

    A slug with NO row behind it answers `unknown_provider` rather than probing the dict's
    hardcoded base_url: this installation's providers are ROWS, and the app must not probe an
    address nobody configured. `openai` and `anthropic` are the slugs that means today.

    Args:
        provider_id: Provider slug (`ollama`, `openai`, `anthropic`, `openrouter`, `deepseek`)

    Returns:
        dict: Test results including latency and status
    """
    if provider_id not in PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found",
        )

    row = (
        await db.execute(select(Provider).where(Provider.name == provider_id))
    ).scalar_one_or_none()
    if row is None:
        return {
            "status": "unknown_provider",
            "message": f"No provider row matches '{provider_id}'",
        }

    reading = (
        await read_availability_for(db, extra_names=[row.name], force=True)
    ).get(row.name)
    if reading is None:
        return {"status": "error", "message": f"No availability reading for {row.name}"}

    return test_card(reading, row.display_name or row.name)



def _is_provider_configured(provider_id: str, settings) -> bool:
    """Check if a provider is configured."""
    if provider_id == "ollama":
        # Ollama is always "configured" if it's local
        return True
    elif provider_id == "openai":
        return bool(settings.openai_api_key)
    elif provider_id == "anthropic":
        return bool(settings.anthropic_api_key)
    elif provider_id == "openrouter":
        return bool(settings.openrouter_api_key)
    elif provider_id == "deepseek":
        return bool(settings.deepseek_api_key)
    return False
