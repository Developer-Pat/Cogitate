"""Memory Profiles API Router.

Provides REST endpoints for managing memory profile configurations
(strategy, window size, persistence, compaction, summarization).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.services.cognitive_pipeline.memory_profile_service import (
    list_memory_profiles,
    get_memory_profile,
    create_memory_profile,
    update_memory_profile,
    delete_memory_profile,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory-profiles", tags=["cognitive-pipeline"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class MemoryProfileResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    strategy: str = "default"
    window_size: int = 50
    persistence: str = "memory"
    compaction_threshold: Optional[int] = None
    summarization: bool = False
    config: Optional[Dict[str, Any]] = None
    is_builtin: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class MemoryProfileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    strategy: str = Field(default="default", max_length=50)
    window_size: int = Field(default=50, ge=0)
    persistence: str = Field(default="memory", max_length=20)
    compaction_threshold: Optional[int] = Field(default=None, ge=0)
    summarization: bool = False
    config: Optional[Dict[str, Any]] = None


class MemoryProfileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    strategy: Optional[str] = Field(default=None, max_length=50)
    window_size: Optional[int] = Field(default=None, ge=0)
    persistence: Optional[str] = Field(default=None, max_length=20)
    compaction_threshold: Optional[int] = Field(default=None, ge=0)
    summarization: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=List[MemoryProfileResponse])
async def list_profiles(
    include_builtin: bool = Query(default=True),
    db: AsyncSession = Depends(get_db_session),
):
    """List all memory profiles."""
    return await list_memory_profiles(db, include_builtin=include_builtin)


@router.get("/{profile_id}", response_model=MemoryProfileResponse)
async def get_profile(
    profile_id: int,
    db: AsyncSession = Depends(get_db_session),
):
    """Get a memory profile by ID."""
    profile = await get_memory_profile(db, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Memory profile not found")
    return profile


@router.post("", response_model=MemoryProfileResponse, status_code=201)
async def create_profile(
    data: MemoryProfileCreate,
    db: AsyncSession = Depends(get_db_session),
):
    """Create a new memory profile."""
    try:
        return await create_memory_profile(db, data.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{profile_id}", response_model=MemoryProfileResponse)
async def update_profile(
    profile_id: int,
    data: MemoryProfileUpdate,
    db: AsyncSession = Depends(get_db_session),
):
    """Update a memory profile. Built-in profiles cannot be modified."""
    try:
        profile = await update_memory_profile(db, profile_id, data.model_dump(exclude_unset=True))
        if not profile:
            raise HTTPException(status_code=404, detail="Memory profile not found")
        return profile
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{profile_id}", status_code=204)
async def delete_profile(
    profile_id: int,
    db: AsyncSession = Depends(get_db_session),
):
    """Delete a memory profile. Built-in profiles cannot be deleted."""
    try:
        deleted = await delete_memory_profile(db, profile_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Memory profile not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
