"""
Ollama Model Browser.

Ollama-specific implementation of model browser service.
Ollama is local-only and doesn't require an API key.
"""

import logging
from typing import Optional, List, Dict, Any

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


class OllamaModelBrowser(ModelBrowserService):
    """
    Ollama-specific model browser implementation.

    Features:
    - Browse locally installed Ollama models
    - Filter by name, architecture, parameter size
    - Pagination support
    - Caching integration (short TTL since models change frequently)
    """

    # NO `DEFAULT_BASE_URL` (2026-10-11, the `ollama_cloud` ruling): the address is the caller's,
    # resolved by `provider_endpoints.resolve_endpoint` — the row's, else the type's canonical one.
    # Every caller passes the row's value today, so the default was a backup of that decision; a
    # local row that declares no endpoint is REPORTED by the caller, never dialled from here.

    async def browse_models(  # type: ignore[override]
        self,
        db: AsyncSession,
        provider_id: int,
        base_url: str,
        api_key: str | None = None,
        filters: ModelBrowserFilters | None = None,
    ) -> ModelBrowserResult:
        """
        Browse Ollama models with filtering and pagination.

        Args:
            db: Database session
            provider_id: Provider ID
            base_url: the RESOLVED endpoint — the row's, else the type's canonical one
            api_key: Not used for Ollama (local-only)
            filters: Browser filters

        Returns:
            Paginated model results
        """
        if filters is None:
            filters = ModelBrowserFilters()

        url = base_url

        # Fetch models (from cache or API)
        models = await self._fetch_models(db, provider_id, url)

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
            f"✅ Ollama model browse: {len(paginated_models)}/{total} models "
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

    async def get_model_details(  # type: ignore[override]
        self,
        db: AsyncSession,
        provider_id: int,
        base_url: str,
        api_key: str | None = None,
        model_id: str | None = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific Ollama model.

        Args:
            db: Database session
            provider_id: Provider ID
            base_url: the RESOLVED endpoint — the row's, else the type's canonical one
            api_key: Not used for Ollama
            model_id: Model name (e.g., "llama3.1:8b")

        Returns:
            Model details dictionary or None if not found
        """
        if not model_id:
            return None

        url = base_url

        # Try cache first
        models = await self._fetch_models(db, provider_id, url)

        # Find specific model
        model = next((m for m in models if m.get("id") == model_id), None)

        if model:
            logger.info(f"✅ Found Ollama model details: {model_id}")
            return self._enrich_model_details(model)

        # If not in cache, try direct API call for model info
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    f"{native_root(url)}/api/show",
                    json={"name": model_id},
                )
                response.raise_for_status()
                data = response.json()

                details = {
                    "id": model_id,
                    "name": model_id,
                    "display_name": model_id.split(":")[0],
                    "description": f"Ollama model: {model_id}",
                    "context_length": None,
                    "architecture": data.get("details", {}).get("family"),
                    "modality": "text",
                    "function_calling": False,
                    "pricing_prompt": 0,
                    "pricing_completion": 0,
                    "top_provider": "ollama",
                    "license": data.get("license", ""),
                    "parameters": data.get("parameters", ""),
                    "model_info": data.get("model_info", {}),
                }

                logger.info(f"✅ Fetched Ollama model details from API: {model_id}")
                return self._enrich_model_details(details)

        except Exception as e:
            logger.warning(f"⚠️ Could not fetch Ollama model details for {model_id}: {e}")

        return None

    async def get_available_capabilities(  # type: ignore[override]
        self,
        db: AsyncSession,
        provider_id: int,
        base_url: str,
        api_key: str | None = None,
    ) -> List[str]:
        """
        Get list of available capabilities for Ollama models.

        Ollama models are local and generally support basic text completion.
        Capabilities are limited compared to cloud providers.

        Args:
            db: Database session
            provider_id: Provider ID
            api_key: Not used for Ollama
            base_url: Ollama API base URL

        Returns:
            List of capability names
        """
        url = base_url
        models = await self._fetch_models(db, provider_id, url)

        # Collect all unique capabilities
        all_capabilities = set()
        for model in models:
            caps = self._get_model_capabilities(model)
            all_capabilities.update(caps)

        return sorted(list(all_capabilities))

    async def _fetch_models(
        self,
        db: AsyncSession,
        provider_id: int,
        base_url: str,
    ) -> List[Dict[str, Any]]:
        """
        Fetch models from cache or Ollama API.

        Args:
            db: Database session
            provider_id: Provider ID
            base_url: Ollama API base URL

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
        logger.info("🔄 Fetching fresh Ollama models for browser...")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{native_root(base_url)}/api/tags")
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
                        "description": f"Ollama model: {model_name}",
                        "context_length": None,
                        "architecture": model.get("details", {}).get("family"),
                        "modality": "text",
                        "function_calling": False,
                        "pricing_prompt": 0,
                        "pricing_completion": 0,
                        "top_provider": "ollama",
                        "size": model.get("size", 0),
                        "parameter_size": model.get("details", {}).get("parameter_size"),
                        "quantization": model.get("details", {}).get("quantization_level"),
                    })

                if models:
                    # Cache with short TTL (1 hour) since Ollama models change frequently
                    await provider_model_cache_service.cache_models(
                        db, provider_id, models, ttl_hours=1
                    )
                    await db.commit()

                return models

        except httpx.ConnectError as e:
            logger.warning(f"⚠️ Ollama not available: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Unexpected error fetching Ollama models: {e}")
            return []

    def _enrich_model_details(self, model: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich model with additional details.

        Args:
            model: Model dictionary

        Returns:
            Enriched model dictionary
        """
        capabilities = self._get_model_capabilities(model)

        enriched = {
            **model,
            "capabilities": capabilities,
            "capability_badges": self._format_capability_badges(capabilities),
        }

        # Add size info
        size = model.get("size", 0)
        if size:
            enriched["size_formatted"] = self._format_size(size)

        return enriched

    def _format_capability_badges(self, capabilities: List[str]) -> List[Dict[str, str]]:
        """
        Format capabilities as badge data.

        Args:
            capabilities: List of capability names

        Returns:
            List of badge dictionaries
        """
        badge_config = {
            "function_calling": {
                "label": "Function Calling",
                "color": "blue",
                "icon": "⚡",
            },
            "vision": {
                "label": "Vision",
                "color": "green",
                "icon": "👁️",
            },
            "code": {
                "label": "Code",
                "color": "orange",
                "icon": "💻",
            },
        }

        badges = []
        for cap in capabilities:
            config = badge_config.get(cap, {
                "label": cap.replace("_", " ").title(),
                "color": "gray",
                "icon": "📌",
            })
            badges.append({
                "id": cap,
                **config,
            })

        return badges

    def _format_size(self, size_bytes: float) -> str:
        """Format file size in human-readable format."""
        if size_bytes < 0:
            return "Unknown"

        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"

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
ollama_model_browser = OllamaModelBrowser()
