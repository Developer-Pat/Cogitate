"""
Preset Service — CRUD operations for cognitive configuration presets.

Provides the business logic layer for managing named presets that define
strategy overrides for the four pipeline components (context_builder,
executor, memory_manager, response_formatter) plus extended configuration.

Built-in presets (``is_builtin=True``) are seeded by migration and cannot
be modified or deleted. User-created presets are fully editable.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import CognitivePreset

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _preset_to_dict(preset: CognitivePreset) -> Dict[str, Any]:
    """Convert an ORM preset to a dictionary matching PresetResponse."""
    config = None
    if preset.config_json:
        try:
            config = json.loads(preset.config_json)
        except (json.JSONDecodeError, TypeError):
            config = {"_raw": preset.config_json}

    return {
        "id": preset.id,
        "name": preset.name,
        "description": preset.description,
        "context_builder": preset.context_builder,
        "executor": preset.executor,
        "memory_manager": preset.memory_manager,
        "response_formatter": preset.response_formatter,
        "config": config,
        "is_builtin": preset.is_builtin,
        "created_at": preset.created_at,
        "updated_at": preset.updated_at,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def list_presets(
    db: AsyncSession,
    *,
    include_builtin: bool = True,
) -> List[Dict[str, Any]]:
    """List all presets, optionally filtering out built-in ones.

    Args:
        db: Database session.
        include_builtin: If True (default), include built-in presets.

    Returns:
        List of preset dicts.
    """
    stmt = select(CognitivePreset).order_by(CognitivePreset.name)
    result = await db.execute(stmt)
    presets = result.scalars().all()

    if not include_builtin:
        presets = [p for p in presets if not p.is_builtin]

    return [_preset_to_dict(p) for p in presets]


async def get_preset(
    db: AsyncSession,
    preset_id: int,
) -> Optional[Dict[str, Any]]:
    """Get a single preset by ID.

    Args:
        db: Database session.
        preset_id: The preset ID.

    Returns:
        Preset dict, or None if not found.
    """
    preset = await db.get(CognitivePreset, preset_id)
    if preset is None:
        return None
    return _preset_to_dict(preset)


async def get_preset_by_name(
    db: AsyncSession,
    name: str,
) -> Optional[Dict[str, Any]]:
    """Get a single preset by name.

    Args:
        db: Database session.
        name: The preset name.

    Returns:
        Preset dict, or None if not found.
    """
    stmt = select(CognitivePreset).where(CognitivePreset.name == name)
    result = await db.execute(stmt)
    preset = result.scalar_one_or_none()
    if preset is None:
        return None
    return _preset_to_dict(preset)


async def create_preset(
    db: AsyncSession,
    name: str,
    *,
    description: Optional[str] = None,
    context_builder: str = "default",
    executor: str = "default",
    memory_manager: str = "default",
    response_formatter: str = "default",
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a new user preset.

    Args:
        db: Database session.
        name: Unique preset name.
        description: Optional description.
        context_builder: Context builder strategy name.
        executor: Executor strategy name.
        memory_manager: Memory manager strategy name.
        response_formatter: Response formatter strategy name.
        config: Extended configuration dict (JSON-serializable).

    Returns:
        The created preset dict.

    Raises:
        ValueError: If a preset with the same name already exists.
    """
    # Check for duplicate name
    existing = await get_preset_by_name(db, name)
    if existing is not None:
        raise ValueError(f"Preset '{name}' already exists")

    config_json = json.dumps(config) if config else None

    preset = CognitivePreset(
        name=name,
        description=description,
        context_builder=context_builder,
        executor=executor,
        memory_manager=memory_manager,
        response_formatter=response_formatter,
        config_json=config_json,
        is_builtin=False,
    )
    db.add(preset)
    await db.flush()
    await db.refresh(preset)

    logger.info("Created cognitive preset '%s' (id=%d)", name, preset.id)
    return _preset_to_dict(preset)


async def update_preset(
    db: AsyncSession,
    preset_id: int,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    context_builder: Optional[str] = None,
    executor: Optional[str] = None,
    memory_manager: Optional[str] = None,
    response_formatter: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Update an existing user preset.

    Only user-created presets (``is_builtin=False``) can be updated.
    Built-in presets are rejected.

    Args:
        db: Database session.
        preset_id: The preset ID to update.
        name: New name (optional).
        description: New description (optional).
        context_builder: New context builder strategy (optional).
        executor: New executor strategy (optional).
        memory_manager: New memory manager strategy (optional).
        response_formatter: New response formatter strategy (optional).
        config: New extended configuration (optional, replaces existing).

    Returns:
        Updated preset dict, or None if not found.

    Raises:
        ValueError: If the preset is built-in or the new name conflicts.
    """
    preset = await db.get(CognitivePreset, preset_id)
    if preset is None:
        return None

    if preset.is_builtin:
        raise ValueError(f"Cannot modify built-in preset '{preset.name}'")

    # Check name uniqueness if changing
    if name is not None and name != preset.name:
        existing = await get_preset_by_name(db, name)
        if existing is not None:
            raise ValueError(f"Preset '{name}' already exists")
        preset.name = name

    if description is not None:
        preset.description = description
    if context_builder is not None:
        preset.context_builder = context_builder
    if executor is not None:
        preset.executor = executor
    if memory_manager is not None:
        preset.memory_manager = memory_manager
    if response_formatter is not None:
        preset.response_formatter = response_formatter
    if config is not None:
        preset.config_json = json.dumps(config)

    await db.flush()
    await db.refresh(preset)

    logger.info("Updated cognitive preset '%s' (id=%d)", preset.name, preset.id)
    return _preset_to_dict(preset)


async def delete_preset(
    db: AsyncSession,
    preset_id: int,
) -> bool:
    """Delete a user preset by ID.

    Built-in presets cannot be deleted.

    Args:
        db: Database session.
        preset_id: The preset ID to delete.

    Returns:
        True if deleted, False if not found.

    Raises:
        ValueError: If the preset is built-in.
    """
    preset = await db.get(CognitivePreset, preset_id)
    if preset is None:
        return False

    if preset.is_builtin:
        raise ValueError(f"Cannot delete built-in preset '{preset.name}'")

    await db.delete(preset)
    await db.flush()

    logger.info("Deleted cognitive preset '%s' (id=%d)", preset.name, preset_id)
    return True


async def export_presets(
    db: AsyncSession,
    preset_ids: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Export presets as a JSON-serializable dict.

    Args:
        db: Database session.
        preset_ids: Optional list of preset IDs to export.
            If None, exports all presets.

    Returns:
        Export data dict with format_version and presets list.
    """
    if preset_ids:
        stmt = (
            select(CognitivePreset)
            .where(CognitivePreset.id.in_(preset_ids))
            .order_by(CognitivePreset.name)
        )
    else:
        stmt = select(CognitivePreset).order_by(CognitivePreset.name)

    result = await db.execute(stmt)
    presets = result.scalars().all()

    return {
        "format_version": "1",
        "presets": [_preset_to_dict(p) for p in presets],
    }


async def import_presets(
    db: AsyncSession,
    export_data: Dict[str, Any],
    *,
    overwrite: bool = False,
) -> List[Dict[str, Any]]:
    """Import presets from an export dict.

    Args:
        db: Database session.
        export_data: The export data dict (must have ``format_version``
            and ``presets`` keys).
        overwrite: If True, overwrite existing presets with matching names.
            If False (default), skip existing presets.

    Returns:
        List of imported/updated preset dicts.

    Raises:
        ValueError: If the export data format is invalid.
    """
    if not isinstance(export_data, dict):
        raise ValueError("Export data must be a dict")

    presets_data = export_data.get("presets", [])
    if not isinstance(presets_data, list):
        raise ValueError("Export data 'presets' must be a list")

    imported: List[Dict[str, Any]] = []

    for pd in presets_data:
        name = pd.get("name")
        if not name:
            logger.warning("Skipping preset with missing name in import data")
            continue

        existing = await get_preset_by_name(db, name)

        if existing is not None:
            if overwrite:
                result = await update_preset(
                    db,
                    existing["id"],
                    name=pd.get("name"),
                    description=pd.get("description"),
                    context_builder=pd.get("context_builder", "default"),
                    executor=pd.get("executor", "default"),
                    memory_manager=pd.get("memory_manager", "default"),
                    response_formatter=pd.get("response_formatter", "default"),
                    config=pd.get("config"),
                )
                if result:
                    imported.append(result)
            else:
                logger.info(
                    "Skipping existing preset '%s' (use overwrite=True to replace)",
                    name,
                )
        else:
            result = await create_preset(
                db,
                name=name,
                description=pd.get("description"),
                context_builder=pd.get("context_builder", "default"),
                executor=pd.get("executor", "default"),
                memory_manager=pd.get("memory_manager", "default"),
                response_formatter=pd.get("response_formatter", "default"),
                config=pd.get("config"),
            )
            imported.append(result)

    return imported
