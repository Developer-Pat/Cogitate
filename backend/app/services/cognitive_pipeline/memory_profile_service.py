"""Memory Profile Service — CRUD operations for memory profiles.

Provides the business logic layer for managing named memory configurations
(strategy, window size, persistence backend, compaction, summarization).

Built-in profiles (``is_builtin=True``) are seeded by migration and cannot
be modified or deleted. User-created profiles are fully editable.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import MemoryProfile

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _profile_to_dict(profile: MemoryProfile) -> Dict[str, Any]:
    """Convert an ORM memory profile to a dictionary."""
    config = None
    if profile.config_json:
        try:
            config = json.loads(profile.config_json)
        except (json.JSONDecodeError, TypeError):
            config = {"_raw": profile.config_json}

    return {
        "id": profile.id,
        "name": profile.name,
        "description": profile.description,
        "strategy": profile.strategy,
        "window_size": profile.window_size,
        "persistence": profile.persistence,
        "compaction_threshold": profile.compaction_threshold,
        "summarization": profile.summarization,
        "config": config,
        "is_builtin": profile.is_builtin,
        "created_at": profile.created_at.isoformat() if profile.created_at else None,
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def list_memory_profiles(
    db: AsyncSession,
    *,
    include_builtin: bool = True,
) -> List[Dict[str, Any]]:
    """List all memory profiles, optionally filtering out built-in ones."""
    stmt = select(MemoryProfile).order_by(MemoryProfile.name)
    result = await db.execute(stmt)
    profiles = result.scalars().all()

    if not include_builtin:
        profiles = [p for p in profiles if not p.is_builtin]

    return [_profile_to_dict(p) for p in profiles]


async def get_memory_profile(
    db: AsyncSession,
    profile_id: int,
) -> Optional[Dict[str, Any]]:
    """Get a single memory profile by ID."""
    stmt = select(MemoryProfile).where(MemoryProfile.id == profile_id)
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()
    return _profile_to_dict(profile) if profile else None


async def get_memory_profile_by_name(
    db: AsyncSession,
    name: str,
) -> Optional[Dict[str, Any]]:
    """Get a single memory profile by name."""
    stmt = select(MemoryProfile).where(MemoryProfile.name == name)
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()
    return _profile_to_dict(profile) if profile else None


async def create_memory_profile(
    db: AsyncSession,
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a new memory profile."""
    profile = MemoryProfile(
        name=data["name"],
        description=data.get("description"),
        strategy=data.get("strategy", "default"),
        window_size=data.get("window_size", 50),
        persistence=data.get("persistence", "memory"),
        compaction_threshold=data.get("compaction_threshold"),
        summarization=data.get("summarization", False),
        config_json=json.dumps(data["config"]) if data.get("config") else None,
        is_builtin=False,
    )
    db.add(profile)
    try:
        await db.flush()
    except Exception as e:
        await db.rollback()
        if "UNIQUE constraint" in str(e):
            raise ValueError(f"Memory profile with name '{data['name']}' already exists")
        raise
    await db.refresh(profile)
    logger.info("Created memory profile: id=%d name='%s'", profile.id, profile.name)
    return _profile_to_dict(profile)


async def update_memory_profile(
    db: AsyncSession,
    profile_id: int,
    data: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Update an existing memory profile. Built-in profiles cannot be updated."""
    stmt = select(MemoryProfile).where(MemoryProfile.id == profile_id)
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()

    if not profile:
        return None

    if profile.is_builtin:
        raise ValueError("Built-in memory profiles cannot be modified")

    if "name" in data:
        profile.name = data["name"]
    if "description" in data:
        profile.description = data.get("description")
    if "strategy" in data:
        profile.strategy = data["strategy"]
    if "window_size" in data:
        profile.window_size = data["window_size"]
    if "persistence" in data:
        profile.persistence = data["persistence"]
    if "compaction_threshold" in data:
        profile.compaction_threshold = data.get("compaction_threshold")
    if "summarization" in data:
        profile.summarization = data["summarization"]
    if "config" in data:
        profile.config_json = json.dumps(data["config"]) if data["config"] else None

    await db.flush()
    await db.refresh(profile)
    logger.info("Updated memory profile: id=%d name='%s'", profile.id, profile.name)
    return _profile_to_dict(profile)


async def delete_memory_profile(
    db: AsyncSession,
    profile_id: int,
) -> bool:
    """Delete a memory profile. Built-in profiles cannot be deleted."""
    stmt = select(MemoryProfile).where(MemoryProfile.id == profile_id)
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()

    if not profile:
        return False

    if profile.is_builtin:
        raise ValueError("Built-in memory profiles cannot be deleted")

    await db.delete(profile)
    await db.flush()
    logger.info("Deleted memory profile: id=%d name='%s'", profile.id, profile.name)
    return True
