"""
Ollama Cloud Model Browser.

Ollama Cloud-specific implementation of model browser service.
Ollama Cloud is the hosted Ollama API at https://ollama.com — the native
/api/tags endpoint works with a Bearer API key (same shape as local).

Key difference from local Ollama: requires api_key (Bearer token from
ollama.com account) and uses the cloud base URL.
"""

import logging
from typing import List, Dict, Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.providers.model_browser_service import (
    ModelBrowserService,
    ModelBrowserFilters,
    ModelBrowserResult,
)
from app.domain.providers.cache_service import provider_model_cache_service
from app.domain.providers.provider_endpoints import native_root

logger = logging.getLogger(__name__)


class OllamaCloudModelBrowser(ModelBrowserService):
    """
    Ollama Cloud model browser implementation.

    Features:
    - Browse Ollama Cloud models (hosted at https://ollama.com)
    - Bearer-token auth via API key
    - Filter by name, architecture, parameter size
    - Pagination support
    - Caching integration (short TTL since models change frequently)

    **THE ENDPOINT IS NOT THIS CLASS'S TO GUESS** (2026-10-11, the `ollama_cloud` ruling): this browser
    carries no `DEFAULT_BASE_URL`. The address comes from the caller, resolved by
    `provider_endpoints.resolve_endpoint` — the row's, else the type's canonical one. A default here
    was a backup of that decision, and it disagreed with the registry (it said `https://ollama.com`
    where the type's canonical endpoint is `https://ollama.com/v1`).
    """

    async def browse_models(  # type: ignore[override]
        self,
        db: AsyncSession,
        provider_id: int,
        base_url: str,
        api_key: str | None = None,
        filters: ModelBrowserFilters | None = None,
    ) -> ModelBrowserResult:
        """
        Browse Ollama Cloud models with filtering and pagination.

        Args:
            db: Database session
            provider_id: Provider ID
            base_url: the RESOLVED endpoint (`provider_endpoints.resolve_endpoint`) — the row's,
                else the type's canonical one. No default: a backup here is how a configuration
                gap passes for an address somebody chose (the service-literals arc).
            api_key: Ollama Cloud API key (required)
            filters: Browser filters

        Returns:
            Paginated model results
        """
        if filters is None:
            filters = ModelBrowserFilters()

        url = base_url

        # Fetch models (from cache or API)
        models = await self._fetch_models(db, provider_id, url, api_key)

        if not models:
            return ModelBrowserResult(
                models=[],
                total=0,
                page=filters.page,
                page_size=filters.page_size,
                total_pages=0,
                has_more=False,
                filters_applied=self._filters_to_dict(filters),
                from_cache=False,
            )

        # Apply filters
        filtered_models = self._apply_filters(models, filters)

        # Apply sorting
        sorted_models = self._apply_sorting(
            filtered_models,
            filters.sort_by,
            filters.sort_order,
        )

        # Paginate
        paginated_models, total, has_more = self._paginate(
            sorted_models,
            filters.page,
            filters.page_size,
        )

        total_pages = (total + filters.page_size - 1) // filters.page_size

        logger.info(
            f"✅ Ollama Cloud model browse: {len(paginated_models)}/{total} models "
            f"(page {filters.page}/{total_pages})"
        )

        return ModelBrowserResult(
            models=paginated_models,
            total=total,
            page=filters.page,
            page_size=filters.page_size,
            total_pages=total_pages,
            has_more=has_more,
            filters_applied=self._filters_to_dict(filters),
            from_cache=True,
        )

    async def _fetch_models(
        self,
        db: AsyncSession,
        provider_id: int,
        base_url: str,
        api_key: str | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch models from cache or Ollama Cloud API.

        Args:
            db: Database session
            provider_id: Provider ID
            base_url: Ollama Cloud API base URL
            api_key: Ollama Cloud API key (Bearer token)

        Returns:
            List of model dictionaries
        """
        # Try cache first
        cached_models = await provider_model_cache_service.get_cached_models(
            db, provider_id, force_refresh=False
        )

        if cached_models:
            # Normalize cached data: flatten nested pricing to flat fields
            for model in cached_models:
                pricing = model.get("pricing", {})
                if isinstance(pricing, dict):
                    model["pricing_prompt"] = pricing.get("prompt")
                    model["pricing_completion"] = pricing.get("completion")
            return cached_models

        # Fetch from API
        logger.info("🔄 Fetching fresh Ollama Cloud models for browser...")

        if not api_key:
            logger.warning("⚠️ No Ollama Cloud API key provided — cannot fetch models")
            return []

        try:
            headers = {"Authorization": f"Bearer {api_key}"}
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{native_root(base_url)}/api/tags", headers=headers
                )
                response.raise_for_status()
                data = response.json()

                raw_models = data.get("models", [])

                # Transform to our format
                models = []
                for model in raw_models:
                    model_name = model.get("name", "")
                    models.append({
                        "id": model_name,
                        "name": model_name,
                        "display_name": model_name.split(":")[0],
                        "description": f"Ollama Cloud model: {model_name}",
                        "context_length": None,
                        "architecture": model.get("details", {}).get("family"),
                        "modality": "text",
                        "function_calling": False,
                        "pricing_prompt": 0,
                        "pricing_completion": 0,
                        "top_provider": "ollama_cloud",
                        "size": model.get("size", 0),
                        "parameter_size": model.get("details", {}).get("parameter_size"),
                        "quantization": model.get("details", {}).get("quantization_level"),
                    })

                if models:
                    # Cache with short TTL (1 hour) since models change frequently
                    await provider_model_cache_service.cache_models(
                        db, provider_id, models, ttl_hours=1
                    )
                    await db.commit()

                return models

        except httpx.HTTPStatusError as e:
            logger.warning(f"⚠️ Ollama Cloud API error: {e.response.status_code} — {e}")
            return []
        except httpx.ConnectError as e:
            logger.warning(f"⚠️ Ollama Cloud not reachable: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Unexpected error fetching Ollama Cloud models: {e}")
            return []

    def _filters_to_dict(self, filters: ModelBrowserFilters) -> Dict[str, Any]:
        """Convert filters to dictionary for response."""
        return {
            "search": filters.search,
            "capabilities": filters.capabilities,
            "min_context_length": filters.min_context_length,
            "max_context_length": filters.max_context_length,
            "free_only": filters.free_only,
            "max_price_prompt": filters.max_price_prompt,
            "max_price_completion": filters.max_price_completion,
            "providers": filters.providers,
            "page": filters.page,
            "page_size": filters.page_size,
            "sort_by": filters.sort_by,
            "sort_order": filters.sort_order,
        }


# Singleton instance
ollama_cloud_model_browser = OllamaCloudModelBrowser()
