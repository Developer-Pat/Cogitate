"""
Runtime configuration domain service.

Business logic for runtime configuration operations.
"""

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.domain.runtime_config.schemas import (
    RuntimeConfigCreate,
)
from app.infrastructure.database.models import RuntimeConfig

logger = logging.getLogger(__name__)


class RuntimeConfigService:
    """
    Service for runtime configuration business logic.

    Handles per-session configuration overrides.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize runtime config service.

        Args:
            db: Async database session
        """
        self.db = db

    async def get_by_session_id(
        self, session_id: int
    ) -> Optional[RuntimeConfig]:
        """
        Get runtime config by session ID.

        Args:
            session_id: Chat session ID

        Returns:
            RuntimeConfig if found, None otherwise
        """
        query = select(RuntimeConfig).where(RuntimeConfig.session_id == session_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_or_update(
        self, config_data: RuntimeConfigCreate
    ) -> RuntimeConfig:
        """
        Create a new runtime config or update existing one for session.

        Args:
            config_data: Runtime config creation data

        Returns:
            Created or updated runtime config
        """
        # Check if config already exists for this session
        existing = await self.get_by_session_id(config_data.session_id)

        if existing:
            # Update existing config
            update_data = config_data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(existing, field, value)

            await self.db.flush()
            await self.db.refresh(existing)

            logger.info(
                f"Updated runtime config for session {config_data.session_id}"
            )
            return existing
        else:
            # Create new config
            config = RuntimeConfig(**config_data.model_dump())
            self.db.add(config)
            await self.db.flush()
            await self.db.refresh(config)

            logger.info(
                f"Created runtime config for session {config_data.session_id}"
            )
            return config

    async def delete_by_session_id(self, session_id: int) -> bool:
        """
        Delete runtime config by session ID.

        Args:
            session_id: Chat session ID

        Returns:
            True if deleted, False if not found
        """
        config = await self.get_by_session_id(session_id)
        if not config:
            return False

        await self.db.delete(config)
        await self.db.flush()

        logger.info(f"Deleted runtime config for session {session_id}")
        return True

    # REMOVED (G-I, 2026-09-25): `get_effective_config(session_id, agent_id)` — a
    # dead method (no router, no service, no test called it) that merged agent
    # defaults with session overrides into a shape the system no longer has: its
    # payload carried `parameters.max_tokens` (the retired declaration slot) and its
    # own copy of the silent `2000` default. A merge of a shape nothing reads is not
    # a compatibility layer, it is a second place for the old numbers to live.

    async def reset_to_agent_defaults(
        self, session_id: int
    ) -> Optional[RuntimeConfig]:
        """
        Reset runtime config to agent defaults (clear all overrides).

        Args:
            session_id: Chat session ID

        Returns:
            Deleted config if it existed, None otherwise
        """
        config = await self.get_by_session_id(session_id)
        if config:
            await self.delete_by_session_id(session_id)
            return config
        return None
