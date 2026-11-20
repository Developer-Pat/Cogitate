"""
Provider Management API endpoints.

Provides CRUD operations for LLM providers stored in database.
"""

import logging
from typing import Any, Optional, List, cast
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db_session
from app.infrastructure.database.models import Provider
from app.domain.providers.availability import read_availability_for, test_card
from app.domain.providers.cache_service import provider_model_cache_service
from app.domain.providers.discovery_service import provider_discovery_service
from app.domain.providers.provider_endpoints import resolve_endpoint
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


def _announce(event: str, payload: dict) -> None:
    """THE CROSS-WINDOW SYNC (2026-08-25, the roadmap Phase 7):
    provider:<name>:<event> — the frontend's sync reloads the open pages."""
    try:
        from app.domain.messaging.services import publish
        publish(f"provider:{payload.get('name')}:{event}", payload)
    except Exception as e:  # pragma: no cover
        logger.error(f"  ❌ provider:{event} publish failed: {e}")

router = APIRouter(prefix="/providers", tags=["provider-management"])


# Pydantic schemas for provider management
class ProviderConfig(BaseModel):
    """Schema for provider configuration."""
    name: str = Field(..., description="Provider name (e.g., 'ollama', 'openai')")
    display_name: Optional[str] = Field(None, description="Human-readable display name")
    provider_type: str = Field(..., description="Provider type (ollama, openai, anthropic, etc.)")
    api_key: Optional[str] = Field(None, description="API key (will be encrypted)")
    base_url: Optional[str] = Field(None, description="Base URL for API")
    is_active: bool = Field(True, description="Whether provider is active")
    priority: int = Field(99, description="Priority for fallback (lower = higher priority)")
    is_default: bool = Field(False, description="Whether this is the system default provider")
    config: Optional[dict] = Field(None, description="Additional configuration")


class ProviderResponse(BaseModel):
    """Schema for provider response."""
    id: int
    name: str
    display_name: Optional[str]
    provider_type: str
    base_url: Optional[str]
    is_active: bool
    priority: int
    is_default: bool
    config: Optional[dict]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProviderTestResponse(BaseModel):
    """Schema for provider test response.

    Mirrors the `/providers/config` card field for field: `providerConfigService.testProvider`, the
    Health modal and `SetupPage` all read these keys, so any of the test endpoints can answer with
    this shape. `state` + `checked_at` are the availability read's own vocabulary and WHEN it
    looked, added so a caller can have the finer answer without a second probe.
    """
    status: str
    message: str
    latency_ms: Optional[float] = None
    models_available: Optional[int] = None
    state: Optional[str] = Field(None, description="The availability read's own state")
    checked_at: Optional[str] = Field(None, description="When the availability read looked")


class ProviderListResponse(BaseModel):
    """Schema for provider list response."""
    providers: List[ProviderResponse]
    total: int


class DefaultProviderResponse(BaseModel):
    """Schema for default provider response."""
    provider_id: int
    provider_name: str
    provider_type: str
    model_name: str
    base_url: Optional[str]
    is_active: bool


class SetDefaultProviderRequest(BaseModel):
    """Schema for setting default provider."""
    provider_id: int = Field(..., description="ID of provider to set as default")
    model: Optional[str] = Field(None, description="Optional model to set as default for this provider")


@router.get("/managed", response_model=ProviderListResponse)
async def list_managed_providers(db: AsyncSession = Depends(get_db_session)):
    """
    List all configured providers from database.
    
    Returns providers stored in the database, not hardcoded ones.
    """
    query = select(Provider).order_by(Provider.priority)
    result = await db.execute(query)
    providers = result.scalars().all()
    
    return {
        "providers": providers,
        "total": len(providers),
    }


@router.post("/managed", response_model=ProviderResponse, status_code=status.HTTP_201_CREATED)
async def create_provider(
    config: ProviderConfig,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Add a new provider configuration.
    
    Args:
        config: Provider configuration
    """
    # Check if provider already exists
    query = select(Provider).where(Provider.name == config.name)
    result = await db.execute(query)
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider '{config.name}' already exists"
        )
    
    # API key → .env (the app's secrets store, decision 2026-08-04)
    if config.api_key:
        from app.domain.providers.env_key_store import env_key_store
        if env_key_store.env_var_for(config.provider_type):
            env_key_store.set_key(config.provider_type, config.api_key)
    
    # Create provider
    provider = Provider(
        name=config.name,
        display_name=config.display_name or config.name.title(),
        provider_type=config.provider_type,
        base_url=config.base_url,
        is_active=config.is_active,
        priority=config.priority,
        config=config.config,
    )
    
    db.add(provider)
    await db.flush()
    await db.refresh(provider)
    
    logger.info(f"✅ Created provider: {provider.name} (ID: {provider.id})")
    _announce("created", {"name": provider.name, "event": "created"})
    
    return provider


@router.get("/managed/keys")
async def list_provider_key_status(
    db: AsyncSession = Depends(get_db_session),
):
    """
    List API-key status for all providers: source = env | db | none.

    env = a key is available from settings (.env) for this provider type;
    db = an encrypted key is stored on the provider row.
    """
    from app.core.config import get_settings
    from app.domain.providers.env_key_store import env_key_store

    settings = get_settings()
    result = await db.execute(select(Provider).order_by(Provider.id))
    providers = result.scalars().all()

    rows = []
    for provider in providers:
        provider_type = provider.provider_type
        # .env is the secrets store (decision 2026-08-04). Read fresh from
        # the file so external edits are reflected; settings is the live
        # cache the app actually uses.
        has_env = bool(env_key_store.get_key(provider_type))
        if not has_env:
            # fall back to cached settings (e.g. in-memory only)
            attr = {
                "openrouter": settings.openrouter_api_key,
                "deepseek": settings.deepseek_api_key,
                "groq": settings.groq_api_key,
                "openai": settings.openai_api_key,
                "anthropic": settings.anthropic_api_key,
                "ollama_cloud": settings.ollama_cloud_api_key,
            }.get(provider_type, "")
            has_env = bool(attr)
        source = "env" if has_env else "none"
        rows.append({
            "provider_id": provider.id,
            "provider_name": provider.name,
            "provider_type": provider_type,
            "key_source": source,
            "has_key": has_env,
        })

    return {"providers": rows, "total": len(rows)}


@router.put("/managed/{provider_id}/key")
async def set_provider_api_key(
    provider_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Set or rotate a provider's API key.

    Keys are written to .env (the app's single secrets store, decision
    2026-08-04) — NOT the DB. The cached settings instance is updated
    in-place so the change applies immediately.
    """
    from app.domain.providers.env_key_store import env_key_store

    api_key = (body or {}).get("api_key", "")
    if not api_key or not api_key.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="api_key is required",
        )

    result = await db.execute(select(Provider).where(Provider.id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found",
        )

    provider_type = provider.provider_type
    ok = env_key_store.set_key(provider_type, api_key.strip())
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No env var mapped for provider type {provider_type}",
        )

    # Retire any legacy DB-encrypted value (main DB holds no secrets)
        await db.commit()

    return {
        "provider_id": provider_id,
        "provider_name": provider.name,
        "key_source": "env",
        "message": f"API key stored in .env ({env_key_store.env_var_for(provider_type)})",
    }


@router.delete("/managed/{provider_id}/key")
async def clear_provider_api_key(
    provider_id: int,
    db: AsyncSession = Depends(get_db_session),
):
    """Clear a provider's API key from .env (and any legacy DB value)."""
    from app.domain.providers.env_key_store import env_key_store

    result = await db.execute(select(Provider).where(Provider.id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found",
        )

    env_key_store.clear_key(provider.provider_type)
    await db.commit()

    return {
        "provider_id": provider_id,
        "provider_name": provider.name,
        "key_source": "none",
        "message": "API key cleared from .env",
    }




@router.get("/managed/{provider_id}", response_model=ProviderResponse)
async def get_managed_provider(
    provider_id: int,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get provider details by ID.
    
    Args:
        provider_id: Provider ID
    """
    query = select(Provider).where(Provider.id == provider_id)
    result = await db.execute(query)
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found"
        )
    
    return provider


@router.put("/managed/{provider_id}", response_model=ProviderResponse)
async def update_provider(
    provider_id: int,
    config: ProviderConfig,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Update provider configuration.
    
    Args:
        provider_id: Provider ID
        config: New provider configuration
    """
    query = select(Provider).where(Provider.id == provider_id)
    result = await db.execute(query)
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found"
        )
    
    # Update fields
    provider.display_name = config.display_name or provider.display_name
    provider.provider_type = config.provider_type
    provider.base_url = config.base_url
    provider.is_active = config.is_active
    provider.priority = config.priority
    provider.config = config.config
    
    # API key → .env (EnvKeyStore); the DB column was removed
    # (DB hygiene round 2). The env store handles writes on config.
    if config.api_key:
        from app.domain.providers.env_key_store import env_key_store
        if env_key_store.env_var_for(provider.provider_type):
            env_key_store.set_key(provider.provider_type, config.api_key)
    
    await db.flush()
    await db.refresh(provider)
    
    logger.info(f"✅ Updated provider: {provider.name} (ID: {provider.id})")
    _announce("updated", {"name": provider.name, "event": "updated"})
    
    return provider


@router.delete("/managed/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(
    provider_id: int,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Delete a provider configuration.
    
    Args:
        provider_id: Provider ID
    """
    query = select(Provider).where(Provider.id == provider_id)
    result = await db.execute(query)
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found"
        )
    
    await db.delete(provider)
    await db.flush()
    
    logger.info(f"✅ Deleted provider: {provider.name} (ID: {provider.id})")
    _announce("deleted", {"name": provider.name, "event": "deleted"})


@router.post("/managed/{provider_id}/test", response_model=ProviderTestResponse)
async def test_managed_provider(
    provider_id: int,
    db: AsyncSession = Depends(get_db_session)
):
    """Test provider connectivity — through the ONE availability read.

    The same absorption as `/providers/config/{id}/test` (phase 6, group 5): this endpoint carried
    its own inline probe, its own provider-type branches and its own key resolution; it now calls
    the ONE read with `force=True` — an explicit test must not answer from a memo a minute old —
    and renders it with the shared `test_card`. `SetupPage` is the live caller.

    Args:
        provider_id: Provider ID
    """
    query = select(Provider).where(Provider.id == provider_id)
    result = await db.execute(query)
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found"
        )
    
    # `verify_key=True`: the user pressed Test, so answer the question a listing cannot — whether the
    # KEY works. On ollama.com a listing answers 200 with no key at all (and the OpenAI-compat
    # `/v1/models` answers 200 to a fake one), which is exactly how a dead key read as "connected".
    # This is the one caller that should spend an inference request to find out.
    reading = (
        await read_availability_for(
            db, extra_names=[provider.name], force=True, verify_key=True
        )
    ).get(provider.name)
    if reading is None:
        return ProviderTestResponse(
            status="error",
            message=f"No availability reading for {provider.name}",
        )

    # ONE renderer for every "test this provider" card (`availability.test_card`) — the same read
    # the capability page, the agent badges and the pre-turn refusal use, so this check and the
    # profile page can never describe one daemon differently.
    return ProviderTestResponse(**test_card(reading, provider.display_name or provider.name))


@router.get("/managed/{provider_id}/api-key")
async def get_provider_api_key_status(
    provider_id: int,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Check if provider has API key configured.
    
    Returns only the status, not the actual key for security.
    
    Args:
        provider_id: Provider ID
    """
    query = select(Provider).where(Provider.id == provider_id)
    result = await db.execute(query)
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found"
        )
    
    from app.domain.providers.env_key_store import env_key_store
    return {
        "provider_id": provider_id,
        "api_key_configured": bool(env_key_store.get_key(provider.provider_type)),
        "provider_name": provider.name,
    }


@router.get("/managed/{provider_id}/models")
async def get_provider_models(
    provider_id: int,
    force_refresh: bool = False,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get models for a provider (with caching).

    Returns cached models by default to avoid repeated API calls.
    Use force_refresh=true to bypass cache and fetch fresh data.

    Args:
        provider_id: Provider ID
        force_refresh: If true, bypass cache and fetch fresh data
    """
    # Check if provider exists
    query = select(Provider).where(Provider.id == provider_id)
    result = await db.execute(query)
    provider = result.scalar_one_or_none()

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found"
        )

    # Snapshot plain values before any discovery call.
    # The discovery service calls db.commit() or db.rollback(), which expires
    # all ORM objects in the session. Accessing provider.name after that point
    # triggers a synchronous lazy-load that raises MissingGreenlet in async context.
    provider_name = provider.name
    provider_type = provider.provider_type
    provider_base_url = provider.base_url

    # Check if provider has API key (for cloud providers)
    # .env (EnvKeyStore) — the DB column was removed
    from app.domain.providers.env_key_store import env_key_store
    api_key = env_key_store.get_key(provider.provider_type)
    if not api_key:
        # .env for development
        from app.core.config import get_settings
        settings = get_settings()
        if provider_type == "openrouter":
            api_key = settings.openrouter_api_key
        elif provider_type == "openai":
            api_key = settings.openai_api_key
        elif provider_type == "anthropic":
            api_key = settings.anthropic_api_key
        elif provider_type == "deepseek":
            api_key = settings.deepseek_api_key
        elif provider_type == "groq":
            api_key = settings.groq_api_key
        elif provider_type == "ollama_cloud":
            api_key = settings.ollama_cloud_api_key

    # Discover models based on provider type
    discovery_result: dict[str, Any]
    if provider_type == "openrouter":
        if not api_key:
            return {
                "models": [],
                "total": 0,
                "from_cache": False,
                "provider_name": provider_name,
                "error": "OpenRouter API key not configured",
            }

        discovery_result = await provider_discovery_service.discover_openrouter_models(
            db, provider_id, api_key, force_refresh
        )

    elif provider_type == "deepseek":
        if not api_key:
            return {
                "models": [],
                "total": 0,
                "from_cache": False,
                "provider_name": provider_name,
                "error": "Deepseek API key not configured",
            }

        discovery_result = await provider_discovery_service.discover_deepseek_models(
            db, provider_id, api_key, force_refresh
        )

    elif provider_type == "groq":
        if not api_key:
            return {
                "models": [],
                "total": 0,
                "from_cache": False,
                "provider_name": provider_name,
                "error": "Groq API key not configured",
            }

        discovery_result = await provider_discovery_service.discover_groq_models(
            db, provider_id, api_key, force_refresh
        )

    elif provider_type == "ollama":
        endpoint = resolve_endpoint(provider_type, provider_base_url, provider_name)
        if endpoint is None:
            return {
                "models": [],
                "total": 0,
                "from_cache": False,
                "provider_name": provider_name,
                "error": f"The '{provider_name}' row declares no endpoint",
            }
        discovery_result = await provider_discovery_service.discover_ollama_models(
            db, provider_id, endpoint, force_refresh
        )

    elif provider_type == "ollama_cloud":
        if not api_key:
            return {
                "models": [],
                "total": 0,
                "from_cache": False,
                "provider_name": provider_name,
                "error": "Ollama Cloud API key not configured",
            }

        endpoint = resolve_endpoint(provider_type, provider_base_url, provider_name)
        if endpoint is None:
            return {
                "models": [],
                "total": 0,
                "from_cache": False,
                "provider_name": provider_name,
                "error": f"The '{provider_name}' row declares no endpoint",
            }
        discovery_result = await provider_discovery_service.discover_ollama_cloud_models(
            db, provider_id, api_key, endpoint, force_refresh
        )

    elif provider_type == "openai" and provider_name == "llama":
        # THE KEYLESS LOCAL ROW (2026-09-09): the llama.cpp / llama
        # row is openai-compat but needs no API key (the name-based
        # alias rule, like the test route). Its /v1/models lists the
        # loaded GGUF — the browse page was dead for it, so there
        # was no way to select a model for the daemon.
        endpoint = resolve_endpoint(provider_type, provider_base_url, provider_name)
        if endpoint is None:
            return {
                "models": [],
                "total": 0,
                "from_cache": False,
                "provider_name": provider_name,
                "error": (
                    f"The '{provider_name}' row declares no endpoint, and the "
                    f"'{provider_type}' type has none — set base_url on the row"
                ),
            }
        discovery_result = await provider_discovery_service.discover_openai_compat_models(
            db, provider_id, endpoint, force_refresh
        )

    else:
        # Other providers not yet implemented
        return {
            "models": [],
            "total": 0,
            "from_cache": False,
            "provider_name": provider_name,
            "message": f"Model discovery not yet implemented for {provider_type}",
        }

    return {
        **discovery_result,
        "provider_name": provider_name,
    }


@router.post("/managed/{provider_id}/models/refresh")
async def refresh_provider_models(
    provider_id: int,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Force refresh models for a provider.

    Clears cache and fetches fresh data from provider API.

    Args:
        provider_id: Provider ID
    """
    # Check if provider exists
    query = select(Provider).where(Provider.id == provider_id)
    query_result = await db.execute(query)
    provider = query_result.scalar_one_or_none()

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found"
        )

    # Snapshot plain values before any discovery call (same reason as get_provider_models).
    provider_name = provider.name
    provider_type = provider.provider_type
    provider_base_url = provider.base_url

    # Check if provider has API key
    # .env (EnvKeyStore) — the DB column was removed
    from app.domain.providers.env_key_store import env_key_store
    api_key = env_key_store.get_key(provider.provider_type)
    if not api_key:
        # Fallback to .env for development
        from app.core.config import get_settings
        settings = get_settings()
        if provider_type == "openrouter":
            api_key = settings.openrouter_api_key
        elif provider_type == "openai":
            api_key = settings.openai_api_key
        elif provider_type == "anthropic":
            api_key = settings.anthropic_api_key
        elif provider_type == "deepseek":
            api_key = settings.deepseek_api_key
        elif provider_type == "groq":
            api_key = settings.groq_api_key

    # Refresh based on provider type
    if provider_type == "openrouter":
        if not api_key:
            return {
                "status": "error",
                "message": "OpenRouter API key not configured",
                "provider_name": provider_name,
            }

        result = await provider_discovery_service.discover_openrouter_models(
            db, provider_id, api_key, force_refresh=True
        )

    elif provider_type == "deepseek":
        if not api_key:
            return {
                "status": "error",
                "message": "Deepseek API key not configured",
                "provider_name": provider_name,
            }

        result = await provider_discovery_service.discover_deepseek_models(
            db, provider_id, api_key, force_refresh=True
        )

    elif provider_type == "groq":
        if not api_key:
            return {
                "status": "error",
                "message": "Groq API key not configured",
                "provider_name": provider_name,
            }

        result = await provider_discovery_service.discover_groq_models(
            db, provider_id, api_key, force_refresh=True
        )

    elif provider_type == "ollama":
        endpoint = resolve_endpoint(provider_type, provider_base_url, provider_name)
        if endpoint is None:
            return {
                "status": "error",
                "message": f"The '{provider_name}' row declares no endpoint",
                "provider_name": provider_name,
            }
        result = await provider_discovery_service.discover_ollama_models(
            db, provider_id, endpoint, force_refresh=True
        )

    else:
        return {
            "status": "error",
            "message": f"Model discovery not yet implemented for {provider_type}",
            "provider_name": provider_name,
        }

    return {
        "status": "success",
        "message": f"Successfully refreshed {result.get('total', 0)} models for {provider_name}",
        "provider_name": provider_name,
        "models_discovered": result.get("total", 0),
        "from_cache": result.get("from_cache", False),
    }


@router.get("/managed/{provider_id}/models/cache-status")
async def get_models_cache_status(
    provider_id: int,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get cache status for provider models.

    Shows when cache was last updated and when it expires.

    Args:
        provider_id: Provider ID
    """
    # Check if provider exists
    query = select(Provider).where(Provider.id == provider_id)
    result = await db.execute(query)
    provider = result.scalar_one_or_none()

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found"
        )

    provider_name = provider.name

    # Get cache status
    cache_status = await provider_model_cache_service.get_cache_status(db, provider_id)

    return {
        "provider_id": provider_id,
        "provider_name": provider_name,
        **cache_status,
    }


# =========================================================================
# Default Provider Endpoints
# =========================================================================

@router.get("/default", response_model=DefaultProviderResponse)
async def get_default_provider(
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get the current default provider configuration.
    
    Returns the system-wide default LLM provider used by workflows,
    title generation, and other services.
    
    Returns:
        Default provider configuration
        
    Raises:
        HTTPException: If no default provider configured (404)
    """
    from app.domain.providers.config_service import DefaultProviderService
    
    default_service = DefaultProviderService()
    config = await default_service.get_default_provider(db)
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No default provider configured. Please set a default provider."
        )
    
    return DefaultProviderResponse(
        provider_id=cast(int, config.id),
        provider_name=config.name,
        provider_type=config.provider_type,
        model_name=config.config.get("default_model", config.name) if config.config else config.name,
        base_url=config.base_url,
        is_active=config.is_active,
    )


@router.put("/default", response_model=DefaultProviderResponse)
async def set_default_provider(
    request: SetDefaultProviderRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Set a provider as the system default.

    This will unset any existing default provider first.
    Optionally updates the provider's default model.

    Args:
        request: Request with provider ID and optional model

    Returns:
        Updated default provider configuration

    Raises:
        HTTPException: If provider not found (404)
    """
    from sqlalchemy import update as sa_update

    try:
        logger.info(f"📥 Received request: provider_id={request.provider_id}, model={request.model}")
        
        # First, unset any existing default
        await db.execute(
            sa_update(Provider)
            .where(Provider.is_default)
            .values(is_default=False)
        )

        # Get the provider and set as default
        query = select(Provider).where(Provider.id == request.provider_id)
        result = await db.execute(query)
        provider = result.scalar_one_or_none()

        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Provider {request.provider_id} not found"
            )

        # Set as default
        provider.is_default = True

        # Update model config if provided
        if request.model:
            config = provider.config or {}
            config["default_model"] = request.model
            provider.config = config
            logger.info(f"✅ Updated model for provider {provider.name}: {request.model}")

        # Flush all changes to database
        await db.flush()
        logger.info(f"✅ Set default provider: {provider.name} (ID: {provider.id})")

        # THE VALUE'S CONSUMER (measured 2026-11-20). Setting the default model HERE is the
        # same event as the CLI accept: the shipped agents were waiting for a chat model, and
        # the only other seeding caller was app startup — so a model configured in the browser
        # left the Agents page empty until a restart nobody had a reason to expect. Idempotent:
        # an install that already has its agents reports that and re-creates nothing.
        from app.domain.agents.shipped import seed_shipped_agents

        await db.commit()
        try:
            for outcome in await seed_shipped_agents(db):
                logger.info("news desk — %s", outcome.describe())
        except Exception as exc:  # a setup step must not fail on a seed
            logger.warning("news desk — not seeded: %s", exc)

        return DefaultProviderResponse(
            provider_id=provider.id,
            provider_name=provider.name,
            provider_type=provider.provider_type,
            model_name=provider.config.get("default_model", provider.name) if provider.config else provider.name,
            base_url=provider.base_url,
            is_active=provider.is_active,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to set default provider: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/initialize-default")
async def initialize_default_provider(
    db: AsyncSession = Depends(get_db_session)
):
    """
    Initialize default provider if none exists.

    Creates a default Ollama configuration if no providers exist.
    This is called automatically on first run, but can be called
    manually to ensure default provider is set up.

    Returns:
        Status message and provider info
    """
    from app.domain.providers.config_service import DefaultProviderService

    default_service = DefaultProviderService()
    config = await default_service.initialize_default_provider(db)

    if not config:
        return {
            "status": "warning",
            "message": "Default provider already exists or initialization failed",
        }

    return {
        "status": "success",
        "message": f"Initialized default provider: {config.name}",
        "provider_id": config.id,
        "provider_name": config.name,
        "provider_type": config.provider_type,
    }


@router.get("/default/ready")
async def check_default_provider_ready(
    db: AsyncSession = Depends(get_db_session)
):
    """
    Check if default provider is configured and ready for workflow execution.

    Validates:
    - Default provider exists
    - Provider is active
    - Model is configured (for Ollama)
    - API key is configured (for cloud providers)

    Returns:
        Readiness status and configuration details
    """
    from app.domain.providers.config_service import DefaultProviderService

    default_service = DefaultProviderService()
    result = await default_service.is_default_provider_ready(db)

    return {
        "ready": result["ready"],
        "provider": {
            "id": result["provider"].id if result["provider"] else None,
            "name": result["provider"].name if result["provider"] else None,
            "type": result["provider"].provider_type if result["provider"] else None,
            "model": result["provider"].config.get("default_model") if result["provider"] and result["provider"].config else None,
        } if result["provider"] else None,
        "message": result["message"],
        "issues": result["issues"],
    }
