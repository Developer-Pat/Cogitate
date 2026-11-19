"""
Macros API Router.

Provides REST endpoints for macro sets and meta topics management
in the main database.
"""

import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.domain.macros.schemas import (
    MacroSetCreate,
    MacroSetUpdate,
    MacroSetResponse,
    MacroSetListResponse,
    MetaTopicCreate,
    MetaTopicUpdate,
    MetaTopicResponse,
    MetaTopicListResponse,
    MetaTopicLoadResponse,
    TopicListResponse,
)
from app.domain.macros.services import AgentMacroService, DEFAULT_USER_KEY
from app.api.v1.macros.backup_router import router as backup_router
from app.api.v1.macros.export_router import router as export_router

logger = logging.getLogger(__name__)


def _announce(topic: str, event: str, payload: dict) -> None:
    """THE CROSS-WINDOW MACRO SYNC (2026-08-25, the roadmap Phase 5):
    the macro sets + the meta-topics' CRUD publish macro:<id>:<event>
    / meta-topic:<id>:<event>; the frontend's sync reloads the
    shared macro store in every open tab."""
    try:
        from app.domain.messaging.services import publish
        publish(f"{topic}:{payload.get('id')}:{event}", payload)
    except Exception as e:  # pragma: no cover
        logger.error(f"  ❌ {topic}:{event} publish failed: {e}")

router = APIRouter(prefix="/macros", tags=["macros"])

# Include backup and export sub-routers
router.include_router(backup_router)
router.include_router(export_router)


# =============================================================================
# Helper Functions
# =============================================================================


def _get_macro_service(db: AsyncSession) -> AgentMacroService:
    """Get agent macro service instance (operates on ``cogitate.db``)."""
    return AgentMacroService(db)


# =============================================================================
# Macro Set Endpoints
# =============================================================================


@router.get("", response_model=MacroSetListResponse)
async def list_macro_sets(
    topic: Optional[str] = Query(None, description="Filter by topic"),
    user_key: Optional[str] = Query(None, description="User identifier"),
    all: bool = Query(False, description="Return all macro sets without pagination limits"),
    db: AsyncSession = Depends(get_db_session),
):
    """
    List macro sets (agent macros in ``cogitate.db``).

    Returns all macro sets for a user, optionally filtered by topic.

    **Parameters:**
    - `topic`: Optional topic filter (e.g., "Algebra", "Geometry")
    - `user_key`: User identifier (default: "default")

    **Returns:**
    - List of macro sets with metadata
    """
    key_to_use = user_key or DEFAULT_USER_KEY
    service = _get_macro_service(db)

    try:
        macro_sets = await service.list_macro_sets(key_to_use, topic, all_sets=all)

        return MacroSetListResponse(
            macro_sets=macro_sets,
            total=len(macro_sets),
        )
    except Exception as e:
        logger.error(f"Failed to list macro sets: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list macro sets: {str(e)}")


@router.get("/topics/list", response_model=TopicListResponse)
async def list_topics(
    user_key: Optional[str] = Query(None, description="User identifier"),
    db: AsyncSession = Depends(get_db_session),
):
    """
    List all unique topics (agent macros in ``cogitate.db``).

    Returns a list of all unique topic names that have macro sets.

    **Parameters:**
    - `user_key`: User identifier (default: "default")

    **Returns:**
    - List of unique topic names
    """
    key_to_use = user_key or DEFAULT_USER_KEY
    service = _get_macro_service(db)

    try:
        topics = await service.list_topics(key_to_use)

        return TopicListResponse(
            topics=topics,
            total=len(topics),
        )
    except Exception as e:
        logger.error(f"Failed to list topics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list topics: {str(e)}")


# =============================================================================
# Meta Topic Endpoints (MUST be before /{macro_set_id} routes)
# =============================================================================


@router.get("/meta-topics", response_model=MetaTopicListResponse)
async def list_meta_topics(
    user_key: Optional[str] = Query(None, description="User identifier"),
    all: bool = Query(False, description="Return all meta topics without pagination limits"),
    db: AsyncSession = Depends(get_db_session),
):
    """
    List all agent meta topics (with ``namespace='agent'``).

    Returns all agent meta topics.

    **Parameters:**
    - `user_key`: User identifier (default: "default") — kept for backward compatibility

    **Returns:**
    - List of agent meta topics
    """
    from app.infrastructure.database.models import MetaTopic
    from sqlalchemy import select

    try:
        stmt = (
            select(MetaTopic)
            .where(MetaTopic.is_active)
            .order_by(MetaTopic.name)
        )
        result = await db.execute(stmt)
        meta_topics = result.scalars().all()

        meta_topic_responses = []
        for mt in meta_topics:
            meta_topic_responses.append(MetaTopicResponse(
                id=mt.id,
                user_key=mt.user_key or "",
                name=mt.name,
                description=mt.description or "",
                topic_mappings=mt.topic_mappings or [],
                is_active=mt.is_active,
                created_at=mt.created_at,
                updated_at=mt.updated_at,
            ))

        return MetaTopicListResponse(
            meta_topics=meta_topic_responses,
            total=len(meta_topic_responses),
        )
    except Exception as e:
        logger.error(f"Failed to list meta topics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list meta topics: {str(e)}")


@router.get("/meta-topics/{meta_topic_id}", response_model=MetaTopicResponse)
async def get_meta_topic(
    meta_topic_id: int,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get an agent meta topic by ID (with ``namespace='agent'``).

    **Parameters:**
    - `meta_topic_id`: Meta topic ID

    **Returns:**
    - Meta topic details
    """
    from app.infrastructure.database.models import MetaTopic
    from sqlalchemy import select

    try:
            stmt = select(MetaTopic).where(
                MetaTopic.id == meta_topic_id,
            )
            result = await db.execute(stmt)
            meta_topic = result.scalar_one_or_none()

            if not meta_topic:
                raise HTTPException(status_code=404, detail=f"Meta topic {meta_topic_id} not found")

            return MetaTopicResponse(
                id=meta_topic.id,
                user_key="",
                namespace=meta_topic.namespace,
                name=meta_topic.name,
                description=meta_topic.description or "",
                topic_mappings=meta_topic.topic_mappings or [],
                is_active=meta_topic.is_active,
                created_at=meta_topic.created_at,
                updated_at=meta_topic.updated_at,
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get meta topic: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get meta topic: {str(e)}")


@router.post("/meta-topics", response_model=MetaTopicResponse, status_code=201)
async def create_meta_topic(
    meta_topic_data: MetaTopicCreate,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Create a new agent meta topic (with ``namespace='agent'``).

    **Request Body:**
    - `name`: Name of the meta topic
    - `description`: Optional description
    - `topic_mappings`: List of {topic, slot_start} mappings
    - `is_active`: Whether the meta topic is active (default: true)

    **Example:**
    ```json
    {
      "name": "Math Curriculum",
      "description": "All math topics combined",
      "topic_mappings": [
        {"topic": "Algebra", "slot_start": "F1"},
        {"topic": "Geometry", "slot_start": "F6"},
        {"topic": "Calculus", "slot_start": "F11"}
      ]
    }
    ```

    **Returns:**
    - Created meta topic
    """
    from app.infrastructure.database.models import MetaTopic
    from sqlalchemy.exc import IntegrityError

    try:
        # topic_mappings is a Text column — must be JSON-serialized
        # (the list form crashes SQLite binding; existing rows store
        # JSON strings). Fixed 2026-08-13.
        import json as _json
        meta_topic = MetaTopic(
            # user_key is NOT NULL — the request's user_key (or the
            # default) must be persisted. Missing it crashed with a
            # misleading 409 IntegrityError (fixed 2026-08-13).
            user_key=getattr(meta_topic_data, "user_key", None) or DEFAULT_USER_KEY,
            name=meta_topic_data.name,
            description=meta_topic_data.description,
            topic_mappings=_json.dumps([
                {"topic": tm.topic, "slot_start": tm.slot_start}
                for tm in (meta_topic_data.topic_mappings or [])
            ]),
            is_active=meta_topic_data.is_active if meta_topic_data.is_active is not None else True,
        )
        db.add(meta_topic)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=409,
                detail=f"Meta topic with name '{meta_topic_data.name}' already exists",
            )
        await db.refresh(meta_topic)
        _announce("meta-topic", "created", {"id": meta_topic.id, "name": getattr(meta_topic, "name", None), "event": "created"})
        logger.info(f"Created agent meta topic: {meta_topic.name} (id: {meta_topic.id})")

        return MetaTopicResponse(
            id=meta_topic.id,
            user_key=meta_topic.user_key or "",
            namespace=meta_topic.namespace,
            name=meta_topic.name,
            description=meta_topic.description or "",
            topic_mappings=meta_topic.topic_mappings or [],
            is_active=meta_topic.is_active,
            created_at=meta_topic.created_at,
            updated_at=meta_topic.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create meta topic: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create meta topic: {str(e)}")


@router.put("/meta-topics/{meta_topic_id}", response_model=MetaTopicResponse)
async def update_meta_topic(
    meta_topic_id: int,
    meta_topic_data: MetaTopicUpdate,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Update an agent meta topic (with ``namespace='agent'``).

    **Parameters:**
    - `meta_topic_id`: Meta topic ID

    **Request Body:**
    - Fields to update (all optional)

    **Returns:**
    - Updated meta topic
    """
    from app.infrastructure.database.models import MetaTopic
    from sqlalchemy import select

    try:
            stmt = select(MetaTopic).where(
                MetaTopic.id == meta_topic_id,
            )
            result = await db.execute(stmt)
            meta_topic = result.scalar_one_or_none()

            if not meta_topic:
                raise HTTPException(status_code=404, detail=f"Meta topic {meta_topic_id} not found")

            update_data = meta_topic_data.model_dump(exclude_unset=True)
            # Remove mode_slug from update data (not a column in MetaTopic)
            update_data.pop('mode_slug', None)

            # topic_mappings is a Text column — must be JSON-serialized
            # (the list form crashes SQLite binding, same fix as create)
            if "topic_mappings" in update_data:
                import json as _json
                update_data["topic_mappings"] = _json.dumps([
                    {"topic": tm.topic, "slot_start": tm.slot_start}
                    if hasattr(tm, "topic")
                    else tm
                    for tm in (update_data["topic_mappings"] or [])
                ])

            updatable_fields = ["name", "description", "topic_mappings", "is_active"]
            for field in updatable_fields:
                if field in update_data:
                    setattr(meta_topic, field, update_data[field])

            await db.commit()
            await db.refresh(meta_topic)
            _announce("meta-topic", "updated", {"id": meta_topic_id, "name": getattr(meta_topic, "name", None), "event": "updated"})
            logger.info(f"Updated agent meta topic: {meta_topic.name} (id: {meta_topic_id})")

            return MetaTopicResponse(
                id=meta_topic.id,
                user_key="",
                namespace=meta_topic.namespace,
                name=meta_topic.name,
                description=meta_topic.description or "",
                topic_mappings=meta_topic.topic_mappings or [],
                is_active=meta_topic.is_active,
                created_at=meta_topic.created_at,
                updated_at=meta_topic.updated_at,
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update meta topic: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update meta topic: {str(e)}")


@router.delete("/meta-topics/{meta_topic_id}")
async def delete_meta_topic(
    meta_topic_id: int,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Delete (deactivate) an agent meta topic (with ``namespace='agent'``).

    Sets ``is_active`` to False rather than hard-deleting, preserving
    referential integrity for any associated data.

    **Parameters:**
    - `meta_topic_id`: Meta topic ID

    **Returns:**
    - Success message
    """
    from app.infrastructure.database.models import MetaTopic
    from sqlalchemy import select

    try:
            stmt = select(MetaTopic).where(
                MetaTopic.id == meta_topic_id,
            )
            result = await db.execute(stmt)
            meta_topic = result.scalar_one_or_none()

            if not meta_topic:
                raise HTTPException(status_code=404, detail=f"Meta topic {meta_topic_id} not found")

            meta_topic.is_active = False
            await db.commit()
            logger.info(f"Deactivated agent meta topic: {meta_topic.name} (id: {meta_topic_id})")
            _announce("meta-topic", "deleted", {"id": meta_topic_id, "event": "deleted"})
            return {"message": f"Meta topic {meta_topic_id} deactivated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete meta topic: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete meta topic: {str(e)}")


@router.post("/meta-topics/{meta_topic_id}/load", response_model=MetaTopicLoadResponse)
async def load_meta_topic(
    meta_topic_id: int,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Load a meta topic and resolve all macros to extended slots (agent macros in ``cogitate.db``).

    This endpoint resolves the meta topic's topic mappings to actual macro
    definitions, creating an extended keyboard layout (F1-F20+).

    **Parameters:**
    - `meta_topic_id`: Meta topic ID

    **Returns:**
    - Extended macro mappings for keyboard display

    **Example Response:**
    ```json
    {
      "meta_topic_id": 1,
      "name": "Math Curriculum",
      "extended_macros": {
        "F1": "Solve for x: {{equation}}",
        "F2": "Factor: {{expression}}",
        ...
        "F6": "Area of circle: {{radius}}",
        ...
      },
      "slot_count": 15
    }
    ```
    """
    service = _get_macro_service(db)

    try:
        result = await service.load_meta_topic(meta_topic_id)
        logger.info(f"Loaded meta topic: {result.name} with {result.slot_count} macros")

        return result
    except ValueError as e:
        logger.warning(f"Meta topic not found: {meta_topic_id}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to load meta topic: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load meta topic: {str(e)}")


# =============================================================================
# Search Endpoint (MUST be before /{macro_set_id} routes)
# =============================================================================


@router.get("/search", response_model=MacroSetListResponse)
async def search_macro_sets(
    q: str = Query(..., min_length=1, max_length=200, description="Search query for macro sets (matches name, topic, description)"),
    user_key: Optional[str] = Query(None, description="User identifier"),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Search macro sets by name, topic, or description (case-insensitive, agent macros in ``cogitate.db``).

    Performs a case-insensitive search against macro set name, topic,
    and description fields. Returns matching results without pagination
    since macro sets are typically few in number.

    **Parameters:**
    - `q`: Search query string
    - `user_key`: User identifier (default: "default")

    **Returns:**
    - List of matching macro sets with metadata
    """
    key_to_use = user_key or DEFAULT_USER_KEY
    service = _get_macro_service(db)

    try:
        macro_sets = await service.search_macro_sets(query=q, user_key=key_to_use)

        return MacroSetListResponse(
            macro_sets=macro_sets,
            total=len(macro_sets),
        )
    except Exception as e:
        logger.error(f"Failed to search macro sets: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to search macro sets: {str(e)}")


# ─── Save / Load Meta-Topics (file system) ──────────────────────────────────


@router.post("/meta-topics/{meta_topic_id}/save")
async def save_meta_topic_to_file(
    meta_topic_id: int,
    db: AsyncSession = Depends(get_db_session),
):
    """Save a meta-topic and its macro sets to a JSON file on disk."""
    from app.infrastructure.database.models import MetaTopic
    from app.infrastructure.database.models import MacroSet
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    import json, os

    try:
        async with AsyncSessionLocal() as odb:
            result = await odb.execute(
                select(MetaTopic).where(MetaTopic.id == meta_topic_id)
            )
            meta_topic = result.scalar_one_or_none()
            if not meta_topic:
                raise HTTPException(status_code=404, detail="Meta-topic not found")

            _mappings = meta_topic.topic_mappings
            if isinstance(_mappings, str):
                try:
                    _mappings = json.loads(_mappings)
                except Exception:
                    _mappings = []
            topics = [m.get("topic") for m in (_mappings or []) if isinstance(m, dict)]

            # Query from macro_sets table (standard model)
            macro_sets: List[MacroSet] = []
            if topics:
                result = await odb.execute(
                    select(MacroSet).where(MacroSet.topic.in_(topics))
                )
                macro_sets = list(result.scalars(MacroSet).all())

        bundle = {
            "meta_topic": MetaTopicResponse.model_validate(meta_topic).model_dump(),
            "macro_sets": [MacroSetResponse.model_validate(ms).model_dump() for ms in macro_sets],
        }

        # THROUGH THE RESOLVER (2026-09-12). This was
        # `os.path.expanduser("~/Projects/cogitate/data/macro-saves")` — a
        # hardcoded HOME DIRECTORY in application code, so macro saves worked
        # only on a machine where the project happened to live at that exact
        # path. Any other install — another user, another directory, a
        # packaged fork — silently wrote somewhere else entirely.
        from app.core.config import Paths, get_settings

        saves_dir = str(Paths.from_settings(get_settings()).data_dir / "macro-saves")
        os.makedirs(saves_dir, exist_ok=True)
        safe_name = meta_topic.name.lower().replace(" ", "-").replace("/", "-")[:50]
        filepath = os.path.join(saves_dir, f"{safe_name}.json")
        with open(filepath, "w") as f:
            json.dump(bundle, f, indent=2, default=str)

        logger.info("Saved meta-topic '%s' to %s", meta_topic.name, filepath)
        return {"message": f"Saved to {os.path.basename(filepath)}", "file": filepath}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to save meta-topic: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to save: {str(e)}")

@router.get("/saves")
async def list_saved_meta_topics():
    """List previously saved meta-topic files."""
    import json, os

    from app.core.config import Paths, get_settings

    saves_dir = str(Paths.from_settings(get_settings()).data_dir / "macro-saves")
    saves = []
    if os.path.exists(saves_dir):
        for fname in sorted(os.listdir(saves_dir)):
            if fname.endswith(".json"):
                fpath = os.path.join(saves_dir, fname)
                try:
                    with open(fpath) as f:
                        bundle = json.load(f)
                    mt = bundle.get("meta_topic", {})
                    saves.append({
                        "folder": fname.replace(".json", ""),
                        "name": mt.get("name", fname),
                        "description": mt.get("description", ""),
                        "macro_count": len(bundle.get("macro_sets", [])),
                        "file": fname,
                        "saved_at": os.path.getmtime(fpath),
                    })
                except Exception:
                    saves.append({"folder": fname.replace(".json", ""), "name": fname, "error": True})

    return {"saves": saves}


@router.post("/meta-topics/load/{folder}")
async def load_meta_topic_from_file(
    folder: str,
    db: AsyncSession = Depends(get_db_session),
):
    """Load a saved meta-topic file and import it into the database."""
    from app.infrastructure.database.models import MacroSet, MetaTopic
    from sqlalchemy import select
    import json, os

    from app.core.config import Paths, get_settings

    saves_dir = str(Paths.from_settings(get_settings()).data_dir / "macro-saves")
    fpath = os.path.join(saves_dir, f"{folder}.json")

    if not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail=f"Save file not found: {folder}")

    try:
        with open(fpath) as f:
            bundle = json.load(f)

        mt_data = bundle.get("meta_topic", {})
        macro_sets_data = bundle.get("macro_sets", [])

        # Check if meta-topic already exists by name
        result = await db.execute(
            select(MetaTopic).where(MetaTopic.name == mt_data.get("name"))
        )
        existing = result.scalar_one_or_none()

        if existing:
            meta_topic_id = existing.id
            for key, val in mt_data.items():
                if hasattr(existing, key) and key not in ("id", "created_at", "updated_at"):
                    if key == "topic_mappings" and isinstance(val, list):
                        import json as _j2
                        val = _j2.dumps(val)
                    setattr(existing, key, val)
            await db.commit()
            await db.refresh(existing)
        else:
            mt_data.pop("id", None)
            mt_data.pop("created_at", None)
            import json as _json
            for _key in list(mt_data.keys()):
                if _key not in ("namespace", "name", "description", "topic_mappings", "is_active", "user_key"):
                    mt_data.pop(_key, None)
            if isinstance(mt_data.get("topic_mappings"), list):
                mt_data["topic_mappings"] = _json.dumps(mt_data["topic_mappings"])
            mt_data.setdefault("user_key", "default")
            meta_topic = MetaTopic(**mt_data)
            db.add(meta_topic)
            await db.commit()
            await db.refresh(meta_topic)
            meta_topic_id = meta_topic.id

        # Import macro sets
        for ms_data in macro_sets_data:
            ms_data.pop("id", None)
            ms_data.pop("created_at", None)
            ms_data.pop("updated_at", None)
            ms_data.pop("mode_slug", None)
            ms_data.pop("slug", None)
            ms_data["user_key"] = "default"
            # Skip if already exists (unique constraint on user_key, topic, name)
            from sqlalchemy import select as _sel
            _existing = await db.execute(
                _sel(MacroSet).where(
                    MacroSet.user_key == ms_data.get("user_key", "default"),
                    MacroSet.topic == ms_data.get("topic", ""),
                    MacroSet.name == ms_data.get("name", "")
                )
            )
            if not _existing.scalar_one_or_none():
                macro_set = MacroSet(**ms_data)
                db.add(macro_set)

        await db.commit()

        # Refresh frontend stores
        logger.info("Loaded meta-topic '%s' (id=%d) with %d macro sets",
                    mt_data.get("name", "?"), meta_topic_id, len(macro_sets_data))
        return {"meta_topic_id": meta_topic_id, "message": f"Loaded {mt_data.get('name', folder)}"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to load meta-topic: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to load: {str(e)}")




# =============================================================================
# Macro Set Endpoints (MUST be after /meta-topics and /search routes)
# =============================================================================


@router.get("/{macro_set_id}", response_model=MacroSetResponse)
async def get_macro_set(
    macro_set_id: int,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get a macro set by ID (agent macros in ``cogitate.db``).

    **Parameters:**
    - `macro_set_id`: Macro set ID

    **Returns:**
    - Macro set details
    """
    service = _get_macro_service(db)

    try:
        macro_set = await service.get_macro_set(macro_set_id)

        if not macro_set:
            raise HTTPException(status_code=404, detail=f"Macro set {macro_set_id} not found")

        return macro_set
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get macro set: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get macro set: {str(e)}")


@router.post("", response_model=MacroSetResponse, status_code=201)
async def create_macro_set(
    macro_set_data: MacroSetCreate,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Create a new macro set.

    **Request Body:**
    - `user_key`: User identifier (default: "default")
    - `topic`: Topic category (e.g., "Algebra")
    - `name`: Name of the macro set
    - `description`: Optional description
    - `f1_macro` through `f5_macro`: Macro definitions
    - `is_active`: Whether the macro set is active (default: true)
    - `sort_order`: Sort order for display (default: 0)

    **Returns:**
    - Created macro set
    """
    service = _get_macro_service(db)

    try:
        macro_set = await service.create_macro_set(macro_set_data)
        _announce("macro", "created", {"id": macro_set.id, "name": getattr(macro_set, "name", None), "event": "created"})
        logger.info(f"Created macro set: {macro_set.name} (topic: {macro_set.topic})")

        return macro_set
    except Exception as e:
        logger.error(f"Failed to create macro set: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create macro set: {str(e)}")


async def _repoint_meta_topic_mappings(
    db: AsyncSession, old_topic: str, new_topic: str
) -> int:
    """Repoint every meta-topic mapping that names ``old_topic`` at ``new_topic``.

    THE LINK IS A NAME. A meta-topic's ``topic_mappings`` hold the macro set's ``topic``
    string — there is no id column tying the two — and the UI resolves a slot with
    ``macroSets.find(m => m.topic === mapping.topic)``. So renaming a macro set's topic
    changes one side of the pair and leaves the other dangling: the slot resolves to
    nothing, and the macro set silently vanishes from that meta-topic. Renaming is a
    supported action, so the reference has to be carried across it.

    Returns the number of meta-topics whose mapping list changed.
    """
    from app.infrastructure.database.models import MetaTopic
    from sqlalchemy import select
    import json as _json

    changed_topics = 0
    result = await db.execute(select(MetaTopic))

    for meta_topic in result.scalars().all():
        try:
            mappings = _json.loads(meta_topic.topic_mappings or "[]")
        except (TypeError, ValueError):
            # A row that is not JSON is left exactly as it is — repairing it is not this
            # function's business, and guessing at its shape would lose whatever it holds.
            continue
        if not isinstance(mappings, list):
            continue

        touched = False
        for mapping in mappings:
            if isinstance(mapping, dict) and mapping.get("topic") == old_topic:
                mapping["topic"] = new_topic
                touched = True

        if touched:
            meta_topic.topic_mappings = _json.dumps(mappings)
            changed_topics += 1

    if changed_topics:
        # A SECOND COMMIT IS INTENTIONAL. The service has already committed the macro set
        # itself, so by here the session is clean and this commit carries only the
        # repointed mappings. Leaving it out would make the repair look applied while the
        # session discards it at close — the silent kind of failure this whole function
        # exists to prevent.
        await db.commit()
    return changed_topics


@router.put("/{macro_set_id}", response_model=MacroSetResponse)
async def update_macro_set(
    macro_set_id: int,
    macro_set_data: MacroSetUpdate,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Update a macro set (agent macros in ``cogitate.db``).

    **Parameters:**
    - `macro_set_id`: Macro set ID

    **Request Body:**
    - Fields to update (all optional)

    **Returns:**
    - Updated macro set
    """
    service = _get_macro_service(db)

    try:
        # The topic is the MAPPING KEY on the meta-topic side, so read it BEFORE the
        # update: a rename would otherwise orphan this set from every slot that names it.
        from app.infrastructure.database.models import MacroSet
        from sqlalchemy import select

        previous = await db.execute(
            select(MacroSet.topic).where(MacroSet.id == macro_set_id)
        )
        old_topic = previous.scalar_one_or_none()

        macro_set = await service.update_macro_set(macro_set_id, macro_set_data)

        if not macro_set:
            raise HTTPException(status_code=404, detail=f"Macro set {macro_set_id} not found")

        new_topic = getattr(macro_set, "topic", None)
        if old_topic and new_topic and old_topic != new_topic:
            repointed = await _repoint_meta_topic_mappings(db, old_topic, new_topic)
            logger.info(
                "Renamed macro set topic %r -> %r (id=%s); repointed %d meta-topic mapping list(s)",
                old_topic,
                new_topic,
                macro_set_id,
                repointed,
            )

        _announce("macro", "updated", {"id": macro_set.id, "name": getattr(macro_set, "name", None), "event": "updated"})
        logger.info(f"Updated macro set: {macro_set.name}")
        return macro_set
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update macro set: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update macro set: {str(e)}")


@router.delete("/{macro_set_id}")
async def delete_macro_set(
    macro_set_id: int,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Delete a macro set (agent macros in ``cogitate.db``).

    **Parameters:**
    - `macro_set_id`: Macro set ID

    **Returns:**
    - Success message
    """
    service = _get_macro_service(db)

    try:
        deleted = await service.delete_macro_set(macro_set_id)

        if not deleted:
            raise HTTPException(status_code=404, detail=f"Macro set {macro_set_id} not found")

        logger.info(f"Deleted macro set: {macro_set_id}")
        _announce("macro", "deleted", {"id": macro_set_id, "event": "deleted"})
        return {"message": f"Macro set {macro_set_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete macro set: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete macro set: {str(e)}")
