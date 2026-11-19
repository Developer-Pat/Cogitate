"""
OpenRouter Model Browser.

OpenRouter-specific implementation of model browser service.
"""

import logging
from typing import Optional, List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.providers.model_browser_service import (
    ModelBrowserService,
    ModelBrowserFilters,
    ModelBrowserResult,
)
from app.domain.providers.openrouter_client import create_openrouter_client, OpenRouterAPIError
from app.domain.providers.cache_service import provider_model_cache_service

logger = logging.getLogger(__name__)


class OpenRouterModelBrowser(ModelBrowserService):
    """
    OpenRouter-specific model browser implementation.
    
    Features:
    - Search across 344+ OpenRouter models
    - Filter by capabilities, context length, pricing
    - Pagination support
    - Caching integration
    """
    
    async def browse_models(  # type: ignore[override]
        self,
        db: AsyncSession,
        provider_id: int,
        api_key: str,
        filters: ModelBrowserFilters | None = None,
    ) -> ModelBrowserResult:
        """
        Browse OpenRouter models with filtering and pagination.
        
        Args:
            db: Database session
            provider_id: Provider ID
            api_key: OpenRouter API key
            filters: Browser filters
            
        Returns:
            Paginated model results
        """
        if filters is None:
            filters = ModelBrowserFilters()
        
        # Fetch models (from cache or API)
        models = await self._fetch_models(db, provider_id, api_key)
        
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
            f"✅ OpenRouter model browse: {len(paginated_models)}/{total} models "
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
            from_cache=True,  # We always use cache for browsing
        )
    
    async def get_model_details(  # type: ignore[override]
        self,
        db: AsyncSession,
        provider_id: int,
        api_key: str,
        model_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific OpenRouter model.
        
        Args:
            db: Database session
            provider_id: Provider ID
            api_key: OpenRouter API key
            model_id: Model identifier (e.g., "nvidia/nemotron-3-super-120b-a12b:free")
            
        Returns:
            Model details dictionary or None if not found
        """
        # Fetch all models
        models = await self._fetch_models(db, provider_id, api_key)
        
        # Find specific model
        model = next((m for m in models if m.get("id") == model_id), None)
        
        if model:
            logger.info(f"✅ Found OpenRouter model details: {model_id}")
            # Add additional details
            return self._enrich_model_details(model)
        
        logger.warning(f"⚠️ OpenRouter model not found: {model_id}")
        return None
    
    async def get_available_capabilities(  # type: ignore[override]
        self,
        db: AsyncSession,
        provider_id: int,
        api_key: str,
    ) -> List[str]:
        """
        Get list of available capabilities for OpenRouter models.
        
        Args:
            db: Database session
            provider_id: Provider ID
            api_key: OpenRouter API key
            
        Returns:
            List of capability names
        """
        models = await self._fetch_models(db, provider_id, api_key)
        
        # Collect all unique capabilities
        all_capabilities = set()
        for model in models:
            caps = self._get_model_capabilities(model)
            all_capabilities.update(caps)
        
        # Sort for consistent ordering
        return sorted(list(all_capabilities))
    
    async def _fetch_models(
        self,
        db: AsyncSession,
        provider_id: int,
        api_key: str,
    ) -> List[Dict[str, Any]]:
        """
        Fetch models from cache or API.
        
        Args:
            db: Database session
            provider_id: Provider ID
            api_key: OpenRouter API key
            
        Returns:
            List of model dictionaries
        """
        # Try cache first
        cached_models = await provider_model_cache_service.get_cached_models(
            db, provider_id, force_refresh=False
        )
        
        if cached_models:
            return cached_models
        
        # Fetch from API
        logger.info("🔄 Fetching fresh OpenRouter models for browser...")
        
        try:
            client = create_openrouter_client(api_key)
            models = await client.list_models()
            
            if models:
                # Cache for future use
                await provider_model_cache_service.cache_models(
                    db, provider_id, models, ttl_hours=168  # 7 days
                )
                await db.commit()
            
            return models or []
            
        except OpenRouterAPIError as e:
            logger.error(f"❌ OpenRouter fetch error: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Unexpected error fetching OpenRouter models: {e}")
            return []
    
    def _enrich_model_details(self, model: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich model with additional details.
        
        Args:
            model: Model dictionary
            
        Returns:
            Enriched model dictionary
        """
        # Extract capabilities
        capabilities = self._get_model_capabilities(model)
        
        # Build enriched details
        enriched = {
            **model,
            "capabilities": capabilities,
            "capability_badges": self._format_capability_badges(capabilities),
        }
        
        # Add context length category
        context_length = model.get("context_length") or 0
        if context_length >= 200000:
            enriched["context_category"] = "ultra_long"
        elif context_length >= 100000:
            enriched["context_category"] = "very_long"
        elif context_length >= 32000:
            enriched["context_category"] = "long"
        else:
            enriched["context_category"] = "standard"
        
        return enriched
    
    def _format_capability_badges(self, capabilities: List[str]) -> List[Dict[str, str]]:
        """
        Format capabilities as badge data.
        
        Args:
            capabilities: List of capability names
            
        Returns:
            List of badge dictionaries with label, color, icon
        """
        badge_config = {
            "function_calling": {
                "label": "Function Calling",
                "color": "blue",
                "icon": "⚡",
            },
            "reasoning": {
                "label": "Reasoning",
                "color": "purple",
                "icon": "🧠",
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
            "in_context_training": {
                "label": "In-Context Training",
                "color": "pink",
                "icon": "📚",
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
openrouter_model_browser = OpenRouterModelBrowser()
