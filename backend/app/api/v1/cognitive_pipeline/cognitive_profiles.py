"""Cognitive Profiles API Router.

Provides REST endpoints for managing cognitive pipeline configurations
that bundle strategy selectors and reference a memory profile.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.services.cognitive_pipeline.cognitive_profile_service import (
    list_cognitive_profiles,
    get_cognitive_profile,
    create_cognitive_profile,
    update_cognitive_profile,
    delete_cognitive_profile,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cognitive-profiles", tags=["cognitive-pipeline"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CognitiveProfileResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    context_builder: str = "default"
    executor: str = "default"
    response_formatter: str = "default"
    memory_profile_id: Optional[int] = None
    memory_profile_name: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    is_builtin: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class CognitiveProfileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    context_builder: str = Field(default="default", max_length=50)
    executor: str = Field(default="default", max_length=50)
    response_formatter: str = Field(default="default", max_length=50)
    memory_profile_id: Optional[int] = None
    config: Optional[Dict[str, Any]] = None


class CognitiveProfileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    context_builder: Optional[str] = Field(default=None, max_length=50)
    executor: Optional[str] = Field(default=None, max_length=50)
    response_formatter: Optional[str] = Field(default=None, max_length=50)
    memory_profile_id: Optional[int] = None
    config: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=List[CognitiveProfileResponse])
async def list_profiles(
    include_builtin: bool = Query(default=True),
    db: AsyncSession = Depends(get_db_session),
):
    """List all cognitive profiles."""
    return await list_cognitive_profiles(db, include_builtin=include_builtin)


@router.get("/{profile_id}", response_model=CognitiveProfileResponse)
async def get_profile(
    profile_id: int,
    db: AsyncSession = Depends(get_db_session),
):
    """Get a cognitive profile by ID."""
    profile = await get_cognitive_profile(db, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Cognitive profile not found")
    return profile


@router.post("", response_model=CognitiveProfileResponse, status_code=201)
async def create_profile(
    data: CognitiveProfileCreate,
    db: AsyncSession = Depends(get_db_session),
):
    """Create a new cognitive profile."""
    try:
        return await create_cognitive_profile(db, data.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{profile_id}", response_model=CognitiveProfileResponse)
async def update_profile(
    profile_id: int,
    data: CognitiveProfileUpdate,
    db: AsyncSession = Depends(get_db_session),
):
    """Update a cognitive profile. Built-in profiles cannot be modified."""
    try:
        profile = await update_cognitive_profile(db, profile_id, data.model_dump(exclude_unset=True))
        if not profile:
            raise HTTPException(status_code=404, detail="Cognitive profile not found")
        return profile
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{profile_id}", status_code=204)
async def delete_profile(
    profile_id: int,
    db: AsyncSession = Depends(get_db_session),
):
    """Delete a cognitive profile. Built-in profiles cannot be deleted."""
    try:
        deleted = await delete_cognitive_profile(db, profile_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Cognitive profile not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
