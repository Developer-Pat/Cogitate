"""
Tool Permissions domain service.

Provides business logic for tool-collection permission management.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func, and_, or_, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.tools.tool_permission_models import ToolCollectionPermission
from app.domain.tools.tool_permission_schemas import (
    ToolPermissionSummary,
    ToolPermissionsResponse,
    ToolPermissionsUpdateRequest,
    PermissionCheckResponse,
    AccessibleToolSummary,
    AccessibleToolsResponse,
)
from app.domain.tools.models import Tool
from app.domain.collections.models import Collection

logger = logging.getLogger(__name__)


class ToolPermissionService:
    """
    Service for managing tool-collection permissions.

    Provides CRUD operations and permission checking for tools.
    """

    def __init__(self, db: AsyncSession):
        """Initialize tool permission service."""
        self.db = db

    # =========================================================================
    # Permission CRUD Operations
    # =========================================================================

    async def get_tool_permissions(self, tool_id: str) -> Optional[ToolPermissionsResponse]:
        """
        Get all permissions for a tool.

        Args:
            tool_id: Tool ID

        Returns:
            Tool permissions response or None if tool not found
        """
        # Get tool
        tool_result = await self.db.execute(
            select(Tool).where(Tool.id == tool_id)
        )
        tool = tool_result.scalar_one_or_none()
        
        if not tool:
            return None

        # Get permissions with collection info
        perm_query = select(
            ToolCollectionPermission,
            Collection.name.label('collection_name'),
            Collection.icon.label('collection_icon'),
            Collection.color.label('collection_color'),
        ).join(
            Collection,
            ToolCollectionPermission.collection_id == Collection.id
        ).where(
            ToolCollectionPermission.tool_id == tool_id
        ).order_by(
            Collection.name
        )
        
        perm_result = await self.db.execute(perm_query)
        permissions = perm_result.all()
        
        permission_summaries = []
        for perm, coll_name, coll_icon, coll_color in permissions:
            permission_summaries.append(
                ToolPermissionSummary(
                    collection_id=perm.collection_id,
                    collection_name=coll_name,
                    permission_level=perm.permission_level,
                    member_count=0,  # Will be populated by caller if needed
                    created_at=perm.created_at,
                    updated_at=perm.updated_at,
                )
            )

        # Get default access from collections table (use first collection's default as example)
        # For now, we'll use 'read' as default if no collections exist
        default_access = 'read'
        
        return ToolPermissionsResponse(
            tool_id=tool_id,
            tool_name=tool.name,
            default_access=default_access,
            permissions=permission_summaries,
            total=len(permission_summaries),
        )

    async def update_tool_permissions(
        self,
        tool_id: str,
        update_data: ToolPermissionsUpdateRequest,
    ) -> bool:
        """
        Update permissions for a tool.

        Args:
            tool_id: Tool ID
            update_data: Permission update data

        Returns:
            True if successful
        """
        # Verify tool exists
        tool_result = await self.db.execute(
            select(Tool).where(Tool.id == tool_id)
        )
        tool = tool_result.scalar_one_or_none()
        
        if not tool:
            raise ValueError(f"Tool not found: {tool_id}")

        # Update default access on collections if provided
        if update_data.default_access:
            # Update default_tool_permission on collections that have permissions for this tool
            # For now, we'll store this in a separate config or use a system-wide default
            logger.info(f"Updating default access for tool {tool_id} to {update_data.default_access}")

        # Process permission updates
        for perm_entry in update_data.permissions:
            collection_id = perm_entry.get('collection_id')
            permission_level = perm_entry.get('permission_level')
            
            if not collection_id or not permission_level:
                continue
            
            # Check if permission exists
            existing_result = await self.db.execute(
                select(ToolCollectionPermission).where(
                    and_(
                        ToolCollectionPermission.tool_id == tool_id,
                        ToolCollectionPermission.collection_id == collection_id,
                    )
                )
            )
            existing = existing_result.scalar_one_or_none()
            
            if existing:
                # Update existing permission
                existing.permission_level = permission_level
                existing.updated_at = datetime.now(timezone.utc)
            else:
                # Create new permission
                new_perm = ToolCollectionPermission(
                    id=str(uuid.uuid4()),
                    tool_id=tool_id,
                    collection_id=collection_id,
                    permission_level=permission_level,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                self.db.add(new_perm)

        await self.db.commit()
        logger.info(f"Updated permissions for tool {tool_id}")
        return True

    async def set_collection_permission(
        self,
        tool_id: str,
        collection_id: str,
        permission_level: str,
    ) -> ToolCollectionPermission:
        """
        Set permission for a specific collection.

        Args:
            tool_id: Tool ID
            collection_id: Collection ID
            permission_level: Permission level

        Returns:
            Created or updated permission
        """
        # Check if permission exists
        existing_result = await self.db.execute(
            select(ToolCollectionPermission).where(
                and_(
                    ToolCollectionPermission.tool_id == tool_id,
                    ToolCollectionPermission.collection_id == collection_id,
                )
            )
        )
        existing = existing_result.scalar_one_or_none()
        
        if existing:
            # Update existing
            existing.permission_level = permission_level
            existing.updated_at = datetime.now(timezone.utc)
            await self.db.commit()
            await self.db.refresh(existing)
            logger.info(f"Updated permission for tool {tool_id}, collection {collection_id}")
            return existing
        else:
            # Create new
            new_perm = ToolCollectionPermission(
                id=str(uuid.uuid4()),
                tool_id=tool_id,
                collection_id=collection_id,
                permission_level=permission_level,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            self.db.add(new_perm)
            await self.db.commit()
            await self.db.refresh(new_perm)
            logger.info(f"Created permission for tool {tool_id}, collection {collection_id}")
            return new_perm

    async def remove_collection_permission(
        self,
        tool_id: str,
        collection_id: str,
    ) -> bool:
        """
        Remove permission for a specific collection.

        Args:
            tool_id: Tool ID
            collection_id: Collection ID

        Returns:
            True if removed, False if not found
        """
        result = await self.db.execute(
            select(ToolCollectionPermission).where(
                and_(
                    ToolCollectionPermission.tool_id == tool_id,
                    ToolCollectionPermission.collection_id == collection_id,
                )
            )
        )
        permission = result.scalar_one_or_none()
        
        if not permission:
            return False
        
        await self.db.delete(permission)
        await self.db.commit()
        logger.info(f"Removed permission for tool {tool_id}, collection {collection_id}")
        return True

    # =========================================================================
    # Permission Checking
    # =========================================================================

    async def check_permission(
        self,
        tool_id: str,
        user_id: str = "default",
        required_permission: str = "read",
    ) -> PermissionCheckResponse:
        """
        Check if a user has permission to access a tool.

        Args:
            tool_id: Tool ID
            user_id: User ID (defaults to "default" until auth is implemented)
            required_permission: Required permission level

        Returns:
            Permission check response
        """
        # Get user's collections
        collections_result = await self.db.execute(
            select(Collection.id, Collection.name).where(
                and_(
                    Collection.user_key == user_id,
                    Collection.is_active,
                )
            )
        )
        user_collections = {cid: cname for cid, cname in collections_result.all()}
        
        if not user_collections:
            return PermissionCheckResponse.model_construct(
                has_permission=False,
                permission_level=None,
                required=required_permission,
                message="User has no collections",
            )

        # Get tool permissions for user's collections
        perm_result = await self.db.execute(
            select(
                ToolCollectionPermission.collection_id,
                ToolCollectionPermission.permission_level,
            ).where(
                and_(
                    ToolCollectionPermission.tool_id == tool_id,
                    ToolCollectionPermission.collection_id.in_(list(user_collections.keys())),
                )
            )
        )
        permissions = perm_result.all()
        
        if not permissions:
            # No explicit permissions - use default access
            return PermissionCheckResponse(
                has_permission=True,
                permission_level='read',
                required=required_permission,
                source="default",
                message="Using default read access",
            )
        
        # Find highest permission level
        permission_hierarchy = {'read': 0, 'execute': 1, 'write': 2, 'admin': 3}
        highest_level = 'read'
        source_collection = None
        
        for coll_id, perm_level in permissions:
            if permission_hierarchy.get(perm_level, 0) > permission_hierarchy.get(highest_level, 0):
                highest_level = perm_level
                source_collection = user_collections.get(coll_id, str(coll_id))
        
        # Check if user has required permission
        has_permission = permission_hierarchy.get(highest_level, 0) >= permission_hierarchy.get(required_permission, 0)
        
        return PermissionCheckResponse(
            has_permission=has_permission,
            permission_level=highest_level,
            required=required_permission,
            source=f"collection:{source_collection}" if source_collection else None,
            message=None if has_permission else f"User has {highest_level} permission, {required_permission} required",
        )

    async def get_accessible_tools(
        self,
        user_id: str = "default",
        min_permission: str = "read",
        limit: int = 100,
        offset: int = 0,
    ) -> AccessibleToolsResponse:
        """
        Get list of tools accessible to a user.

        Args:
            user_id: User ID
            min_permission: Minimum required permission level
            limit: Maximum results
            offset: Result offset

        Returns:
            Accessible tools response
        """
        # Get user's collections
        collections_result = await self.db.execute(
            select(Collection.id).where(
                and_(
                    Collection.user_key == user_id,
                    Collection.is_active,
                )
            )
        )
        user_collection_ids = [row[0] for row in collections_result.all()]
        
        if not user_collection_ids:
            # User has no collections - return empty list
            return AccessibleToolsResponse(
                tools=[],
                total=0,
                user_id=user_id,
                permission_filter=min_permission,
            )

        # Get tools with permissions for user's collections
        permission_hierarchy = {'read': 0, 'execute': 1, 'write': 2, 'admin': 3}
        min_level_value = permission_hierarchy.get(min_permission, 0)
        
        tool_query = select(
            Tool.id,
            Tool.name,
            Tool.slug,
            Tool.description,
            Tool.icon,
            Tool.color,
            Tool.type,
            Tool.provider,
            func.max(ToolCollectionPermission.permission_level).label('max_permission'),
        ).join(
            ToolCollectionPermission,
            Tool.id == ToolCollectionPermission.tool_id,
        ).where(
            and_(
                ToolCollectionPermission.collection_id.in_(user_collection_ids),
                Tool.is_active,
            )
        ).group_by(
            Tool.id, Tool.name, Tool.slug, Tool.description, Tool.icon, Tool.color, Tool.type, Tool.provider
        ).having(
            or_(
                *[func.max(ToolCollectionPermission.permission_level) == level 
                  for level in permission_hierarchy.keys() 
                  if permission_hierarchy[level] >= min_level_value]
            )
        ).order_by(
            Tool.name
        ).offset(offset).limit(limit)
        
        tool_result = await self.db.execute(tool_query)
        tools = tool_result.all()
        
        # Get total count
        count_query = select(
            func.count(distinct(Tool.id))
        ).join(
            ToolCollectionPermission,
            Tool.id == ToolCollectionPermission.tool_id,
        ).where(
            and_(
                ToolCollectionPermission.collection_id.in_(user_collection_ids),
                Tool.is_active,
            )
        )
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0
        
        accessible_tools = []
        for tool_id, name, slug, desc, icon, color, ttype, provider, max_perm in tools:
            accessible_tools.append(
                AccessibleToolSummary(
                    id=tool_id,
                    name=name,
                    slug=slug,
                    description=desc,
                    icon=icon,
                    color=color,
                    type=ttype,
                    provider=provider,
                    permission_level=max_perm,
                )
            )

        return AccessibleToolsResponse(
            tools=accessible_tools,
            total=total,
            user_id=user_id,
            permission_filter=min_permission,
        )
