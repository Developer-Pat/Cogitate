"""
Model synchronization scheduler service.

Business logic for automatic model discovery scheduling.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta, UTC

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.infrastructure.database.models import Provider, ProviderSyncSchedule
from app.domain.providers.discovery_service import provider_discovery_service
from app.domain.providers.provider_endpoints import resolve_endpoint
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class SyncSchedule:
    """Sync schedule data class."""

    def __init__(
        self,
        provider_id: int,
        sync_interval_hours: int = 168,
        last_sync_at: Optional[datetime] = None,
        next_sync_at: Optional[datetime] = None,
        sync_enabled: bool = True,
        last_sync_status: str = "pending",
    ):
        self.provider_id = provider_id
        self.sync_interval_hours = sync_interval_hours
        self.last_sync_at = last_sync_at
        self.next_sync_at = next_sync_at
        self.sync_enabled = sync_enabled
        self.last_sync_status = last_sync_status

    @classmethod
    def from_model(cls, schedule: ProviderSyncSchedule) -> "SyncSchedule":
        """Create SyncSchedule from database model."""
        return cls(
            provider_id=schedule.provider_id,
            sync_interval_hours=schedule.sync_interval_hours,
            last_sync_at=schedule.last_sync_at,
            next_sync_at=schedule.next_sync_at,
            sync_enabled=schedule.sync_enabled,
            last_sync_status=schedule.last_sync_status or "",
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "provider_id": self.provider_id,
            "sync_interval_hours": self.sync_interval_hours,
            "last_sync_at": self.last_sync_at.isoformat() if self.last_sync_at else None,
            "next_sync_at": self.next_sync_at.isoformat() if self.next_sync_at else None,
            "sync_enabled": self.sync_enabled,
            "last_sync_status": self.last_sync_status,
        }


class SyncStatus:
    """Sync status data class."""

    def __init__(
        self,
        provider_id: int,
        status: str,
        message: str,
        models_synced: int = 0,
        last_sync_at: Optional[datetime] = None,
        next_sync_at: Optional[datetime] = None,
    ):
        self.provider_id = provider_id
        self.status = status
        self.message = message
        self.models_synced = models_synced
        self.last_sync_at = last_sync_at
        self.next_sync_at = next_sync_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "provider_id": self.provider_id,
            "status": self.status,
            "message": self.message,
            "models_synced": self.models_synced,
            "last_sync_at": self.last_sync_at.isoformat() if self.last_sync_at else None,
            "next_sync_at": self.next_sync_at.isoformat() if self.next_sync_at else None,
        }


class ModelSyncScheduler:
    """
    Service for model synchronization scheduling.

    Handles automatic model discovery scheduling for providers.
    """

    def __init__(self):
        """Initialize model sync scheduler."""
        settings = get_settings()
        self.default_sync_interval_hours = settings.default_sync_interval_hours

    async def get_sync_schedule(
        self,
        db: AsyncSession,
        provider_id: int,
    ) -> Optional[SyncSchedule]:
        """
        Get sync schedule for a provider.

        Args:
            db: Database session
            provider_id: Provider ID

        Returns:
            SyncSchedule or None if not configured
        """
        query = select(ProviderSyncSchedule).where(
            ProviderSyncSchedule.provider_id == provider_id
        )
        result = await db.execute(query)
        schedule = result.scalar_one_or_none()

        if schedule:
            return SyncSchedule.from_model(schedule)
        return None

    async def set_sync_schedule(
        self,
        db: AsyncSession,
        provider_id: int,
        sync_interval_hours: int,
    ) -> Optional[SyncSchedule]:
        """
        Set sync schedule for a provider.

        Args:
            db: Database session
            provider_id: Provider ID
            sync_interval_hours: Sync interval in hours

        Returns:
            Updated SyncSchedule or None if provider not found
        """
        # Check if provider exists
        query = select(Provider).where(Provider.id == provider_id)
        result = await db.execute(query)
        provider = result.scalar_one_or_none()

        if not provider:
            return None

        # Get or create sync schedule
        schedule_query = select(ProviderSyncSchedule).where(
            ProviderSyncSchedule.provider_id == provider_id
        )
        schedule_result = await db.execute(schedule_query)
        schedule = schedule_result.scalar_one_or_none()

        now = datetime.now(UTC)
        next_sync = now + timedelta(hours=sync_interval_hours)

        if schedule:
            # Update existing schedule
            schedule.sync_interval_hours = sync_interval_hours
            schedule.next_sync_at = next_sync
            schedule.sync_enabled = True
        else:
            # Create new schedule
            schedule = ProviderSyncSchedule(
                provider_id=provider_id,
                sync_interval_hours=sync_interval_hours,
                next_sync_at=next_sync,
                sync_enabled=True,
                last_sync_status="pending",
            )
            db.add(schedule)

        await db.flush()
        await db.refresh(schedule)

        logger.info(
            f"✅ Set sync schedule for provider {provider.name}: "
            f"every {sync_interval_hours}h, next sync at {next_sync}"
        )

        return SyncSchedule.from_model(schedule)

    async def disable_sync(
        self,
        db: AsyncSession,
        provider_id: int,
    ) -> bool:
        """
        Disable automatic sync for a provider.

        Args:
            db: Database session
            provider_id: Provider ID

        Returns:
            True if disabled, False if not found
        """
        query = select(ProviderSyncSchedule).where(
            ProviderSyncSchedule.provider_id == provider_id
        )
        result = await db.execute(query)
        schedule = result.scalar_one_or_none()

        if not schedule:
            return False

        schedule.sync_enabled = False
        await db.flush()

        logger.info(f"✅ Disabled sync for provider ID {provider_id}")

        return True

    async def run_sync(
        self,
        db: AsyncSession,
        provider_id: int,
        force_refresh: bool = True,
    ) -> SyncStatus:
        """
        Run model synchronization for a provider.

        Args:
            db: Database session
            provider_id: Provider ID
            force_refresh: Force refresh from provider API

        Returns:
            SyncStatus with sync results
        """
        # Check if provider exists
        query = select(Provider).where(Provider.id == provider_id)
        query_result = await db.execute(query)
        provider = query_result.scalar_one_or_none()

        if not provider:
            return SyncStatus(
                provider_id=provider_id,
                status="error",
                message=f"Provider {provider_id} not found",
            )

        try:
            # API key: .env stofirst (decision 2026-08-04); the DB column was removed
            from app.domain.providers.env_key_store import env_key_store
            api_key = env_key_store.get_key(provider.provider_type)
            if not api_key:
                # last resort: cached settings
                settings = get_settings()
                api_key = getattr(
                    settings, f"{provider.provider_type}_api_key", ""
                ) or None

            # Run discovery based on provider type
            models_synced = 0
            if provider.provider_type == "openrouter":
                if not api_key:
                    return SyncStatus(
                        provider_id=provider_id,
                        status="error",
                        message="OpenRouter API key not configured",
                    )
                result = await provider_discovery_service.discover_openrouter_models(
                    db, provider_id, api_key, force_refresh
                )
                models_synced = result.get("total", 0)

            elif provider.provider_type == "deepseek":
                if not api_key:
                    return SyncStatus(
                        provider_id=provider_id,
                        status="error",
                        message="Deepseek API key not configured",
                    )
                result = await provider_discovery_service.discover_deepseek_models(
                    db, provider_id, api_key, force_refresh
                )
                models_synced = result.get("total", 0)

            elif provider.provider_type == "ollama":
                endpoint = resolve_endpoint(
                    provider.provider_type, provider.base_url, provider.name
                )
                if endpoint is None:
                    return SyncStatus(
                        provider_id=provider_id,
                        status="skipped",
                        message=(
                            f"the '{provider.name}' row declares no endpoint, and the "
                            f"'{provider.provider_type}' type has none"
                        ),
                    )
                result = await provider_discovery_service.discover_ollama_models(
                    db, provider_id, endpoint, force_refresh
                )
                models_synced = result.get("total", 0)

            else:
                return SyncStatus(
                    provider_id=provider_id,
                    status="skipped",
                    message=f"Model discovery not implemented for {provider.provider_type}",
                )

            # Update sync schedule
            now = datetime.now(UTC)
            schedule_query = select(ProviderSyncSchedule).where(
                ProviderSyncSchedule.provider_id == provider_id
            )
            schedule_result = await db.execute(schedule_query)
            schedule = schedule_result.scalar_one_or_none()

            if schedule:
                schedule.last_sync_at = now
                schedule.last_sync_status = "success"
                if schedule.sync_enabled:
                    schedule.next_sync_at = now + timedelta(hours=schedule.sync_interval_hours)
            else:
                # Create schedule if it doesn't exist
                schedule = ProviderSyncSchedule(
                    provider_id=provider_id,
                    sync_interval_hours=self.default_sync_interval_hours,
                    last_sync_at=now,
                    last_sync_status="success",
                    next_sync_at=now + timedelta(hours=self.default_sync_interval_hours),
                )
                db.add(schedule)

            await db.flush()

            logger.info(
                f"✅ Synced {models_synced} models for provider {provider.name} (ID: {provider_id})"
            )

            return SyncStatus(
                provider_id=provider_id,
                status="success",
                message=f"Successfully synced {models_synced} models",
                models_synced=models_synced,
                last_sync_at=now,
                next_sync_at=schedule.next_sync_at if schedule else None,
            )

        except Exception as e:
            logger.error(f"❌ Sync failed for provider {provider_id}: {e}")

            # Update sync status to failed
            schedule_query = select(ProviderSyncSchedule).where(
                ProviderSyncSchedule.provider_id == provider_id
            )
            schedule_result = await db.execute(schedule_query)
            schedule = schedule_result.scalar_one_or_none()

            if schedule:
                schedule.last_sync_status = "failed"

            return SyncStatus(
                provider_id=provider_id,
                status="error",
                message=str(e),
            )

    async def get_sync_status(
        self,
        db: AsyncSession,
        provider_id: int,
    ) -> SyncStatus:
        """
        Get current sync status for a provider.

        Args:
            db: Database session
            provider_id: Provider ID

        Returns:
            SyncStatus object
        """
        # Check if provider exists
        query = select(Provider).where(Provider.id == provider_id)
        result = await db.execute(query)
        provider = result.scalar_one_or_none()

        if not provider:
            return SyncStatus(
                provider_id=provider_id,
                status="error",
                message=f"Provider {provider_id} not found",
            )

        # Get sync schedule
        schedule_query = select(ProviderSyncSchedule).where(
            ProviderSyncSchedule.provider_id == provider_id
        )
        schedule_result = await db.execute(schedule_query)
        schedule = schedule_result.scalar_one_or_none()

        if not schedule:
            return SyncStatus(
                provider_id=provider_id,
                status="not_configured",
                message="Sync schedule not configured",
            )

        # Determine current status
        now = datetime.now(UTC)
        if schedule.sync_enabled and schedule.next_sync_at and schedule.next_sync_at < now:
            status = "pending"
            message = "Sync is due"
        elif not schedule.sync_enabled:
            status = "disabled"
            message = "Sync is disabled"
        elif schedule.last_sync_status == "failed":
            status = "error"
            message = "Last sync failed"
        else:
            status = "ok"
            message = "Sync is up to date"

        return SyncStatus(
            provider_id=provider_id,
            status=status,
            message=message,
            last_sync_at=schedule.last_sync_at,
            next_sync_at=schedule.next_sync_at,
        )

    async def get_due_syncs(
        self,
        db: AsyncSession,
    ) -> list[int]:
        """
        Get list of provider IDs that are due for sync.

        Args:
            db: Database session

        Returns:
            List of provider IDs due for sync
        """
        now = datetime.now(UTC)

        query = select(ProviderSyncSchedule).where(
            ProviderSyncSchedule.sync_enabled,
            ProviderSyncSchedule.next_sync_at <= now,
        )

        result = await db.execute(query)
        schedules = result.scalars().all()

        return [s.provider_id for s in schedules]


async def sync_due_providers() -> None:
    """Refresh the catalogs whose schedule is DUE — the ones a user enabled.

    Registered as a maintenance job at boot and **inert until then**: a schedule row exists only
    because someone set an interval in that provider's panel, so on a fresh install nothing is ever
    due and no provider is ever contacted. The app ships with no provider sync of its own; the timer
    is opt-in, one provider at a time.

    Nothing else refreshes this catalog, and it is a TTL cache: rows past `expires_at` are served as
    they are, and their prices are what the usage page and a traced call's cost are computed from.
    A schedule the user enabled is the only thing that moves those prices.
    """
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        due = await ModelSyncScheduler().get_due_syncs(db)
        if not due:
            return

        logger.info("🔄 Provider catalog sync due for %d provider(s): %s", len(due), due)
        for provider_id in due:
            # ONE PROVIDER'S FAILURE IS NOT THE NEXT ONE'S. This job has no caller to raise to and no
            # user waiting on it: a provider that is down must not cost every other provider its
            # refresh, and the next tick is an hour away.
            try:
                status = await ModelSyncScheduler().run_sync(db, provider_id)
                logger.info("✅ Provider %d catalog synced: %s", provider_id, status)
            except Exception as exc:  # noqa: BLE001 - the job's contract is to keep going
                logger.warning("⚠️ Provider %d catalog sync failed: %s", provider_id, exc)
