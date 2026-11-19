"""
Provider configuration API endpoints.

Provides CRUD operations for provider configurations.
"""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db_session
from app.domain.providers.availability import (
    read_availability_for,
    test_card,
)
from app.domain.providers.config_service import ProviderConfigService
from app.domain.providers.discovery_service import provider_discovery_service
from app.domain.providers.provider_endpoints import resolve_endpoint

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/providers/config", tags=["provider-config"])


class ProviderConfigCreate(BaseModel):
    """Schema for creating a provider."""
    name: str = Field(..., description="Provider name (e.g., 'openai', 'anthropic')")
    display_name: Optional[str] = Field(None, description="Human-readable display name")
    provider_type: str = Field(..., description="Provider type")
    base_url: Optional[str] = Field(None, description="Base URL for API")
    api_key: Optional[str] = Field(None, description="API key (will be encrypted)")
    is_active: bool = Field(True, description="Whether provider is active")
    priority: int = Field(99, description="Priority for fallback (lower = higher priority)")
    config: Optional[dict] = Field(None, description="Additional configuration")


class ProviderConfigUpdate(BaseModel):
    """Schema for updating a provider."""
    display_name: Optional[str] = Field(None, description="Human-readable display name")
    base_url: Optional[str] = Field(None, description="Base URL for API")
    api_key: Optional[str] = Field(None, description="API key (will be encrypted)")
    is_active: Optional[bool] = Field(None, description="Whether provider is active")
    priority: Optional[int] = Field(None, description="Priority for fallback")
    config: Optional[dict] = Field(None, description="Additional configuration")


class ProviderConfigResponse(BaseModel):
    """Schema for provider response."""
    id: int
    name: str
    display_name: Optional[str]
    provider_type: str
    base_url: Optional[str]
    is_active: bool
    priority: int
    config: Optional[dict]
    has_api_key: bool
    created_at: datetime
    updated_at: datetime
    location: str = "cloud"

    model_config = ConfigDict(from_attributes=True)


class ProviderConfigListResponse(BaseModel):
    """Schema for provider list response."""
    providers: List[ProviderConfigResponse]
    total: int


class ApiKeyRequest(BaseModel):
    """Schema for setting API key."""
    api_key: str = Field(..., description="API key to set")


class ProviderTestResponse(BaseModel):
    """Schema for provider test response.

    THE SHAPE IS UNCHANGED on purpose (phase 6, group 5): `providerConfigService.testProvider` and
    the Health modal read `status`/`message`/`latency_ms`/`models_available`, so the absorption of
    this endpoint into the ONE availability read is invisible to them. `state` and `checked_at` are
    ADDED — the availability read's own vocabulary and WHEN it looked — so a caller that wants the
    finer answer (a swap-away is not an incident) or the age of the reading has it; a caller that
    does not still sees exactly what it saw before.
    """

    status: str
    message: str
    latency_ms: Optional[float] = None
    models_available: Optional[int] = None
    state: Optional[str] = Field(None, description="The availability read's own state")
    checked_at: Optional[str] = Field(None, description="When the availability read looked")


@router.get("", response_model=ProviderConfigListResponse)
async def list_provider_configs(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db_session),
):
    """
    List all provider configurations.

    Args:
        include_inactive: Whether to include inactive providers
    """
    config_service = ProviderConfigService()
    providers = await config_service.list_providers(db, include_inactive)

    return {
        "providers": providers,
        "total": len(providers),
    }


@router.get("/{provider_id}", response_model=ProviderConfigResponse)
async def get_provider_config(
    provider_id: int,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get provider configuration by ID.

    Args:
        provider_id: Provider ID
    """
    config_service = ProviderConfigService()
    provider = await config_service.get_provider(db, provider_id)

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found",
        )

    return provider


@router.post("", response_model=ProviderConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_provider_config(
    config: ProviderConfigCreate,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Create a new provider configuration.

    Args:
        config: Provider configuration
    """
    config_service = ProviderConfigService()

    try:
        provider = await config_service.create_provider(
            db=db,
            name=config.name,
            provider_type=config.provider_type,
            display_name=config.display_name,
            base_url=config.base_url,
            api_key=config.api_key,
            is_active=config.is_active,
            priority=config.priority,
            config=config.config,
        )
        return provider
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.put("/{provider_id}", response_model=ProviderConfigResponse)
async def update_provider_config(
    provider_id: int,
    config: ProviderConfigUpdate,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Update provider configuration.

    Args:
        provider_id: Provider ID
        config: New provider configuration
    """
    config_service = ProviderConfigService()

    provider = await config_service.update_provider(
        db=db,
        provider_id=provider_id,
        display_name=config.display_name,
        base_url=config.base_url,
        api_key=config.api_key,
        is_active=config.is_active,
        priority=config.priority,
        config=config.config,
    )

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found",
        )

    return provider


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider_config(
    provider_id: int,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Delete provider configuration.

    Args:
        provider_id: Provider ID
    """
    config_service = ProviderConfigService()

    deleted = await config_service.delete_provider(db, provider_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found",
        )


@router.post("/{provider_id}/api-key", status_code=status.HTTP_204_NO_CONTENT)
async def set_provider_api_key(
    provider_id: int,
    request: ApiKeyRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Set provider API key.

    Args:
        provider_id: Provider ID
        request: API key request
    """
    config_service = ProviderConfigService()

    success = await config_service.set_api_key(db, provider_id, request.api_key)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found",
        )


@router.get("/{provider_id}/api-key")
async def get_provider_api_key_status(
    provider_id: int,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Check if provider has API key configured.

    Args:
        provider_id: Provider ID
    """
    config_service = ProviderConfigService()

    has_key = await config_service.has_api_key(db, provider_id)
    provider = await config_service.get_provider(db, provider_id)

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found",
        )

    return {
        "provider_id": provider_id,
        "provider_name": provider.name,
        "api_key_configured": has_key,
    }


@router.post("/{provider_id}/test", response_model=ProviderTestResponse)
async def test_provider_config(
    provider_id: int,
    db: AsyncSession = Depends(get_db_session),
):
    """Test provider connectivity — through the ONE availability read.

    This endpoint used to carry its own inline probe (a branch per provider type and per provider
    NAME) — the copy the Health button used, and one of the answers to *"is this provider up?"* that
    agreed with the others only by luck. It now calls `availability.read_availability_for` and
    RENDERS what that read found; `_TEST_STATUS` above is the whole of what is left here.

    `force=True` on purpose: an explicit test must not answer with a memo a minute old. The refresh
    is SHARED, so what this button finds is what the capability page and the agent badges show next
    — the opposite of the four-answers shape this absorbs.

    Args:
        provider_id: Provider ID
    """
    provider = await ProviderConfigService().get_provider(db, provider_id)

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found",
        )

    reading = (
        await read_availability_for(db, extra_names=[provider.name], force=True)
    ).get(provider.name)
    if reading is None:
        return ProviderTestResponse(
            status="error",
            message=f"No availability reading for {provider.name}",
        )

    # ONE renderer for every "test this provider" card (`availability.test_card`) — the vocabulary
    # lives with the read, so this endpoint and its two siblings cannot describe one daemon
    # differently.
    return ProviderTestResponse(**test_card(reading, provider.display_name or provider.name))


@router.post("/{provider_id}/sync")
async def sync_provider_models(
    provider_id: int,
    force_refresh: bool = True,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Synchronize models for a provider.

    Args:
        provider_id: Provider ID
        force_refresh: Force refresh from provider API
    """

    config_service = ProviderConfigService()
    provider = await config_service.get_provider(db, provider_id)

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found",
        )

    # Get API key from .env (EnvKeyStore) — the DB column was removed
    from app.domain.providers.env_key_store import env_key_store
    api_key = env_key_store.get_key(provider.provider_type)
    if not api_key:
        # Fallback to settings
        settings = get_settings()
        if provider.provider_type == "openrouter":
            api_key = settings.openrouter_api_key
        elif provider.provider_type == "openai":
            api_key = settings.openai_api_key
        elif provider.provider_type == "anthropic":
            api_key = settings.anthropic_api_key
        elif provider.provider_type == "deepseek":
            api_key = settings.deepseek_api_key

    # Discover models based on provider type
    if provider.provider_type == "openrouter":
        if not api_key:
            return {
                "status": "error",
                "message": "OpenRouter API key not configured",
                "provider_name": provider.name,
            }

        result = await provider_discovery_service.discover_openrouter_models(
            db, provider_id, api_key, force_refresh
        )

    elif provider.provider_type == "deepseek":
        if not api_key:
            return {
                "status": "error",
                "message": "Deepseek API key not configured",
                "provider_name": provider.name,
            }

        result = await provider_discovery_service.discover_deepseek_models(
            db, provider_id, api_key, force_refresh
        )

    elif provider.provider_type == "ollama":
        endpoint = resolve_endpoint(provider.provider_type, provider.base_url, provider.name)
        if endpoint is None:
            return {
                "status": "error",
                "message": f"The '{provider.name}' row declares no endpoint",
                "provider_name": provider.name,
            }
        result = await provider_discovery_service.discover_ollama_models(
            db, provider_id, endpoint, force_refresh
        )

    else:
        return {
            "status": "error",
            "message": f"Model discovery not yet implemented for {provider.provider_type}",
            "provider_name": provider.name,
        }

    return {
        "status": "success",
        "message": f"Successfully synced {result.get('total', 0)} models for {provider.name}",
        "provider_name": provider.name,
        "models_synced": result.get("total", 0),
        "from_cache": result.get("from_cache", False),
    }
