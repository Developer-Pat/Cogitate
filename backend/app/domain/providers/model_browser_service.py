"""
Model Browser Service.

Generic interface for browsing provider models with search, filtering, and pagination.
"""

import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field


logger = logging.getLogger(__name__)


@dataclass
class ModelBrowserFilters:
    """
    Filters for model browsing.
    
    Attributes:
        search: Search query (matches name, id, description)
        capabilities: List of required capabilities
        min_context_length: Minimum context length in tokens
        max_context_length: Maximum context length in tokens
        free_only: Only show free models
        max_price_prompt: Maximum price per 1K prompt tokens (USD)
        max_price_completion: Maximum price per 1K completion tokens (USD)
        providers: List of provider names to filter by
        page: Page number (1-indexed)
        page_size: Number of items per page
        sort_by: Field to sort by
        sort_order: Sort order (asc or desc)
    """
    search: Optional[str] = None
    capabilities: Optional[List[str]] = None
    min_context_length: Optional[int] = None
    max_context_length: Optional[int] = None
    free_only: bool = False
    max_price_prompt: Optional[float] = None
    max_price_completion: Optional[float] = None
    providers: Optional[List[str]] = None
    page: int = 1
    page_size: int = 50
    sort_by: str = "name"
    sort_order: str = "asc"


@dataclass
class ModelBrowserResult:
    """
    Result from model browsing.
    
    Attributes:
        models: List of model dictionaries
        total: Total number of models matching filters
        page: Current page number
        page_size: Number of items per page
        total_pages: Total number of pages
        has_more: Whether there are more pages
        filters_applied: Filters that were applied
        from_cache: Whether results came from cache
    """
    models: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_more: bool
    filters_applied: Dict[str, Any] = field(default_factory=dict)
    from_cache: bool = False


class ModelBrowserService:
    """
    Generic interface for model browsing across providers.
    
    Provides:
    - Search functionality
    - Capability filtering
    - Context length filtering
    - Price filtering
    - Pagination
    - Sorting
    """
    
    async def browse_models(
        self,
        provider_id: int,
        filters: ModelBrowserFilters | None = None,
    ) -> ModelBrowserResult:
        """
        Browse models with filtering and pagination.
        
        Args:
            provider_id: Provider ID
            filters: Browser filters
            
        Returns:
            Paginated model results
        """
        raise NotImplementedError("Subclasses must implement browse_models")
    
    async def get_model_details(
        self,
        provider_id: int,
        model_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific model.
        
        Args:
            provider_id: Provider ID
            model_id: Model identifier
            
        Returns:
            Model details dictionary or None if not found
        """
        raise NotImplementedError("Subclasses must implement get_model_details")
    
    async def get_available_capabilities(
        self,
        provider_id: int,
    ) -> List[str]:
        """
        Get list of available capabilities for filtering.
        
        Args:
            provider_id: Provider ID
            
        Returns:
            List of capability names
        """
        raise NotImplementedError("Subclasses must implement get_available_capabilities")
    
    def _apply_filters(
        self,
        models: List[Dict[str, Any]],
        filters: ModelBrowserFilters,
    ) -> List[Dict[str, Any]]:
        """
        Apply filters to model list.
        
        Args:
            models: List of models to filter
            filters: Filter criteria
            
        Returns:
            Filtered list of models
        """
        filtered = models
        
        # Search filter
        if filters.search:
            search_lower = filters.search.lower()
            filtered = [
                m for m in filtered
                if (search_lower in m.get("id", "").lower() or
                    search_lower in m.get("name", "").lower() or
                    search_lower in m.get("description", "").lower())
            ]
        
        # Capabilities filter
        if filters.capabilities:
            filtered = [
                m for m in filtered
                if all(cap in self._get_model_capabilities(m) for cap in filters.capabilities)
            ]
        
        # Context length filters
        if filters.min_context_length is not None:
            filtered = [
                m for m in filtered
                if (m.get("context_length") or 0) >= filters.min_context_length
            ]
        
        if filters.max_context_length is not None:
            filtered = [
                m for m in filtered
                if (m.get("context_length") or float("inf")) <= filters.max_context_length
            ]
        
        # Price filters
        if filters.free_only:
            filtered = [
                m for m in filtered
                if (m.get("pricing_prompt", 0) == 0 and 
                    m.get("pricing_completion", 0) == 0)
            ]
        
        if filters.max_price_prompt is not None:
            filtered = [
                m for m in filtered
                if (m.get("pricing_prompt", 0) or 0) <= filters.max_price_prompt
            ]
        
        if filters.max_price_completion is not None:
            filtered = [
                m for m in filtered
                if (m.get("pricing_completion", 0) or 0) <= filters.max_price_completion
            ]
        
        # Provider filter
        if filters.providers:
            filtered = [
                m for m in filtered
                if m.get("top_provider", "").lower() in [p.lower() for p in filters.providers]
            ]
        
        return filtered
    
    def _apply_sorting(
        self,
        models: List[Dict[str, Any]],
        sort_by: str,
        sort_order: str,
    ) -> List[Dict[str, Any]]:
        """
        Apply sorting to model list.
        
        Args:
            models: List of models to sort
            sort_by: Field to sort by
            sort_order: Sort order (asc or desc)
            
        Returns:
            Sorted list of models
        """
        reverse = sort_order.lower() == "desc"
        
        # Map sort keys to model fields
        sort_key_map = {
            "name": lambda m: m.get("name", m.get("id", "")).lower(),
            "context_length": lambda m: m.get("context_length") or 0,
            "pricing_prompt": lambda m: m.get("pricing_prompt") or 0,
            "pricing_completion": lambda m: m.get("pricing_completion") or 0,
            "provider": lambda m: m.get("top_provider", "").lower(),
        }
        
        sort_key = sort_key_map.get(sort_by, sort_key_map["name"])
        
        return sorted(models, key=sort_key, reverse=reverse)
    
    def _paginate(
        self,
        models: List[Dict[str, Any]],
        page: int,
        page_size: int,
    ) -> tuple[List[Dict[str, Any]], int, bool]:
        """
        Paginate model list.
        
        Args:
            models: List of models to paginate
            page: Page number (1-indexed)
            page_size: Number of items per page
            
        Returns:
            Tuple of (paginated models, total count, has_more)
        """
        total = len(models)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        
        paginated = models[start_idx:end_idx]
        has_more = end_idx < total
        
        return paginated, total, has_more
    
    def _get_model_capabilities(self, model: Dict[str, Any]) -> List[str]:
        """
        Extract capabilities from model dictionary.
        
        Args:
            model: Model dictionary
            
        Returns:
            List of capability names
        """
        capabilities = []
        
        if model.get("function_calling"):
            capabilities.append("function_calling")
        
        if model.get("in_context_training"):
            capabilities.append("in_context_training")
        
        # Check for reasoning capability (from provider-specific fields)
        if model.get("_raw", {}).get("architecture", {}).get("instruct_type") == "reasoning":
            capabilities.append("reasoning")
        
        # Add modality as capability
        modality = model.get("modality", "")
        if "image" in modality.lower():
            capabilities.append("vision")
        if "code" in modality.lower():
            capabilities.append("code")
        
        return capabilities


# Singleton instance (to be replaced with provider-specific implementations)
model_browser_service = ModelBrowserService()
