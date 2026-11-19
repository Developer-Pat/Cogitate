"""
Provider Model Cache Service.

Manages caching of discovered models to avoid repeated API calls.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.infrastructure.database.models import Provider, ProviderModelCache

logger = logging.getLogger(__name__)


class ProviderModelCacheService:
    """
    Service for managing provider model cache.

    Provides caching functionality to avoid repeated API calls to provider APIs.
    """

    # Default cache TTL: 7 days (168 hours) for development
    # Change to 24 for production
    DEFAULT_TTL_HOURS = 168

    def __init__(self, ttl_hours: int = DEFAULT_TTL_HOURS):
        """
        Initialize cache service.
        
        Args:
            ttl_hours: Cache time-to-live in hours (default: 24)
        """
        self.ttl_hours = ttl_hours
    
    async def get_cached_models(
        self, 
        db: AsyncSession, 
        provider_id: int,
        force_refresh: bool = False,
        limit: Optional[int] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached models for a provider.
        
        Args:
            db: Database session
            provider_id: Provider ID
            force_refresh: If True, ignore cache and return None to force refresh
            limit: Optional cap on the number of cached entries returned
            
        Returns:
            List of cached models or None if cache miss/expired
        """
        if force_refresh:
            logger.info(f"🔄 Force refresh requested for provider {provider_id}, skipping cache")
            return None
        
        query = select(ProviderModelCache).where(
            ProviderModelCache.provider_id == provider_id,
            ProviderModelCache.is_cached
        ).limit(limit) if limit is not None else select(ProviderModelCache).where(
            ProviderModelCache.provider_id == provider_id,
            ProviderModelCache.is_cached
        )
        
        result = await db.execute(query)
        cached_entries = result.scalars().all()
        
        if not cached_entries:
            logger.debug(f"📦 Cache miss for provider {provider_id}")
            return None
        
        # Check if cache is expired
        now = datetime.now(timezone.utc)
        expired_entries = []
        for e in cached_entries:
            if e.expires_at:
                expires_at = e.expires_at
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if expires_at < now:
                    expired_entries.append(e)

        if expired_entries:
            logger.info(f"⏰ Cache expired for provider {provider_id} ({len(expired_entries)} entries)")
            # Clean up expired entries
            await self._clear_cache(db, provider_id)
            return None
        
        # Convert to dict format
        models = []
        for entry in cached_entries:
            models.append({
                "id": entry.model_id,
                "name": entry.name,
                "display_name": entry.display_name,
                "description": entry.description,
                "context_length": entry.context_length,
                "pricing": {
                    "prompt": entry.pricing_prompt,
                    "completion": entry.pricing_completion,
                },
                "top_provider": entry.top_provider,
                "architecture": entry.architecture,
                "modality": entry.modality,
                "function_calling": entry.function_calling,
                "in_context_training": entry.in_context_training,
                "cached_at": entry.cached_at.isoformat(),
                "expires_at": entry.expires_at.isoformat() if entry.expires_at else None,
            })
        
        logger.info(f"✅ Cache hit for provider {provider_id}: {len(models)} models")
        return models
    
    async def pricing_for_model(
        self,
        db: AsyncSession,
        provider: str,
        model: str,
    ) -> Optional[Dict[str, float]]:
        """The provider's own published price for `model`, PER 1K TOKENS, or None.

        This is the price source the cost path reads. `ProviderService.PRICING` — eleven
        hand-added entries — is the FALLBACK, not the source: it drifted from what the
        providers charge, which is why the usage page showed $0.00 for the model actually
        in use while the real price sat here, unread.

        IDENTITY: the wire carries `provider/model` (`openrouter/inclusionai/ling-3.0-flash`)
        while the catalog stores the id the PROVIDER uses (`inclusionai/ling-3.0-flash`), so
        both forms are matched, in one query. Only the provider's own prefix comes off — an
        id that is itself `vendor/model` keeps its inner slash (the openrouter catalog holds
        `deepseek/deepseek-v4-flash` as-is).

        TWO ANSWERS, and the second is deliberate — a zero is not evidence of a gift:
        * a row with a non-zero price -> that price, converted to the per-1K unit
          `calculate_cost` works in (`pricing_prompt` is stored per TOKEN);
        * a row priced at zero, or no row -> None. The cache writes `0.0` when a provider
          publishes no pricing at all (groq, ollama_cloud, llama all do), so an all-zero row
          cannot be told apart from a genuinely free model. Returning None leaves the
          caller's honest fallback in place instead of asserting a price that never arrived.
        """
        candidates = [model]
        prefix = f"{provider}/"
        if model.startswith(prefix):
            candidates.append(model[len(prefix):])

        rows = (
            await db.execute(
                select(
                    ProviderModelCache.pricing_prompt,
                    ProviderModelCache.pricing_completion,
                )
                .join(Provider, Provider.id == ProviderModelCache.provider_id)
                .where(
                    Provider.name == provider,
                    ProviderModelCache.model_id.in_(candidates),
                )
            )
        ).all()

        for prompt_price, completion_price in rows:
            prompt_per_token = float(prompt_price or 0.0)
            completion_per_token = float(completion_price or 0.0)
            if prompt_per_token > 0 or completion_per_token > 0:
                return {
                    "prompt": prompt_per_token * 1000,
                    "completion": completion_per_token * 1000,
                }
        return None

    async def cache_models(
        self,
        db: AsyncSession,
        provider_id: int,
        models: List[Dict[str, Any]],
        ttl_hours: Optional[int] = None
    ) -> int:
        """
        Cache models for a provider.
        
        Args:
            db: Database session
            provider_id: Provider ID
            models: List of model data to cache
            ttl_hours: Custom TTL in hours (optional)
            
        Returns:
            Number of models cached
        """
        ttl = ttl_hours or self.ttl_hours
        expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl)
        
        # Clear existing cache first
        await self._clear_cache(db, provider_id)
        
        # Add new cache entries
        cached_count = 0
        for model_data in models:
            cache_entry = ProviderModelCache(
                provider_id=provider_id,
                model_id=model_data.get("id", model_data.get("name")),
                name=model_data.get("name", model_data.get("id")),
                display_name=model_data.get("display_name"),
                description=model_data.get("description"),
                context_length=model_data.get("context_length"),
                pricing_prompt=model_data.get("pricing", {}).get("prompt") if isinstance(model_data.get("pricing"), dict) else model_data.get("pricing_prompt"),
                pricing_completion=model_data.get("pricing", {}).get("completion") if isinstance(model_data.get("pricing"), dict) else model_data.get("pricing_completion"),
                top_provider=model_data.get("top_provider"),
                architecture=model_data.get("architecture"),
                modality=model_data.get("modality"),
                function_calling=model_data.get("function_calling", False),
                in_context_training=model_data.get("in_context_training", False),
                expires_at=expires_at,
                raw_data=model_data,
            )
            db.add(cache_entry)
            cached_count += 1
        
        await db.flush()
        logger.info(f"💾 Cached {cached_count} models for provider {provider_id} (TTL: {ttl}h)")

        # Mark curated entries verified when their model_id is in the just-fetched
        # catalog — verified is EARNED by discovery/sync, not chosen by hand.
        try:
            from app.domain.providers.curated_models_service import curated_model_service
            model_ids = [
                str(m.get("id") or m.get("name"))
                for m in models
                if m.get("id") or m.get("name")
            ]
            if model_ids:
                await curated_model_service.mark_verified_for_models(
                    db, provider_id, model_ids
                )
        except Exception as e:
            logger.warning(f"⚠️ Could not sync curated verified flags: {e}")

        return cached_count
    
    async def _clear_cache(self, db: AsyncSession, provider_id: int) -> None:
        """Clear all cached models for a provider."""
        query = delete(ProviderModelCache).where(
            ProviderModelCache.provider_id == provider_id
        )
        await db.execute(query)
        await db.flush()
        logger.debug(f"🗑️ Cleared cache for provider {provider_id}")
    
    async def get_cache_status(
        self,
        db: AsyncSession,
        provider_id: int
    ) -> Dict[str, Any]:
        """
        Get cache status for a provider.
        
        Args:
            db: Database session
            provider_id: Provider ID
            
        Returns:
            Cache status information
        """
        query = select(ProviderModelCache).where(
            ProviderModelCache.provider_id == provider_id
        )
        result = await db.execute(query)
        cached_entries = result.scalars().all()
        
        if not cached_entries:
            return {
                "cached": False,
                "count": 0,
                "cached_at": None,
                "expires_at": None,
                "is_expired": True,
                "ttl_remaining_hours": 0,
            }
        
        # Get earliest cache time and expiry
        cached_at = min(e.cached_at for e in cached_entries)
        expires_at = None
        for e in cached_entries:
            if e.expires_at:
                if expires_at is None or e.expires_at < expires_at:
                    expires_at = e.expires_at

        # Handle timezone-aware comparison
        now = datetime.now(timezone.utc)
        is_expired = True
        ttl_remaining: float = 0.0
        
        if expires_at:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            is_expired = expires_at < now
            ttl_remaining = (expires_at - now).total_seconds() / 3600 if not is_expired else 0.0

        return {
            "cached": True,
            "count": len(cached_entries),
            "cached_at": cached_at.isoformat(),
            "expires_at": expires_at.isoformat() if expires_at else None,
            "is_expired": is_expired,
            "ttl_remaining_hours": round(ttl_remaining, 2),
        }


# Singleton instance
provider_model_cache_service = ProviderModelCacheService()
