"""
Tool Permissions API Router.

Provides REST endpoints for tool-collection permission management.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.domain.tools.tool_permission_schemas import (
    PermissionLevel,
    ToolPermissionsResponse,
    ToolPermissionsUpdateRequest,
    PermissionCheckResponse,
    AccessibleToolsResponse,
    ToolCollectionPermissionResponse,
    ToolCollectionPermissionUpdate,
)
from app.domain.tools.tool_permission_service import ToolPermissionService

logger = logging.getLogger(__name__)


def _announce(event: str, payload: dict) -> None:
    """THE CROSS-WINDOW SYNC (2026-08-25, the roadmap Phase 6):
    tool-permission:<id>:<event> — the frontend's sync reloads the open pages."""
    try:
        from app.domain.messaging.services import publish
        publish(f"tool-permission:{payload.get('permission_id')}:{event}", payload)
    except Exception as e:  # pragma: no cover
        logger.error(f"  ❌ tool-permission:{event} publish failed: {e}")


router = APIRouter(prefix="/tools", tags=["tool-permissions"])


# =============================================================================
# Helper Functions
# =============================================================================


def _get_permission_service(db: AsyncSession) -> ToolPermissionService:
    """Get tool permission service instance."""
    return ToolPermissionService(db)


# =============================================================================
# Tool Permissions Endpoints
# =============================================================================


@router.get(
    "/{tool_id}/permissions",
    response_model=ToolPermissionsResponse,
    summary="Get tool permissions",
)
async def get_tool_permissions(
    tool_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> ToolPermissionsResponse:
    """
    Get all permissions for a specific tool.

    Returns the default access level and all collection-specific permissions.
    """
    service = _get_permission_service(db)
    permissions = await service.get_tool_permissions(tool_id)
    
    if not permissions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool not found: {tool_id}"
        )
    
    return permissions


@router.put(
    "/{tool_id}/permissions",
    response_model=ToolPermissionsResponse,
    summary="Update tool permissions",
)
async def update_tool_permissions(
    tool_id: str,
    update_data: ToolPermissionsUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
) -> ToolPermissionsResponse:
    """
    Update permissions for a specific tool.

    This endpoint allows updating the default access level and collection-specific
    permissions in a single request.
    """
    service = _get_permission_service(db)
    
    try:
        # Update permissions
        await service.update_tool_permissions(tool_id, update_data)
        
        # Fetch updated permissions
        permissions = await service.get_tool_permissions(tool_id)
        
        if not permissions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tool not found: {tool_id}"
            )
        
        return permissions
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post(
    "/{tool_id}/permissions/collections/{collection_id}",
    response_model=ToolCollectionPermissionResponse,
    summary="Set collection permission",
    status_code=status.HTTP_201_CREATED,
)
async def set_collection_permission(
    tool_id: str,
    collection_id: str,
    permission_level: str = Query(..., description="Permission level (read, execute, write, admin, deny)"),
    db: AsyncSession = Depends(get_db_session),
) -> ToolCollectionPermissionResponse:
    """
    Set permission for a specific collection to access a tool.

    Creates or updates the permission entry for the given collection.
    """
    service = _get_permission_service(db)
    
    # Validate permission level
    if not PermissionLevel.is_valid(permission_level):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid permission level: {permission_level}. "
                   f"Must be one of: {', '.join(PermissionLevel.VALID_LEVELS)}"
        )
    
    try:
        permission = await service.set_collection_permission(
            tool_id, collection_id, permission_level
        )
        
        # Build response with collection info
        from app.domain.collections.models import Collection
        from sqlalchemy import select
        
        coll_result = await db.execute(
            select(Collection).where(Collection.id == collection_id)
        )
        collection = coll_result.scalar_one_or_none()
        
        collection_summary = None
        if collection:
            from app.domain.tools.tool_permission_schemas import CollectionSummary
            collection_summary = CollectionSummary(
                id=collection.id,
                name=collection.name,
                entity_type=collection.entity_type,
                icon=collection.icon,
                color=collection.color,
            )
        
        _announce("created", {"permission_id": permission.id, "tool_id": permission.tool_id, "collection_id": permission.collection_id, "permission_level": permission.permission_level, "event": "created"})
        return ToolCollectionPermissionResponse(
            id=permission.id,
            tool_id=permission.tool_id,
            collection_id=permission.collection_id,
            permission_level=permission.permission_level,
            collection=collection_summary,
            created_at=permission.created_at,
            updated_at=permission.updated_at,
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete(
    "/{tool_id}/permissions/collections/{collection_id}",
    summary="Remove collection permission",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_collection_permission(
    tool_id: str,
    collection_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """
    Remove permission for a specific collection.

    This revokes the collection's access to the tool.
    """
    service = _get_permission_service(db)
    success = await service.remove_collection_permission(tool_id, collection_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Permission not found for tool {tool_id}, collection {collection_id}"
        )
    _announce("deleted", {"permission_id": None, "tool_id": tool_id, "collection_id": collection_id, "event": "deleted"})


# =============================================================================
# Permission Check Endpoints
# =============================================================================


@router.get(
    "/{tool_id}/check",
    response_model=PermissionCheckResponse,
    summary="Check user permission",
)
async def check_user_permission(
    tool_id: str,
    user_id: str = Query("default", description="User ID to check"),
    permission: str = Query("read", description="Required permission level"),
    db: AsyncSession = Depends(get_db_session),
) -> PermissionCheckResponse:
    """
    Check if a user has permission to access a tool.

    Returns whether the user has the required permission level and details
    about their current access level.
    """
    service = _get_permission_service(db)
    
    # Validate required permission
    if not PermissionLevel.is_valid(permission):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid permission level: {permission}"
        )
    
    return await service.check_permission(tool_id, user_id, permission)


@router.get(
    "/accessible",
    response_model=AccessibleToolsResponse,
    summary="List accessible tools",
)
async def list_accessible_tools(
    user_id: str = Query("default", description="User ID to list tools for"),
    permission: str = Query("read", description="Minimum required permission level"),
    limit: int = Query(100, ge=1, le=500, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Result offset"),
    db: AsyncSession = Depends(get_db_session),
) -> AccessibleToolsResponse:
    """
    List all tools accessible to a user.

    Returns tools that the user has permission to access based on their
    collection memberships.
    """
    service = _get_permission_service(db)
    
    # Validate permission level
    if not PermissionLevel.is_valid(permission):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid permission level: {permission}"
        )
    
    return await service.get_accessible_tools(user_id, permission, limit, offset)


# =============================================================================
# Individual Permission Management
# =============================================================================


@router.get(
    "/{tool_id}/permissions/{permission_id}",
    response_model=ToolCollectionPermissionResponse,
    summary="Get specific permission",
)
async def get_permission(
    tool_id: str,
    permission_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> ToolCollectionPermissionResponse:
    """
    Get details of a specific permission entry.
    """
    from app.domain.tools.tool_permission_models import ToolCollectionPermission
    from sqlalchemy import select
    
    result = await db.execute(
        select(ToolCollectionPermission).where(
            ToolCollectionPermission.id == permission_id,
            ToolCollectionPermission.tool_id == tool_id,
        )
    )
    permission = result.scalar_one_or_none()
    
    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Permission not found: {permission_id}"
        )
    
    # Get collection info
    from app.domain.collections.models import Collection
    coll_result = await db.execute(
        select(Collection).where(Collection.id == permission.collection_id)
    )
    collection = coll_result.scalar_one_or_none()
    
    collection_summary = None
    if collection:
        from app.domain.tools.tool_permission_schemas import CollectionSummary
        collection_summary = CollectionSummary(
            id=collection.id,
            name=collection.name,
            entity_type=collection.entity_type,
            icon=collection.icon,
            color=collection.color,
        )
    
    return ToolCollectionPermissionResponse(
        id=permission.id,
        tool_id=permission.tool_id,
        collection_id=permission.collection_id,
        permission_level=permission.permission_level,
        collection=collection_summary,
        created_at=permission.created_at,
        updated_at=permission.updated_at,
    )


@router.put(
    "/{tool_id}/permissions/{permission_id}",
    response_model=ToolCollectionPermissionResponse,
    summary="Update specific permission",
)
async def update_permission(
    tool_id: str,
    permission_id: str,
    update_data: ToolCollectionPermissionUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> ToolCollectionPermissionResponse:
    """
    Update a specific permission entry.
    """
    from app.domain.tools.tool_permission_models import ToolCollectionPermission
    from sqlalchemy import select
    from datetime import datetime, timezone
    
    result = await db.execute(
        select(ToolCollectionPermission).where(
            ToolCollectionPermission.id == permission_id,
            ToolCollectionPermission.tool_id == tool_id,
        )
    )
    permission = result.scalar_one_or_none()
    
    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Permission not found: {permission_id}"
        )
    
    # Update fields
    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        if hasattr(permission, field):
            setattr(permission, field, value)
    
    permission.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(permission)
    
    # Get collection info for response
    from app.domain.collections.models import Collection
    coll_result = await db.execute(
        select(Collection).where(Collection.id == permission.collection_id)
    )
    collection = coll_result.scalar_one_or_none()
    
    collection_summary = None
    if collection:
        from app.domain.tools.tool_permission_schemas import CollectionSummary
        collection_summary = CollectionSummary(
            id=collection.id,
            name=collection.name,
            entity_type=collection.entity_type,
            icon=collection.icon,
            color=collection.color,
        )
    
    _announce("updated", {"permission_id": permission.id, "tool_id": permission.tool_id, "collection_id": permission.collection_id, "permission_level": permission.permission_level, "event": "updated"})
    return ToolCollectionPermissionResponse(
        id=permission.id,
        tool_id=permission.tool_id,
        collection_id=permission.collection_id,
        permission_level=permission.permission_level,
        collection=collection_summary,
        created_at=permission.created_at,
        updated_at=permission.updated_at,
    )
