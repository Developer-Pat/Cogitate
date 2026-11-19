"""Cognitive Profile Service — CRUD operations for cognitive profiles.

Provides the business logic layer for managing named cognitive pipeline
configurations that bundle strategy selectors and reference a memory profile.

Built-in profiles (``is_builtin=True``) are seeded by migration and cannot
be modified or deleted. User-created profiles are fully editable.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.infrastructure.database.models import CognitiveProfile, MemoryProfile

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _profile_to_dict(profile: CognitiveProfile) -> Dict[str, Any]:
    """Convert an ORM cognitive profile to a dictionary."""
    config = None
    if profile.config_json:
        try:
            config = json.loads(profile.config_json)
        except (json.JSONDecodeError, TypeError):
            config = {"_raw": profile.config_json}

    memory_profile_name = None
    if profile.memory_profile:
        memory_profile_name = profile.memory_profile.name

    return {
        "id": profile.id,
        "name": profile.name,
        "description": profile.description,
        "context_builder": profile.context_builder,
        "executor": profile.executor,
        "response_formatter": profile.response_formatter,
        "memory_profile_id": profile.memory_profile_id,
        "memory_profile_name": memory_profile_name,
        "config": config,
        "is_builtin": profile.is_builtin,
        "created_at": profile.created_at.isoformat() if profile.created_at else None,
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def list_cognitive_profiles(
    db: AsyncSession,
    *,
    include_builtin: bool = True,
) -> List[Dict[str, Any]]:
    """List all cognitive profiles, optionally filtering out built-in ones."""
    stmt = (
        select(CognitiveProfile)
        .options(selectinload(CognitiveProfile.memory_profile))
        .order_by(CognitiveProfile.name)
    )
    result = await db.execute(stmt)
    profiles = result.scalars().all()

    if not include_builtin:
        profiles = [p for p in profiles if not p.is_builtin]

    return [_profile_to_dict(p) for p in profiles]


async def get_cognitive_profile(
    db: AsyncSession,
    profile_id: int,
) -> Optional[Dict[str, Any]]:
    """Get a single cognitive profile by ID."""
    stmt = (
        select(CognitiveProfile)
        .options(selectinload(CognitiveProfile.memory_profile))
        .where(CognitiveProfile.id == profile_id)
    )
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()
    return _profile_to_dict(profile) if profile else None


async def get_cognitive_profile_by_name(
    db: AsyncSession,
    name: str,
) -> Optional[Dict[str, Any]]:
    """Get a single cognitive profile by name."""
    stmt = (
        select(CognitiveProfile)
        .options(selectinload(CognitiveProfile.memory_profile))
        .where(CognitiveProfile.name == name)
    )
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()
    return _profile_to_dict(profile) if profile else None


async def create_cognitive_profile(
    db: AsyncSession,
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a new cognitive profile.

    Validates that the referenced memory_profile_id exists if provided.
    """
    memory_profile_id = data.get("memory_profile_id")
    if memory_profile_id is not None:
        mem_check_stmt = select(MemoryProfile).where(MemoryProfile.id == memory_profile_id)
        result = await db.execute(mem_check_stmt)
        if result.scalar_one_or_none() is None:
            raise ValueError(
                f"Memory profile with id={memory_profile_id} does not exist"
            )

    profile = CognitiveProfile(
        name=data["name"],
        description=data.get("description"),
        context_builder=data.get("context_builder", "default"),
        executor=data.get("executor", "default"),
        response_formatter=data.get("response_formatter", "default"),
        memory_profile_id=memory_profile_id,
        config_json=json.dumps(data["config"]) if data.get("config") else None,
        is_builtin=False,
    )
    db.add(profile)
    try:
        await db.flush()
    except Exception as e:
        await db.rollback()
        if "UNIQUE constraint" in str(e):
            raise ValueError(f"Cognitive profile with name '{data['name']}' already exists")
        raise
    await db.refresh(profile)
    # Eagerly load relationship for the response
    eager_stmt = (
        select(CognitiveProfile)
        .options(selectinload(CognitiveProfile.memory_profile))
        .where(CognitiveProfile.id == profile.id)
    )
    eager_result = await db.execute(eager_stmt)
    created_profile = eager_result.scalar_one()
    logger.info(
        "Created cognitive profile: id=%d name='%s'", created_profile.id, created_profile.name
    )
    return _profile_to_dict(created_profile)


async def update_cognitive_profile(
    db: AsyncSession,
    profile_id: int,
    data: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Update an existing cognitive profile. Built-in profiles cannot be updated."""
    stmt = (
        select(CognitiveProfile)
        .options(selectinload(CognitiveProfile.memory_profile))
        .where(CognitiveProfile.id == profile_id)
    )
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()

    if not profile:
        return None

    if profile.is_builtin:
        raise ValueError("Built-in cognitive profiles cannot be modified")

    # Validate memory_profile_id if being changed
    memory_profile_id = data.get("memory_profile_id")
    if memory_profile_id is not None:
        mp_stmt = select(MemoryProfile).where(MemoryProfile.id == memory_profile_id)
        mp_result = await db.execute(mp_stmt)
        if mp_result.scalar_one_or_none() is None:
            raise ValueError(
                f"Memory profile with id={memory_profile_id} does not exist"
            )

    if "name" in data:
        profile.name = data["name"]
    if "description" in data:
        profile.description = data.get("description")
    if "context_builder" in data:
        profile.context_builder = data["context_builder"]
    if "executor" in data:
        profile.executor = data["executor"]
    if "response_formatter" in data:
        profile.response_formatter = data["response_formatter"]
    if "memory_profile_id" in data:
        profile.memory_profile_id = data.get("memory_profile_id")
    if "config" in data:
        profile.config_json = json.dumps(data["config"]) if data["config"] else None

    await db.flush()
    await db.refresh(profile)
    logger.info(
        "Updated cognitive profile: id=%d name='%s'", profile.id, profile.name
    )
    return _profile_to_dict(profile)


async def delete_cognitive_profile(
    db: AsyncSession,
    profile_id: int,
) -> bool:
    """Delete a cognitive profile. Built-in profiles cannot be deleted."""
    stmt = select(CognitiveProfile).where(CognitiveProfile.id == profile_id)
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()

    if not profile:
        return False

    if profile.is_builtin:
        raise ValueError("Built-in cognitive profiles cannot be deleted")

    await db.delete(profile)
    await db.flush()
    logger.info(
        "Deleted cognitive profile: id=%d name='%s'", profile.id, profile.name
    )
    return True
