"""
Provider Models Browser API endpoints.

Provides model browsing, search, and filtering functionality.
"""

import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.config import get_settings
from app.infrastructure.database.models import CuratedModel, Provider
from sqlalchemy import select

from app.domain.providers.model_browser_service import (
    ModelBrowserFilters,
    ModelBrowserResult,
)
from app.domain.providers.discovery_service import provider_discovery_service
from app.domain.providers.provider_endpoints import resolve_endpoint
from app.domain.providers.openrouter_browser import openrouter_model_browser
from app.domain.providers.ollama_browser import ollama_model_browser
from app.domain.providers.ollama_cloud_browser import ollama_cloud_model_browser
from app.domain.providers.deepseek_browser import deepseek_model_browser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/providers", tags=["provider-models"])


def _endpoint_or_refuse(provider: Provider) -> str:
    """The endpoint a model browser dials — the row's, else its type's canonical one, else a 409.

    **THE SAME RULE THE DISCOVERY BRANCHES IN THIS FILE FOLLOW** (`resolve_endpoint`): a browser is
    handed a RESOLVED address — never the raw row value, and never a literal of its own. The browsers
    used to carry a `DEFAULT_BASE_URL` per class, so a row with no endpoint still dialled
    `http://localhost:11434` / `https://ollama.com` — an address nobody configured. They are gone
    (2026-10-11, the `ollama_cloud` ruling); a row that declares nothing and whose type has no
    canonical endpoint is REPORTED here, in the same shape as this file's discovery branches.
    """
    endpoint = resolve_endpoint(provider.provider_type, provider.base_url, provider.name)
    if endpoint is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"The '{provider.name}' row declares no endpoint, and the "
                f"'{provider.provider_type}' type has none — set base_url on the row"
            ),
        )
    return endpoint


@router.get("/{provider_id}/models/browse")
async def browse_models(
    provider_id: int,
    db: AsyncSession = Depends(get_db_session),
    # Search filters
    search: Optional[str] = Query(None, description="Search query (matches name, id, description)"),
    capabilities: Optional[List[str]] = Query(None, description="Required capabilities"),
    min_context: Optional[int] = Query(None, description="Minimum context length in tokens"),
    max_context: Optional[int] = Query(None, description="Maximum context length in tokens"),
    free_only: bool = Query(False, description="Only show free models"),
    max_price_prompt: Optional[float] = Query(None, description="Max price per 1K prompt tokens"),
    max_price_completion: Optional[float] = Query(None, description="Max price per 1K completion tokens"),
    # Pagination
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    # Sorting
    sort_by: str = Query("name", description="Field to sort by"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$", description="Sort order"),
):
    """
    Browse models with filtering and pagination.
    
    **Use Cases:**
    - Discover available models for a provider
    - Search for models by name or capability
    - Filter by context length, pricing, features
    - Paginated results for large model lists
    
    **Example:**
    ```
    GET /api/v1/providers/1/models/browse?search=nemotron&free_only=true&page=1&page_size=25
    ```
    
    **Response:**
    ```json
    {
      "models": [...],
      "total": 15,
      "page": 1,
      "page_size": 25,
      "total_pages": 1,
      "has_more": false,
      "filters_applied": {...},
      "from_cache": true
    }
    ```
    """
    # Check if provider exists
    query = select(Provider).where(Provider.id == provider_id)
    query_result = await db.execute(query)
    provider = query_result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found",
        )
    
    # Get API key (Ollama is local-only and doesn't need one)
    api_key = await _get_provider_api_key(db, provider_id, provider.provider_type)
    
    if not api_key and provider.provider_type not in ("ollama", "ollama_cloud") and provider.name != "llama":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{provider.name} API key not configured",
        )
    if provider.provider_type == "ollama_cloud" and not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{provider.name} (Ollama Cloud) API key not configured",
        )
    # Keyed providers (openrouter/deepseek/openai/anthropic) have a key here;
    # local Ollama is keyless by design (browse via base_url) — the checks
    # above already raised clean 400s for every keyless non-ollama case.
    # (Was: assert api_key is not None — blew up on local Ollama: 10 hits,
    # AssertionError → 500 → "commit failed, rolling back" in get_db_session.)
    if api_key is None and provider.provider_type not in ("ollama", "ollama_cloud"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{provider.name} API key not configured",
        )

    # Build filters
    filters = ModelBrowserFilters(
        search=search,
        capabilities=capabilities,
        min_context_length=min_context,
        max_context_length=max_context,
        free_only=free_only,
        max_price_prompt=max_price_prompt,
        max_price_completion=max_price_completion,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    
    # Browse models based on provider type
    try:
        if provider.provider_type == "openrouter":
            if api_key is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{provider.name} API key not configured",
                )
            result = await openrouter_model_browser.browse_models(
                db=db,
                provider_id=provider_id,
                api_key=api_key,
                filters=filters,
            )
        elif provider.provider_type == "ollama":
            result = await ollama_model_browser.browse_models(
                db=db,
                provider_id=provider_id,
                base_url=_endpoint_or_refuse(provider),
                api_key=api_key,
                filters=filters,
            )
        elif provider.provider_type == "ollama_cloud":
            result = await ollama_cloud_model_browser.browse_models(
                db=db,
                provider_id=provider_id,
                base_url=_endpoint_or_refuse(provider),
                api_key=api_key,
                filters=filters,
            )
        elif provider.provider_type == "deepseek":
            if api_key is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{provider.name} API key not configured",
                )
            result = await deepseek_model_browser.browse_models(
                db=db,
                provider_id=provider_id,
                api_key=api_key,
                filters=filters,
            )
        elif provider.provider_type == "openai" and provider.name == "llama":
            # THE KEYLESS LOCAL ROW (2026-09-09): llama.cpp's /v1/models
            # lists the loaded GGUF. A local server holds a handful of
            # models — honor the search, then paginate into the browse
            # shape (the discovery caches with the short TTL).
            endpoint = resolve_endpoint(provider.provider_type, provider.base_url, provider.name)
            if endpoint is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"The '{provider.name}' row declares no endpoint, and the "
                        f"'{provider.provider_type}' type has none — set base_url on the row"
                    ),
                )
            discovery = await provider_discovery_service.discover_openai_compat_models(
                db, provider_id, endpoint, False
            )
            all_models = discovery.get("models", [])
            if search:
                needle = search.lower()
                all_models = [
                    m for m in all_models
                    if needle in (str(m.get("id", "")) + str(m.get("display_name", ""))).lower()
                ]
            total = len(all_models)
            total_pages = max((total + page_size - 1) // page_size, 1)
            page_models = all_models[(page - 1) * page_size : page * page_size]
            result = ModelBrowserResult(
                models=page_models,
                total=total,
                page=page,
                page_size=page_size,
                total_pages=total_pages,
                has_more=page < total_pages,
                filters_applied={},
                from_cache=discovery.get("from_cache", False),
            )
        else:
            # For other providers, return not implemented
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail=f"Model browsing not yet implemented for {provider.provider_type}",
            )
        
        # Enrich each model with curated status (verified) so the
        # UI can badge curated models alongside the raw catalog.
        curated = {}
        curated_rows = await db.execute(
            select(CuratedModel).where(CuratedModel.provider_id == provider_id)
        )
        for cm in curated_rows.scalars().all():
            curated[cm.model_id] = {
                "is_curated": True,
                "verified": bool(cm.verified),
            }

        enriched_models = []
        for m in result.models or []:
            row = dict(m) if isinstance(m, dict) else m
            if isinstance(row, dict):
                _lookup_key = row.get("id") or row.get("name")
                row["curated"] = curated.get(str(_lookup_key)) if _lookup_key else None
            enriched_models.append(row)

        return {
            "models": enriched_models,
            "total": result.total,
            "page": result.page,
            "page_size": result.page_size,
            "total_pages": result.total_pages,
            "has_more": result.has_more,
            "filters_applied": result.filters_applied,
            "from_cache": result.from_cache,
            "provider_name": provider.name,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Model browse error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Model browsing failed: {str(e)}",
        )


# NOTE: The capabilities route MUST be defined before the {model_id:path} route
# to avoid the catch-all path parameter intercepting "capabilities" as a model_id.


@router.get("/{provider_id}/models/capabilities")
async def get_available_capabilities(
    provider_id: int,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get list of available capabilities for filtering.
    
    **Use Cases:**
    - Populate filter dropdowns
    - Discover model features
    
    **Example:**
    ```
    GET /api/v1/providers/1/models/capabilities
    ```
    
    **Response:**
    ```json
    {
      "capabilities": [
        {"id": "function_calling", "name": "Function Calling", "count": 45},
        {"id": "reasoning", "name": "Reasoning", "count": 12},
        ...
      ],
      "provider_name": "OpenRouter"
    }
    ```
    """
    # Check if provider exists
    query = select(Provider).where(Provider.id == provider_id)
    result = await db.execute(query)
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found",
        )
    
    # Get API key (Ollama is local-only and doesn't need one)
    api_key = await _get_provider_api_key(db, provider_id, provider.provider_type)
    
    if not api_key and provider.provider_type not in ("ollama", "ollama_cloud") and provider.name != "llama":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{provider.name} API key not configured",
        )
    if provider.provider_type == "ollama_cloud" and not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{provider.name} (Ollama Cloud) API key not configured",
        )
    assert api_key is not None

    # Get capabilities based on provider type
    try:
        if provider.provider_type == "openrouter":
            capabilities = await openrouter_model_browser.get_available_capabilities(
                db=db,
                provider_id=provider_id,
                api_key=api_key,
            )
        elif provider.provider_type == "ollama":
            capabilities = await ollama_model_browser.get_available_capabilities(
                db=db,
                provider_id=provider_id,
                base_url=_endpoint_or_refuse(provider),
                api_key=api_key,
            )
        elif provider.provider_type == "deepseek":
            capabilities = await deepseek_model_browser.get_available_capabilities(
                db=db,
                provider_id=provider_id,
                api_key=api_key,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail=f"Capabilities not yet implemented for {provider.provider_type}",
            )
        
        # Format with counts (would need to fetch models to count)
        # For now, return simple list
        return {
            "capabilities": [
                {"id": cap, "name": cap.replace("_", " ").title()}
                for cap in capabilities
            ],
            "total": len(capabilities),
            "provider_name": provider.name,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Capabilities error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get capabilities: {str(e)}",
        )


@router.get("/{provider_id}/models/{model_id:path}")
async def get_model_details(
    provider_id: int,
    model_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get detailed information about a specific model.
    
    **Use Cases:**
    - View full model specifications
    - Check capabilities before selection
    - Get pricing information
    
    **Example:**
    ```
    GET /api/v1/providers/1/models/nvidia/nemotron-3-super-120b-a12b:free
    ```
    """
    # Check if provider exists
    query = select(Provider).where(Provider.id == provider_id)
    query_result = await db.execute(query)
    provider = query_result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found",
        )
    
    # Get API key (Ollama is local-only and doesn't need one)
    api_key = await _get_provider_api_key(db, provider_id, provider.provider_type)
    
    if not api_key and provider.provider_type not in ("ollama", "ollama_cloud") and provider.name != "llama":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{provider.name} API key not configured",
        )
    if provider.provider_type == "ollama_cloud" and not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{provider.name} (Ollama Cloud) API key not configured",
        )
    assert api_key is not None

    # Get model details based on provider type
    try:
        if provider.provider_type == "openrouter":
            model_details = await openrouter_model_browser.get_model_details(
                db=db,
                provider_id=provider_id,
                api_key=api_key,
                model_id=model_id,
            )
        elif provider.provider_type == "ollama":
            model_details = await ollama_model_browser.get_model_details(
                db=db,
                provider_id=provider_id,
                base_url=_endpoint_or_refuse(provider),
                api_key=api_key,
                model_id=model_id,
            )
        elif provider.provider_type == "deepseek":
            model_details = await deepseek_model_browser.get_model_details(
                db=db,
                provider_id=provider_id,
                api_key=api_key,
                model_id=model_id,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail=f"Model details not yet implemented for {provider.provider_type}",
            )
        
        if not model_details:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model {model_id} not found",
            )
        
        return {
            "model": model_details,
            "provider_name": provider.name,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Model details error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get model details: {str(e)}",
        )


async def _get_provider_api_key(
    db: AsyncSession,
    provider_id: int,
    provider_type: str,
) -> Optional[str]:
    """
    Get API key for provider (from database or environment).
    
    Args:
        db: Database session
        provider_id: Provider ID
        provider_type: Provider type
        
    Returns:
        API key or None
    """
    
    # .env (EnvKeyStore) — the DB column was removed
    from app.domain.providers.env_key_store import env_key_store
    env_key = env_key_store.get_key(provider_type)
    if env_key:
        return env_key

    # Fallback to settings
    settings = get_settings()
    if provider_type == "openrouter":
        return settings.openrouter_api_key
    elif provider_type == "deepseek":
        return settings.deepseek_api_key
    elif provider_type == "openai":
        return settings.openai_api_key
    elif provider_type == "anthropic":
        return settings.anthropic_api_key
    elif provider_type == "ollama_cloud":
        return settings.ollama_cloud_api_key
    
    return None
