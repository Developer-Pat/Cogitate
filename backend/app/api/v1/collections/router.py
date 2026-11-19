"""
Collections API Router.

Provides REST endpoints for collection management, including
creating, updating, deleting collections and managing collection items.
"""

import logging
from typing import Optional, cast


from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.domain.collections.schemas import (
    CollectionCreate,
    CollectionUpdate,
    CollectionResponse,
    CollectionListResponse,
    CollectionItemCreate,
    CollectionItemResponse,
    CollectionContainsResponse,
)
from app.domain.agent_kits.schemas import AgentOwnersResponse
from app.domain.collections.service import CollectionService

logger = logging.getLogger(__name__)


def _announce(event: str, payload: dict) -> None:
    """THE CROSS-WINDOW COLLECTION SYNC (2026-08-25, the roadmap
    Phase 3): the kits' CRUD — the names feed the PackageTab + the
    pickers. The mutations publish collection:<id>:<event>; the
    frontend's sync applies them to every open tab."""
    try:
        from app.domain.messaging.services import publish
        publish(f"collection:{payload.get('collection_id')}:{event}", payload)
    except Exception as e:  # pragma: no cover
        logger.error(f"  ❌ collection:{event} publish failed: {e}")

router = APIRouter(prefix="/collections", tags=["collections"])


# =============================================================================
# Helper Functions
# =============================================================================


def _get_collection_service(db: AsyncSession) -> CollectionService:
    """Get collection service instance."""
    return CollectionService(db)


# =============================================================================
# Collection Endpoints
# =============================================================================


@router.post("", response_model=CollectionResponse, status_code=status.HTTP_201_CREATED)
async def create_collection(
    collection_data: CollectionCreate,
    db: AsyncSession = Depends(get_db_session),
) -> CollectionResponse:
    """
    Create a new collection.

    Collections are curated lists of entities (agents, tools, providers, macros, templates, workflow lists).
    Each collection is associated with a user and filtered by entity type.
    """
    service = _get_collection_service(db)
    try:
        collection = await service.create_collection(collection_data)
        _announce("created", {"collection_id": collection.id, "name": getattr(collection, "name", None), "event": "created"})
        return cast(CollectionResponse, collection)
    except Exception as e:
        logger.error(f"Failed to create collection: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create collection: {str(e)}"
        )


@router.get("", response_model=CollectionListResponse)
async def list_collections(
    entity_type: Optional[str] = Query(None, description="Filter by entity type (agent, tool, provider, macro_set, template, workflow_list)"),
    search: Optional[str] = Query(None, description="Search by name or description"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    limit: int = Query(100, ge=1, le=500, description="Maximum results per page"),
    offset: int = Query(0, ge=0, description="Result offset for pagination"),
    all: bool = Query(False, description="Return all collections without pagination limits"),
    db: AsyncSession = Depends(get_db_session),
) -> CollectionListResponse:
    """
    List all collections with filtering and pagination.

    By default, returns collections for the default user.
    Use entity_type to filter by specific entity types.
    Use `all=true` to return all collections without pagination limits.
    """
    # Override pagination if all=true
    if all:
        limit = 100000
        offset = 0
    service = _get_collection_service(db)
    user_key = "default"  # Until authentication is implemented

    collections, total = await service.list_collections(
        user_key=user_key,
        entity_type=entity_type,
        search=search,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )

    return CollectionListResponse(collections=cast(list[CollectionResponse], collections), total=total)


@router.get("/{collection_id}", response_model=CollectionResponse)
async def get_collection(
    collection_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> CollectionResponse:
    """
    Get a collection by ID.

    Returns the collection with all its items.
    """
    service = _get_collection_service(db)
    collection = await service.get_collection(collection_id)

    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection not found: {collection_id}"
        )

    return cast(CollectionResponse, collection)


@router.put("/{collection_id}", response_model=CollectionResponse)
async def update_collection(
    collection_id: str,
    collection_data: CollectionUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> CollectionResponse:
    """
    Update a collection.

    Can update name, description, color, icon, and active status.
    """
    service = _get_collection_service(db)
    collection = await service.update_collection(collection_id, collection_data)

    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection not found: {collection_id}"
        )

    _announce("updated", {"collection_id": collection_id, "name": getattr(collection, "name", None), "event": "updated"})
    return cast(CollectionResponse, collection)


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(
    collection_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """
    Delete a collection.

    This will also delete all items in the collection.
    """
    service = _get_collection_service(db)
    success = await service.delete_collection(collection_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection not found: {collection_id}"
        )
    _announce("deleted", {"collection_id": collection_id, "event": "deleted"})


# =============================================================================
# Collection Item Endpoints
# =============================================================================


@router.post("/{collection_id}/items", response_model=CollectionItemResponse, status_code=status.HTTP_201_CREATED)
async def add_item_to_collection(
    collection_id: str,
    item_data: CollectionItemCreate,
    db: AsyncSession = Depends(get_db_session),
) -> CollectionItemResponse:
    """
    Add an item to a collection.

    Items represent entities (agents, tools, providers, macros, templates)
    that have been added to the collection.
    """
    service = _get_collection_service(db)

    # Verify collection exists
    collection = await service.get_collection(collection_id)
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection not found: {collection_id}"
        )

    # Check if entity type matches collection's entity type
    if item_data.entity_type != collection.entity_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Entity type '{item_data.entity_type}' does not match collection's entity type '{collection.entity_type}'"
        )

    # Check if item already exists
    exists = await service.is_entity_in_collection(
        collection_id, item_data.entity_type, item_data.entity_id
    )
    if exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Entity '{item_data.entity_id}' is already in collection"
        )

    item = await service.add_item_to_collection(collection_id, item_data)

    if not item:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to add item to collection"
        )

    return cast(CollectionItemResponse, item)


@router.delete("/{collection_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_item_from_collection(
    collection_id: str,
    item_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """
    Remove an item from a collection.

    This removes the association between the entity and the collection.
    The entity itself is not deleted.
    """
    service = _get_collection_service(db)

    # Verify collection exists
    collection = await service.get_collection(collection_id)
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection not found: {collection_id}"
        )

    success = await service.remove_item_from_collection(collection_id, item_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item not found: {item_id}"
        )


@router.get("/contains/{entity_type}/{entity_id}", response_model=CollectionContainsResponse)
async def find_collections_containing_entity(
    entity_type: str,
    entity_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> CollectionContainsResponse:
    """
    Find all collections containing a specific entity.

    Useful for checking which collections an entity belongs to.
    """
    service = _get_collection_service(db)
    user_key = "default"  # Until authentication is implemented

    collections = await service.find_collections_containing_entity(
        user_key=user_key,
        entity_type=entity_type,
        entity_id=entity_id,
    )

    return CollectionContainsResponse(collections=cast(list[CollectionResponse], collections), total=len(collections))


@router.get("/{collection_id}/items", response_model=list[CollectionItemResponse])
async def get_collection_items(
    collection_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> list[CollectionItemResponse]:
    """
    Get all items in a collection.

    Returns the items in the order they were added (newest first).
    """
    service = _get_collection_service(db)

    # Verify collection exists
    collection = await service.get_collection(collection_id)
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection not found: {collection_id}"
        )

    items = await service.get_collection_items(collection_id)
    return cast(list[CollectionItemResponse], items)


@router.get("/{collection_id}/agent-owners", response_model=AgentOwnersResponse)
async def list_collection_agent_owners(
    collection_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> AgentOwnersResponse:
    """The agents that OWN this collection as a kit (the agent_kits
    join direction: who has the Search Kit?). Tool-typed collections
    only — a team or another collection type owns no agents."""
    from sqlalchemy import select

    from app.domain.agent_kits.service import AgentKitService
    from app.domain.collections.models import Collection
    from app.infrastructure.database.models import Agent

    collection = (
        await db.execute(select(Collection).where(Collection.id == collection_id))
    ).scalar_one_or_none()
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection not found: {collection_id}",
        )
    if collection.entity_type != "tool":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only tool-typed collections (kits) have agent owners",
        )
    agent_ids = await AgentKitService(db).agents_for_kit(collection_id)
    owners = []
    if agent_ids:
        rows = await db.execute(select(Agent.id, Agent.name).where(Agent.id.in_(agent_ids)))
        owners = [{"id": aid, "name": name} for aid, name in rows.all()]
    return AgentOwnersResponse(kit_id=collection_id, agents=owners)
