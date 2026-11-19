"""
Tools domain services.

Handles CRUD operations for tools, categories, and agent-tool associations.
Provides search, filtering, and configuration validation.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_, cast, case
from sqlalchemy import String
from sqlalchemy.orm import selectinload

from app.domain.tools.models import ToolCategory, Tool, AgentTool, ToolUsageLog
from app.domain.tools.schemas import (
    ToolCategoryCreate,
    ToolCategoryUpdate,
    ToolCategoryResponse,
    ToolCreate,
    ToolUpdate,
    ToolResponse,
    AgentToolResponse,
    ToolUsageLogResponse,
)
from app.domain.tools.validators import validate_config_schema

logger = logging.getLogger(__name__)


def _is_valid_uuid(val: Optional[str]) -> bool:
    """
    Check if a value is a valid UUID string.

    Args:
        val: Value to check

    Returns:
        True if valid UUID, False otherwise
    """
    if not val:
        return False
    try:
        uuid.UUID(str(val))
        return True
    except (ValueError, AttributeError):
        return False


# =============================================================================
# Tool Category Service
# =============================================================================


class ToolCategoryService:
    """Service for managing hierarchical tool categories."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_category(self, category_data: ToolCategoryCreate) -> ToolCategoryResponse:
        """
        Create a new tool category.

        Args:
            category_data: Category creation data

        Returns:
            Created category
        """
        category = ToolCategory(
            parent_id=category_data.parent_id,
            name=category_data.name,
            slug=category_data.slug,
            description=category_data.description,
            icon=category_data.icon,
            sort_order=category_data.sort_order,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(category)
        await self.db.commit()
        await self.db.refresh(category)

        logger.info(f"Created tool category: {category.name} (slug: {category.slug})")
        return ToolCategoryResponse.model_validate(category)

    async def get_category(self, category_id: str) -> Optional[ToolCategoryResponse]:
        """
        Get a category by ID.

        Args:
            category_id: Category ID

        Returns:
            Category or None if not found
        """
        result = await self.db.execute(
            select(ToolCategory).where(ToolCategory.id == category_id)
        )
        category = result.scalar_one_or_none()

        if category:
            return ToolCategoryResponse.model_validate(category)
        return None

    async def get_category_by_slug(self, slug: str) -> Optional[ToolCategoryResponse]:
        """
        Get a category by slug.

        Args:
            slug: Category slug

        Returns:
            Category or None if not found
        """
        result = await self.db.execute(
            select(ToolCategory).where(ToolCategory.slug == slug)
        )
        category = result.scalar_one_or_none()

        if category:
            return ToolCategoryResponse.model_validate(category)
        return None

    async def list_categories(
        self,
        parent_id: Optional[str] = None,
        include_children: bool = False,
    ) -> List[ToolCategoryResponse]:
        """
        List categories with optional parent filter.

        Args:
            parent_id: Filter by parent category ID
            include_children: If True, include child categories recursively

        Returns:
            List of categories
        """
        query = select(ToolCategory)

        if parent_id is not None:
            query = query.where(ToolCategory.parent_id == parent_id)
        else:
            # Only return root categories by default
            query = query.where(ToolCategory.parent_id.is_(None))

        query = query.order_by(ToolCategory.sort_order, ToolCategory.name)
        result = await self.db.execute(query)
        categories = result.scalars().all()

        return [ToolCategoryResponse.model_validate(cat) for cat in categories]

    async def update_category(
        self, category_id: str, category_data: ToolCategoryUpdate
    ) -> Optional[ToolCategoryResponse]:
        """
        Update a category.

        Args:
            category_id: Category ID
            category_data: Update data

        Returns:
            Updated category or None if not found
        """
        result = await self.db.execute(
            select(ToolCategory).where(ToolCategory.id == category_id)
        )
        category = result.scalar_one_or_none()

        if not category:
            return None

        update_data = category_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(category, field, value)

        category.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(category)

        logger.info(f"Updated tool category: {category.name}")
        return ToolCategoryResponse.model_validate(category)

    async def delete_category(self, category_id: str) -> bool:
        """
        Delete a category.

        Args:
            category_id: Category ID

        Returns:
            True if deleted, False if not found
        """
        result = await self.db.execute(
            select(ToolCategory).where(ToolCategory.id == category_id)
        )
        category = result.scalar_one_or_none()

        if not category:
            return False

        await self.db.delete(category)
        await self.db.commit()

        logger.info(f"Deleted tool category: {category.name}")
        return True

    async def get_category_tree(self) -> List[Dict[str, Any]]:
        """
        Get full category tree with children.

        Returns:
            List of category dictionaries with nested children
        """
        # Get all categories
        result = await self.db.execute(
            select(ToolCategory).order_by(ToolCategory.sort_order, ToolCategory.name)
        )
        all_categories = result.scalars().all()

        # Build category map
        category_map: Dict[str, Dict[str, Any]] = {}
        for cat in all_categories:
            category_map[cat.id] = {
                "id": cat.id,
                "name": cat.name,
                "slug": cat.slug,
                "description": cat.description,
                "icon": cat.icon,
                "sort_order": cat.sort_order,
                "children": [],
            }

        # Build tree
        root_categories = []
        for cat in all_categories:
            if cat.parent_id is None:
                root_categories.append(category_map[cat.id])
            elif cat.parent_id in category_map:
                category_map[cat.parent_id]["children"].append(category_map[cat.id])

        return root_categories


# =============================================================================
# Tool Registry Service
# =============================================================================


class ToolRegistryService:
    """Service for managing tool definitions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_tool(self, tool_data: ToolCreate) -> ToolResponse:
        """
        Create a new tool.

        Args:
            tool_data: Tool creation data

        Returns:
            Created tool
        """
        # Validate config_schema if provided
        if tool_data.config_schema:
            validate_config_schema(tool_data.config_schema)

        tool = Tool(
            name=tool_data.name,
            slug=tool_data.slug,
            description=tool_data.description,
            version=tool_data.version,
            category_id=tool_data.category_id,
            provider=tool_data.provider,
            type=tool_data.type,
            config_schema=tool_data.config_schema or {},
            endpoint=tool_data.endpoint,
            timeout_ms=tool_data.timeout_ms,
            requires_auth=tool_data.requires_auth,
            icon=tool_data.icon,
            color=tool_data.color,
            tags=tool_data.tags,
            is_active=tool_data.is_active,
            is_builtin=tool_data.is_builtin,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(tool)
        await self.db.commit()
        await self.db.refresh(tool)

        logger.info(f"Created tool: {tool.name} (slug: {tool.slug})")
        return await self._tool_to_response(tool)

    async def get_tool(self, tool_id: str) -> Optional[ToolResponse]:
        """
        Get a tool by ID.

        Args:
            tool_id: Tool ID

        Returns:
            Tool or None if not found
        """
        result = await self.db.execute(
            select(Tool)
            .options(selectinload(Tool.category))
            .where(Tool.id == tool_id)
        )
        tool = result.scalar_one_or_none()

        if tool:
            return await self._tool_to_response(tool)
        return None

    async def get_tool_by_slug(self, slug: str) -> Optional[ToolResponse]:
        """
        Get a tool by slug.

        Args:
            slug: Tool slug

        Returns:
            Tool or None if not found
        """
        result = await self.db.execute(
            select(Tool)
            .options(selectinload(Tool.category))
            .where(Tool.slug == slug)
        )
        tool = result.scalar_one_or_none()

        if tool:
            return await self._tool_to_response(tool)
        return None

    async def list_tools(
        self,
        category_id: Optional[str] = None,
        is_active: Optional[bool] = True,
        provider: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[List[ToolResponse], int]:
        """
        List tools with filters.

        Args:
            category_id: Filter by category
            is_active: Filter by active status (None for all)
            provider: Filter by provider
            tags: Filter by tags (must have all specified tags)
            limit: Maximum results
            offset: Result offset

        Returns:
            Tuple of (tools list, total count)
        """
        # Build base query
        query = select(Tool).options(selectinload(Tool.category))

        # Apply filters
        if category_id:
            query = query.where(Tool.category_id == category_id)
        if is_active is not None:
            query = query.where(Tool.is_active == is_active)
        if provider:
            query = query.where(Tool.provider == provider)
        if tags:
            # Tools must have all specified tags
            for tag in tags:
                query = query.where(Tool.tags.contains([tag]))

        # Get total count
        count_query = select(func.count()).select_from(Tool)
        if category_id:
            count_query = count_query.where(Tool.category_id == category_id)
        if is_active is not None:
            count_query = count_query.where(Tool.is_active == is_active)
        if provider:
            count_query = count_query.where(Tool.provider == provider)
        if tags:
            for tag in tags:
                count_query = count_query.where(Tool.tags.contains([tag]))

        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        # Apply pagination
        query = query.order_by(Tool.name).offset(offset).limit(limit)
        result = await self.db.execute(query)
        tools = result.scalars().all()

        responses = [await self._tool_to_response(tool) for tool in tools]
        return responses, total

    async def search_tools(
        self,
        query: str,
        category_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[ToolResponse]:
        """
        Search tools by name, description, or tags.

        Args:
            query: Search query string
            category_id: Optional category filter
            limit: Maximum results

        Returns:
            List of matching tools
        """
        search_pattern = f"%{query}%"

        filters = [
            Tool.name.ilike(search_pattern),
            Tool.description.ilike(search_pattern),
        ]

        # Add tag search if query looks like a tag
        if Tool.tags is not None:
            filters.append(cast(Tool.tags, String).ilike(search_pattern))

        db_query = select(Tool).options(selectinload(Tool.category)).where(
            or_(*filters)
        )

        if category_id:
            db_query = db_query.where(Tool.category_id == category_id)

        db_query = db_query.where(Tool.is_active).limit(limit)
        result = await self.db.execute(db_query)
        tools = result.scalars().all()

        return [await self._tool_to_response(tool) for tool in tools]

    async def update_tool(
        self, tool_id: str, tool_data: ToolUpdate
    ) -> Optional[ToolResponse]:
        """
        Update a tool.

        Args:
            tool_id: Tool ID
            tool_data: Update data

        Returns:
            Updated tool or None if not found
        """
        result = await self.db.execute(
            select(Tool).where(Tool.id == tool_id)
        )
        tool = result.scalar_one_or_none()

        if not tool:
            return None

        update_data = tool_data.model_dump(exclude_unset=True)

        # Validate config_schema if being updated
        if "config_schema" in update_data and update_data["config_schema"]:
            validate_config_schema(update_data["config_schema"])

        for field, value in update_data.items():
            setattr(tool, field, value)

        tool.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(tool)

        logger.info(f"Updated tool: {tool.name}")
        return await self._tool_to_response(tool)

    async def delete_tool(self, tool_id: str) -> bool:
        """
        Delete a tool.

        Args:
            tool_id: Tool ID

        Returns:
            True if deleted, False if not found
        """
        result = await self.db.execute(
            select(Tool).where(Tool.id == tool_id)
        )
        tool = result.scalar_one_or_none()

        if not tool:
            return False

        await self.db.delete(tool)
        await self.db.commit()

        logger.info(f"Deleted tool: {tool.name}")
        return True

    async def increment_usage_count(self, tool_id: str) -> None:
        """
        Increment tool usage count.

        Args:
            tool_id: Tool ID (hyphenated or not — normalized; the
            runtime's tool_def.id is hyphenated, raw sqlite rows
            are not — the recurring UUID-form split)
        """
        from app.domain.tools.grant_service import _norm_uuid
        result = await self.db.execute(
            select(Tool).where(Tool.id == _norm_uuid(tool_id))
        )
        tool = result.scalar_one_or_none()

        if tool:
            tool.usage_count = (tool.usage_count or 0) + 1
            await self.db.commit()

    async def _tool_to_response(self, tool: Tool) -> ToolResponse:
        """Convert Tool model to ToolResponse with category info."""
        from sqlalchemy import inspect

        # Check if category is loaded
        insp = inspect(tool)
        category_loaded = 'category' in insp.unloaded

        response_data = {
            "id": tool.id,
            "name": tool.name,
            "slug": tool.slug,
            "description": tool.description,
            "version": tool.version,
            "category_id": tool.category_id,
            "provider": tool.provider,
            "type": tool.type,
            "config_schema": tool.config_schema or {},
            "arguments_schema": tool.arguments_schema or {},
            "endpoint": tool.endpoint,
            "timeout_ms": tool.timeout_ms,
            "requires_auth": tool.requires_auth,
            "icon": tool.icon,
            "color": tool.color,
            "tags": tool.tags,
            "is_active": tool.is_active,
            "is_builtin": tool.is_builtin,
            "usage_count": tool.usage_count or 0,
            "access_tier": tool.access_tier,
            "capability": tool.capability,
            "created_at": tool.created_at,
            "updated_at": tool.updated_at,
        }

        if tool.category and not category_loaded:
            response_data["category"] = {
                "id": tool.category.id,
                "name": tool.category.name,
                "slug": tool.category.slug,
                "icon": tool.category.icon,
            }

        return ToolResponse.model_validate(response_data)


# =============================================================================
# Agent Tool Service
# =============================================================================


class AgentToolService:
    """Service for managing agent-tool associations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def enable_tool_for_agent(
        self,
        agent_id: int,
        tool_id: str,
        priority: int = 0,
        config: Optional[Dict[str, Any]] = None,
    ) -> AgentToolResponse:
        """
        Enable a tool for an agent.

        Args:
            agent_id: Agent ID (integer)
            tool_id: Tool ID (UUID string)
            priority: Tool priority
            config: Tool-specific configuration

        Returns:
            Created agent-tool association
        """
        # Check if association already exists
        existing = await self.get_agent_tool(str(agent_id), tool_id)
        if existing:
            # Update existing
            result = await self.update_agent_tool_config(
                str(agent_id), tool_id, {"is_enabled": True, "priority": priority, "config": config or {}}
            )
            if result is not None:
                return result

        # Convert agent_id to string for consistency with AgentTool.agent_id (Text column)
        agent_tool = AgentTool(
            agent_id=str(agent_id),
            tool_id=tool_id,
            is_enabled=True,
            priority=priority,
            config=config or {},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(agent_tool)
        await self.db.commit()
        # Skip refresh to avoid issues with UUID primary keys
        # await self.db.refresh(agent_tool)

        logger.info(f"Enabled tool {tool_id} for agent {agent_id}")
        return await self._agent_tool_to_response(agent_tool)

    async def get_agent_tool(
        self, agent_id: str, tool_id: str
    ) -> Optional[AgentToolResponse]:
        """
        Get agent-tool association by tool UUID.

        Args:
            agent_id: Agent ID
            tool_id: Tool UUID

        Returns:
            Agent-tool association or None
        """
        result = await self.db.execute(
            select(AgentTool)
            .options(
                selectinload(AgentTool.tool).selectinload(Tool.category)
            )
            .where(
                and_(
                    AgentTool.agent_id == agent_id,
                    AgentTool.tool_id == tool_id,
                )
            )
        )
        agent_tool = result.scalar_one_or_none()

        if agent_tool:
            return await self._agent_tool_to_response(agent_tool)
        return None

    async def get_agent_tool_by_slug(
        self, agent_id: str, tool_slug: str
    ) -> Optional[AgentToolResponse]:
        """
        Get agent-tool association by tool slug.

        Args:
            agent_id: Agent ID
            tool_slug: Tool slug (URL-friendly identifier)

        Returns:
            Agent-tool association or None
        """
        result = await self.db.execute(
            select(AgentTool)
            .options(
                selectinload(AgentTool.tool).selectinload(Tool.category)
            )
            .join(Tool, AgentTool.tool_id == Tool.id)
            .where(
                and_(
                    AgentTool.agent_id == agent_id,
                    Tool.slug == tool_slug,
                )
            )
        )
        agent_tool = result.scalar_one_or_none()

        if agent_tool:
            return await self._agent_tool_to_response(agent_tool)
        return None

    async def list_agent_tools(
        self,
        agent_id: str,
        is_enabled: Optional[bool] = None,
    ) -> List[AgentToolResponse]:
        """
        List all tools for an agent.

        Args:
            agent_id: Agent ID (string or integer - will be converted to string for comparison)
            is_enabled: Filter by enabled status

        Returns:
            List of agent-tool associations
        """
        # Convert agent_id to string for consistent comparison
        agent_id_str = str(agent_id)
        
        query = (
            select(AgentTool)
            .options(
                selectinload(AgentTool.tool).selectinload(Tool.category)
            )
            .where(AgentTool.agent_id == agent_id_str)
        )

        if is_enabled is not None:
            query = query.where(AgentTool.is_enabled == is_enabled)

        query = query.order_by(AgentTool.priority, AgentTool.tool_id)
        result = await self.db.execute(query)
        agent_tools = result.scalars().all()

        # Filter out None values before conversion
        return [await self._agent_tool_to_response(at) for at in agent_tools if at is not None]

    async def update_agent_tool_config(
        self,
        agent_id: str,
        tool_id: str,
        update_data: Dict[str, Any],
    ) -> Optional[AgentToolResponse]:
        """
        Update agent-tool configuration.

        Args:
            agent_id: Agent ID
            tool_id: Tool ID
            update_data: Fields to update

        Returns:
            Updated association or None
        """
        result = await self.db.execute(
            select(AgentTool)
            .options(selectinload(AgentTool.tool))
            .where(
                and_(
                    AgentTool.agent_id == agent_id,
                    AgentTool.tool_id == tool_id,
                )
            )
        )
        agent_tool = result.scalar_one_or_none()

        if not agent_tool:
            return None

        for field, value in update_data.items():
            if hasattr(agent_tool, field):
                setattr(agent_tool, field, value)

        agent_tool.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(agent_tool)

        logger.info(f"Updated tool config for agent {agent_id}, tool {tool_id}")
        return await self._agent_tool_to_response(agent_tool)

    async def disable_tool_for_agent(
        self, agent_id: str, tool_id: str
    ) -> Optional[AgentToolResponse]:
        """
        Disable a tool for an agent (soft delete).

        Args:
            agent_id: Agent ID
            tool_id: Tool ID

        Returns:
            Updated association or None
        """
        return await self.update_agent_tool_config(
            agent_id, tool_id, {"is_enabled": False}
        )

    async def remove_tool_from_agent(
        self, agent_id: str, tool_id: str
    ) -> bool:
        """
        Remove tool association from agent (hard delete).

        Args:
            agent_id: Agent ID
            tool_id: Tool ID

        Returns:
            True if removed, False if not found
        """
        result = await self.db.execute(
            select(AgentTool).where(
                and_(
                    AgentTool.agent_id == agent_id,
                    AgentTool.tool_id == tool_id,
                )
            )
        )
        agent_tool = result.scalar_one_or_none()

        if not agent_tool:
            return False

        await self.db.delete(agent_tool)
        await self.db.commit()

        logger.info(f"Removed tool {tool_id} from agent {agent_id}")
        return True

    async def _agent_tool_to_response(
        self, agent_tool: AgentTool
    ) -> AgentToolResponse:
        """Convert AgentTool model to AgentToolResponse."""
        response_data: Dict[str, Any] = {
            "id": agent_tool.id,
            "agent_id": str(agent_tool.agent_id),  # Ensure string for AgentToolResponse
            "tool_id": agent_tool.tool_id,
            "is_enabled": agent_tool.is_enabled,
            "priority": agent_tool.priority,
            "config": agent_tool.config or {},
            "created_at": agent_tool.created_at,
            "updated_at": agent_tool.updated_at,
        }

        # Load tool relationship explicitly to avoid lazy loading issues
        from sqlalchemy import select
        from app.domain.tools.models import Tool
        result = await self.db.execute(
            select(Tool).where(Tool.id == agent_tool.tool_id)
        )
        tool = result.scalar_one_or_none()
        if tool:
            response_data["tool"] = {
                "id": tool.id,
                "name": tool.name,
                "slug": tool.slug,
                "description": tool.description,
                "icon": tool.icon,
                "color": tool.color,
                "config_schema": tool.config_schema or {},
                "arguments_schema": tool.arguments_schema or {},
            }
            # Load category if exists
            if tool.category_id:
                from app.domain.tools.models import ToolCategory
                cat_result = await self.db.execute(
                    select(ToolCategory).where(ToolCategory.id == tool.category_id)
                )
                category = cat_result.scalar_one_or_none()
                if category:
                    response_data["tool"]["category"] = {
                        "id": category.id,
                        "name": category.name,
                        "slug": category.slug,
                    }

        return AgentToolResponse.model_validate(response_data)


# =============================================================================
# Tool Usage Logging Service
# =============================================================================


class ToolUsageService:
    """Service for logging and analyzing tool usage."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_usage(
        self,
        tool_id: str,
        agent_id: str,
        success: bool,
        session_id: Optional[str] = None,
        execution_time_ms: Optional[int] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[ToolUsageLogResponse]:
        """
        Log a tool usage event.

        Args:
            tool_id: Tool ID
            agent_id: Agent ID (UUID or string)
            success: Whether execution was successful
            session_id: Optional session ID (UUID or string)
            execution_time_ms: Execution time in milliseconds
            error_message: Error message if failed
            metadata: Additional metadata

        Returns:
            Created usage log

        Note:
            Silently skips logging if agent_id or session_id are not valid UUIDs,
            since the database schema requires UUID format for these fields.
            This allows workflows with non-UUID IDs to function without errors.
        """
        # Validate UUID format - skip logging if IDs don't match schema
        # This allows workflows with string/integer IDs to work without errors
        if not _is_valid_uuid(agent_id):
            logger.debug(
                f"Skipping tool usage log: agent_id '{agent_id}' is not a valid UUID"
            )
            return None

        if session_id and not _is_valid_uuid(session_id):
            logger.debug(
                f"Skipping tool usage log: session_id '{session_id}' is not a valid UUID"
            )
            return None

        try:
            log_entry = ToolUsageLog(
                tool_id=tool_id,
                agent_id=agent_id,
                session_id=session_id,
                success=success,
                execution_time_ms=execution_time_ms,
                error_message=error_message,
                log_metadata=metadata or {},
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(log_entry)
            await self.db.commit()

            # Re-query with eagerly loaded tool relationship for async-safe response
            from sqlalchemy.orm import selectinload

            result = await self.db.execute(
                select(ToolUsageLog)
                .options(selectinload(ToolUsageLog.tool))
                .where(ToolUsageLog.id == log_entry.id)
            )
            log_entry = result.scalar_one()

            # Increment usage count on tool
            registry_service = ToolRegistryService(self.db)
            await registry_service.increment_usage_count(tool_id)

            return await self._log_to_response(log_entry)

        except Exception as e:
            # Log error but don't fail the tool execution
            logger.warning(f"Failed to log tool usage: {e}")
            return None

    async def get_usage_logs(
        self,
        tool_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        success: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[List[ToolUsageLogResponse], int]:
        """
        Get usage logs with filters.

        Args:
            tool_id: Filter by tool
            agent_id: Filter by agent
            session_id: Filter by session
            success: Filter by success status
            limit: Maximum results
            offset: Result offset

        Returns:
            Tuple of (logs list, total count)
        """
        query = select(ToolUsageLog).options(selectinload(ToolUsageLog.tool))

        if tool_id:
            query = query.where(ToolUsageLog.tool_id == tool_id)
        if agent_id:
            query = query.where(ToolUsageLog.agent_id == agent_id)
        if session_id:
            query = query.where(ToolUsageLog.session_id == session_id)
        if success is not None:
            query = query.where(ToolUsageLog.success == success)

        # Get total count
        count_query = select(func.count()).select_from(ToolUsageLog)
        if tool_id:
            count_query = count_query.where(ToolUsageLog.tool_id == tool_id)
        if agent_id:
            count_query = count_query.where(ToolUsageLog.agent_id == agent_id)
        if session_id:
            count_query = count_query.where(ToolUsageLog.session_id == session_id)
        if success is not None:
            count_query = count_query.where(ToolUsageLog.success == success)

        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        # Apply pagination and ordering
        query = (
            query.order_by(ToolUsageLog.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(query)
        logs = result.scalars().all()

        responses = [await self._log_to_response(log) for log in logs]
        return responses, total

    async def get_usage_stats(
        self,
        tool_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        days: int = 7,
    ) -> Dict[str, Any]:
        """
        Get usage statistics.

        Args:
            tool_id: Filter by tool
            agent_id: Filter by agent
            days: Number of days to analyze

        Returns:
            Statistics dictionary
        """
        from datetime import timedelta

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        query = select(
            ToolUsageLog.tool_id,
            func.count().label("total"),
            func.sum(case((ToolUsageLog.success, 1), else_=0)).label("successes"),
            func.avg(ToolUsageLog.execution_time_ms).label("avg_time"),
        ).where(ToolUsageLog.created_at >= cutoff)

        if tool_id:
            query = query.where(ToolUsageLog.tool_id == tool_id)
        if agent_id:
            query = query.where(ToolUsageLog.agent_id == agent_id)

        query = query.group_by(ToolUsageLog.tool_id)
        result = await self.db.execute(query)
        rows = result.all()

        stats = []
        for row in rows:
            tool_id, total, successes, avg_time = row
            success_rate = (successes / total * 100) if total > 0 else 0
            stats.append({
                "tool_id": tool_id,
                "total_usage": total,
                "successes": successes,
                "failures": total - successes,
                "success_rate": round(success_rate, 2),
                "avg_execution_time_ms": round(avg_time, 2) if avg_time else None,
            })

        return {
            "period_days": days,
            "cutoff_date": cutoff.isoformat(),
            "stats": stats,
        }

    async def _log_to_response(
        self, log: ToolUsageLog
    ) -> ToolUsageLogResponse:
        """Convert ToolUsageLog model to ToolUsageLogResponse."""
        response_data = {
            "id": log.id,
            "tool_id": log.tool_id,
            "agent_id": log.agent_id,
            "session_id": log.session_id,
            "success": log.success,
            "execution_time_ms": log.execution_time_ms,
            "error_message": log.error_message,
            "metadata": log.log_metadata,
            "created_at": log.created_at,
        }

        # Relationship is eagerly loaded by all callers (selectinload in queries,
        # or re-queried with selectinload in log_usage)
        if log.tool:
            response_data["tool_name"] = log.tool.name

        return ToolUsageLogResponse.model_validate(response_data)
