"""
Settings domain services.

Handles persistence and retrieval of user settings.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.infrastructure.database.models import UserSettings
from app.domain.settings.schemas import UserSettingsSchema

logger = logging.getLogger(__name__)

# Default user key until authentication is implemented
DEFAULT_USER_KEY = "default"


class SettingsService:
    """Service for managing user settings."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_settings(self, user_key: str = DEFAULT_USER_KEY) -> Optional[UserSettingsSchema]:
        """
        Get settings for a user.

        Args:
            user_key: User identifier (default: "default")

        Returns:
            User settings or None if not found
        """
        result = await self.db.execute(
            select(UserSettings).where(UserSettings.user_key == user_key)
        )
        settings = result.scalar_one_or_none()

        if settings:
            return UserSettingsSchema.model_validate(settings)
        return None

    async def get_or_create_settings(
        self, user_key: str = DEFAULT_USER_KEY
    ) -> UserSettingsSchema:
        """
        Get settings for a user, creating default settings if not found.

        Args:
            user_key: User identifier (default: "default")

        Returns:
            User settings (existing or newly created)
        """
        result = await self.db.execute(
            select(UserSettings).where(UserSettings.user_key == user_key)
        )
        settings = result.scalar_one_or_none()

        if settings:
            return UserSettingsSchema.model_validate(settings)

        # Create default settings
        settings = UserSettings(
            user_key=user_key,
            settings={},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        self.db.add(settings)
        await self.db.commit()
        await self.db.refresh(settings)

        logger.info(f"Created default settings for user: {user_key}")
        return UserSettingsSchema.model_validate(settings)

    async def update_settings(
        self, settings_data: Dict[str, Any], user_key: str = DEFAULT_USER_KEY
    ) -> UserSettingsSchema:
        """
        Update settings for a user.

        Args:
            settings_data: New settings object
            user_key: User identifier (default: "default")

        Returns:
            Updated user settings
        """
        result = await self.db.execute(
            select(UserSettings).where(UserSettings.user_key == user_key)
        )
        settings = result.scalar_one_or_none()

        if not settings:
            # Create new settings if not found
            settings = UserSettings(
                user_key=user_key,
                settings=settings_data,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            self.db.add(settings)
            logger.info(f"Created new settings for user: {user_key}")
        else:
            # Update existing settings
            settings.settings = settings_data
            settings.updated_at = datetime.now(timezone.utc)
            logger.info(f"Updated settings for user: {user_key}")

        await self.db.commit()
        await self.db.refresh(settings)

        return UserSettingsSchema.model_validate(settings)

    async def delete_settings(self, user_key: str = DEFAULT_USER_KEY) -> bool:
        """
        Delete settings for a user.

        Args:
            user_key: User identifier (default: "default")

        Returns:
            True if deleted, False if not found
        """
        result = await self.db.execute(
            select(UserSettings).where(UserSettings.user_key == user_key)
        )
        settings = result.scalar_one_or_none()

        if not settings:
            return False

        await self.db.delete(settings)
        await self.db.commit()

        logger.info(f"Deleted settings for user: {user_key}")
        return True


# Convenience functions for use without explicit service instantiation
async def get_user_settings(
    db: AsyncSession, user_key: str = DEFAULT_USER_KEY
) -> Optional[UserSettingsSchema]:
    """Get settings for a user."""
    service = SettingsService(db)
    return await service.get_settings(user_key)


async def get_or_create_user_settings(
    db: AsyncSession, user_key: str = DEFAULT_USER_KEY
) -> UserSettingsSchema:
    """Get or create settings for a user."""
    service = SettingsService(db)
    return await service.get_or_create_settings(user_key)


async def update_user_settings(
    db: AsyncSession,
    settings_data: Dict[str, Any],
    user_key: str = DEFAULT_USER_KEY,
) -> UserSettingsSchema:
    """Update settings for a user."""
    service = SettingsService(db)
    return await service.update_settings(settings_data, user_key)


async def delete_user_settings(
    db: AsyncSession, user_key: str = DEFAULT_USER_KEY
) -> bool:
    """Delete settings for a user."""
    service = SettingsService(db)
    return await service.delete_settings(user_key)
