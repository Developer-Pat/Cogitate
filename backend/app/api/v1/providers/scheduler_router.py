"""
Model sync scheduling API endpoints.

Provides scheduling operations for automatic model synchronization.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.domain.providers.scheduler import ModelSyncScheduler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/providers/sync-schedule", tags=["provider-sync"])


class SyncScheduleRequest(BaseModel):
    """Schema for setting sync schedule."""
    sync_interval_hours: int = Field(..., ge=1, description="Sync interval in hours")


class SyncScheduleResponse(BaseModel):
    """Schema for sync schedule response."""
    provider_id: int
    sync_interval_hours: int
    last_sync_at: Optional[str]
    next_sync_at: Optional[str]
    sync_enabled: bool
    last_sync_status: str


class SyncStatusResponse(BaseModel):
    """Schema for sync status response."""
    provider_id: int
    status: str
    message: str
    models_synced: int
    last_sync_at: Optional[str]
    next_sync_at: Optional[str]


@router.get("/{provider_id}", response_model=SyncScheduleResponse)
async def get_sync_schedule(
    provider_id: int,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get sync schedule for a provider.

    Args:
        provider_id: Provider ID
    """
    scheduler = ModelSyncScheduler()
    schedule = await scheduler.get_sync_schedule(db, provider_id)

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sync schedule for provider {provider_id} not found",
        )

    return schedule.to_dict()


@router.post("/{provider_id}", response_model=SyncScheduleResponse)
async def set_sync_schedule(
    provider_id: int,
    request: SyncScheduleRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Set sync schedule for a provider.

    Args:
        provider_id: Provider ID
        request: Sync schedule request with interval in hours
    """
    scheduler = ModelSyncScheduler()
    schedule = await scheduler.set_sync_schedule(db, provider_id, request.sync_interval_hours)

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found",
        )

    return schedule.to_dict()


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disable_sync_schedule(
    provider_id: int,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Disable automatic sync for a provider.

    Args:
        provider_id: Provider ID
    """
    scheduler = ModelSyncScheduler()
    success = await scheduler.disable_sync(db, provider_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sync schedule for provider {provider_id} not found",
        )


@router.post("/{provider_id}/run", response_model=SyncStatusResponse)
async def run_sync(
    provider_id: int,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Run model synchronization now.

    Args:
        provider_id: Provider ID
    """
    scheduler = ModelSyncScheduler()
    status_result = await scheduler.run_sync(db, provider_id)

    return status_result.to_dict()


@router.get("/status/{provider_id}", response_model=SyncStatusResponse)
async def get_sync_status(
    provider_id: int,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get current sync status for a provider.

    Args:
        provider_id: Provider ID
    """
    scheduler = ModelSyncScheduler()
    status_result = await scheduler.get_sync_status(db, provider_id)

    return status_result.to_dict()
