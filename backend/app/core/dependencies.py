"""
Application dependency injection.

Provides reusable dependencies for FastAPI route handlers.
"""

from collections.abc import AsyncGenerator
from functools import lru_cache
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db_session, get_documents_session


def get_app_settings() -> Settings:
    """
    Dependency to get application settings.

    Returns:
        Settings: Application settings instance
    """
    return get_settings()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get database session for main app.

    Delegates to get_db_session() from database module.

    Yields:
        AsyncSession: Database session
    """
    async for session in get_db_session():
        yield session


async def get_documents_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get database session for documents.

    Delegates to get_documents_session() from database module.

    Yields:
        AsyncSession: Documents database session
    """
    async for session in get_documents_session():
        yield session


class CacheService:
    """
    Simple in-memory cache service for MVP.

    Will be replaced with Redis in Phase 2.
    """

    def __init__(self, ttl_seconds: int = 300):
        self._cache: dict = {}
        self._ttl = ttl_seconds

    def get(self, key: str) -> Any:  # noqa: ANN401
        """Get value from cache."""
        return self._cache.get(key)

    def set(self, key: str, value: Any) -> None:  # noqa: ANN401
        """Set value in cache."""
        self._cache[key] = value

    def delete(self, key: str) -> None:
        """Delete value from cache."""
        self._cache.pop(key, None)

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()


@lru_cache
def get_cache_service() -> CacheService:
    """
    Dependency to get cache service instance.

    Returns cached singleton instance.

    Returns:
        CacheService: In-memory cache service
    """
    settings = get_settings()
    return CacheService(ttl_seconds=settings.cache_ttl_seconds)


# Type aliases for dependency injection
SettingsDependency = Settings
CacheDependency = CacheService
