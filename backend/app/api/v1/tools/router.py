"""
Tools API Router.

Provides REST endpoints for tool management, including tool definitions,
categories, and agent-tool associations.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.domain.tools.schemas import (
    ToolCreate,
    ToolUpdate,
    ToolResponse,
    ToolListResponse,
    ToolSearchResponse,
    ToolCategoryCreate,
    ToolCategoryUpdate,
    ToolCategoryResponse,
    ToolCategoryListResponse,
    AgentToolUpdate,
    AgentToolResponse,
    AgentToolListResponse,
    AgentToolEnableRequest,
    ToolUsageLogCreate,
    ToolUsageLogResponse,
    ToolUsageLogListResponse,
    ToolUsageStatsResponse,
    ToolExecutionRequest,
    ToolExecutionResponse,
)
from app.domain.tools.services import (
    ToolCategoryService,
    ToolRegistryService,
    AgentToolService,
    ToolUsageService,
)
from app.domain.tools.execution_service import ToolExecutionService
from app.domain.tools.validators import ConfigValidationError

logger = logging.getLogger(__name__)


def _announce(topic: str, event: str, payload: dict) -> None:
    """THE CROSS-WINDOW TOOL SYNC (2026-08-25, the roadmap Phase 6):
    the tools + the categories' CRUD publish tool:<id>:<event> /
    tool-category:<id>:<event>; the frontend's sync reloads the
    open pages."""
    try:
        from app.domain.messaging.services import publish
        publish(f"{topic}:{payload.get('id')}:{event}", payload)
    except Exception as e:  # pragma: no cover
        logger.error(f"  ❌ {topic}:{event} publish failed: {e}")

router = APIRouter(prefix="/tools", tags=["tools"])


# =============================================================================
# Helper Functions
# =============================================================================


def _get_category_service(db: AsyncSession) -> ToolCategoryService:
    """Get tool category service instance."""
    return ToolCategoryService(db)


def _get_tool_service(db: AsyncSession) -> ToolRegistryService:
    """Get tool registry service instance."""
    return ToolRegistryService(db)


def _get_agent_tool_service(db: AsyncSession) -> AgentToolService:
    """Get agent-tool service instance."""
    return AgentToolService(db)


def _get_usage_service(db: AsyncSession) -> ToolUsageService:
    """Get tool usage service instance."""
    return ToolUsageService(db)


# =============================================================================
# Tool Categories Endpoints
# =============================================================================


@router.post("/categories", response_model=ToolCategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    category_data: ToolCategoryCreate,
    db: AsyncSession = Depends(get_db_session),
) -> ToolCategoryResponse:
    """
    Create a new tool category.
    
    Categories can be hierarchical (parent-child relationships).
    """
    service = _get_category_service(db)
    try:
        category = await service.create_category(category_data)
        _announce("tool-category", "created", {"id": category.id, "name": getattr(category, "name", None), "event": "created"})
        return category
    except Exception as e:
        logger.error(f"Failed to create category: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create category: {str(e)}"
        )


@router.get("/categories", response_model=ToolCategoryListResponse)
async def list_categories(
    parent_id: Optional[str] = Query(None, description="Filter by parent category ID"),
    include_children: bool = Query(False, description="Include child categories recursively"),
    db: AsyncSession = Depends(get_db_session),
) -> ToolCategoryListResponse:
    """
    List tool categories.
    
    By default, returns root categories (no parent).
    Use parent_id to filter by parent category.
    """
    service = _get_category_service(db)
    categories = await service.list_categories(parent_id, include_children)
    return ToolCategoryListResponse(categories=categories, total=len(categories))


@router.get("/categories/tree", response_model=List[Dict[str, Any]])
async def get_category_tree(
    db: AsyncSession = Depends(get_db_session),
) -> List[Dict[str, Any]]:
    """
    Get full category tree with nested children.
    
    Returns hierarchical structure suitable for UI display.
    """
    service = _get_category_service(db)
    return await service.get_category_tree()


@router.get("/categories/{category_id}", response_model=ToolCategoryResponse)
async def get_category(
    category_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> ToolCategoryResponse:
    """
    Get a category by ID.
    """
    service = _get_category_service(db)
    category = await service.get_category(category_id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category not found: {category_id}"
        )
    return category


@router.get("/categories/slug/{slug}", response_model=ToolCategoryResponse)
async def get_category_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_db_session),
) -> ToolCategoryResponse:
    """
    Get a category by slug (URL-friendly identifier).
    """
    service = _get_category_service(db)
    category = await service.get_category_by_slug(slug)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category not found with slug: {slug}"
        )
    return category


@router.put("/categories/{category_id}", response_model=ToolCategoryResponse)
async def update_category(
    category_id: str,
    category_data: ToolCategoryUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> ToolCategoryResponse:
    """
    Update a category.
    """
    service = _get_category_service(db)
    category = await service.update_category(category_id, category_data)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category not found: {category_id}"
        )
    _announce("tool-category", "updated", {"id": category_id, "name": getattr(category, "name", None), "event": "updated"})
    return category


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """
    Delete a category.
    
    Note: Deleting a category will set category_id to NULL for associated tools.
    """
    service = _get_category_service(db)
    success = await service.delete_category(category_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category not found: {category_id}"
        )


# =============================================================================
# Tool Definitions Endpoints
# =============================================================================


@router.post("", response_model=ToolResponse, status_code=status.HTTP_201_CREATED)
async def create_tool(
    tool_data: ToolCreate,
    db: AsyncSession = Depends(get_db_session),
) -> ToolResponse:
    """
    Create a new tool definition.
    
    Tools represent capabilities that can be enabled for agents.
    Each tool has a JSON Schema configuration definition.
    """
    service = _get_tool_service(db)
    try:
        tool = await service.create_tool(tool_data)
        _announce("tool", "created", {"id": tool.id, "name": getattr(tool, "name", None), "event": "created"})
        return tool
    except ConfigValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Invalid config schema", "errors": e.errors}
        )
    except Exception as e:
        logger.error(f"Failed to create tool: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create tool: {str(e)}"
        )


@router.get("", response_model=ToolListResponse)
async def list_tools(
    category_id: Optional[str] = Query(None, description="Filter by category"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    provider: Optional[str] = Query(None, description="Filter by provider"),
    tags: Optional[List[str]] = Query(None, description="Filter by tags (comma-separated)"),
    limit: int = Query(100, ge=1, le=500, description="Maximum results per page"),
    offset: int = Query(0, ge=0, description="Result offset for pagination"),
    all: bool = Query(False, description="Return all tools without pagination limits"),
    db: AsyncSession = Depends(get_db_session),
) -> ToolListResponse:
    """
    List tools with filtering and pagination.
    
    Supports filtering by category, active status, provider, and tags.
    Use `all=true` to return all tools without pagination limits.
    """
    # Override pagination if all=true
    if all:
        limit = 100000
        offset = 0
    service = _get_tool_service(db)
    tools, total = await service.list_tools(
        category_id=category_id,
        is_active=is_active,
        provider=provider,
        tags=tags,
        limit=limit,
        offset=offset,
    )
    return ToolListResponse(tools=tools, total=total)


@router.get("/search", response_model=ToolSearchResponse)
async def search_tools(
    query: str = Query(..., description="Search query string"),
    category_id: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
    db: AsyncSession = Depends(get_db_session),
) -> ToolSearchResponse:
    """
    Search tools by name, description, or tags.
    
    Returns tools matching the search query.
    """
    service = _get_tool_service(db)
    tools = await service.search_tools(query, category_id, limit)
    return ToolSearchResponse(
        tools=tools,
        total=len(tools),
        query=query,
        filters={"category_id": category_id} if category_id else None
    )


@router.get("/{tool_id}", response_model=ToolResponse)
async def get_tool(
    tool_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> ToolResponse:
    """
    Get a tool by ID.
    """
    service = _get_tool_service(db)
    tool = await service.get_tool(tool_id)
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool not found: {tool_id}"
        )
    return tool


@router.get("/slug/{slug}", response_model=ToolResponse)
async def get_tool_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_db_session),
) -> ToolResponse:
    """
    Get a tool by slug (URL-friendly identifier).
    """
    service = _get_tool_service(db)
    tool = await service.get_tool_by_slug(slug)
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool not found with slug: {slug}"
        )
    return tool


@router.put("/{tool_id}", response_model=ToolResponse)
async def update_tool(
    tool_id: str,
    tool_data: ToolUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> ToolResponse:
    """
    Update a tool definition.
    """
    service = _get_tool_service(db)
    try:
        tool = await service.update_tool(tool_id, tool_data)
        if not tool:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tool not found: {tool_id}"
            )
        _announce("tool", "updated", {"id": tool_id, "name": getattr(tool, "name", None), "event": "updated"})
        return tool
    except ConfigValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Invalid config schema", "errors": e.errors}
        )


@router.delete("/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tool(
    tool_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """
    Delete a tool definition.
    
    Note: This will also delete associated agent-tool associations.
    """
    service = _get_tool_service(db)
    success = await service.delete_tool(tool_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool not found: {tool_id}"
        )


# =============================================================================
# Agent-Tool Associations Endpoints
# =============================================================================


@router.get("/agents/{agent_id}/tools", response_model=AgentToolListResponse)
async def list_agent_tools(
    agent_id: str,
    is_enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    db: AsyncSession = Depends(get_db_session),
) -> AgentToolListResponse:
    """
    List tools enabled for a specific agent.
    """
    service = _get_agent_tool_service(db)
    tools = await service.list_agent_tools(agent_id, is_enabled)
    return AgentToolListResponse(tools=tools, total=len(tools))


@router.post("/agents/{agent_id}/tools", response_model=AgentToolResponse, status_code=status.HTTP_201_CREATED)
async def enable_tool_for_agent(
    agent_id: str,
    request: AgentToolEnableRequest,
    db: AsyncSession = Depends(get_db_session),
) -> AgentToolResponse:
    """
    Enable a tool for an agent.
    
    Associates a tool with an agent and sets configuration/priority.
    """
    service = _get_agent_tool_service(db)
    return await service.enable_tool_for_agent(
        agent_id=int(agent_id),  # type: ignore[arg-type]
        tool_id=request.tool_id,
        priority=request.priority,
        config=request.config,
    )


@router.get("/agents/{agent_id}/tools/{tool_id}", response_model=AgentToolResponse)
async def get_agent_tool(
    agent_id: str,
    tool_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> AgentToolResponse:
    """
    Get agent-tool association details.
    """
    service = _get_agent_tool_service(db)
    agent_tool = await service.get_agent_tool(agent_id, tool_id)
    if not agent_tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool {tool_id} not enabled for agent {agent_id}"
        )
    return agent_tool


@router.put("/agents/{agent_id}/tools/{tool_id}", response_model=AgentToolResponse)
async def update_agent_tool(
    agent_id: str,
    tool_id: str,
    update_data: AgentToolUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> AgentToolResponse:
    """
    Update agent-tool configuration.
    
    Can update enabled status, priority, or configuration.
    """
    service = _get_agent_tool_service(db)
    
    # Convert Pydantic model to dict for service
    update_dict = update_data.model_dump(exclude_unset=True)
    agent_tool = await service.update_agent_tool_config(agent_id, tool_id, update_dict)
    
    if not agent_tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool {tool_id} not enabled for agent {agent_id}"
        )
    return agent_tool


@router.delete("/agents/{agent_id}/tools/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_tool_from_agent(
    agent_id: str,
    tool_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """
    Remove a tool from an agent (hard delete).
    
    Completely removes the association between agent and tool.
    """
    service = _get_agent_tool_service(db)
    success = await service.remove_tool_from_agent(agent_id, tool_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool {tool_id} not enabled for agent {agent_id}"
        )


@router.post("/agents/{agent_id}/tools/{tool_id}/disable", response_model=AgentToolResponse)
async def disable_tool_for_agent(
    agent_id: str,
    tool_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> AgentToolResponse:
    """
    Disable a tool for an agent (soft delete).
    
    Keeps the association but marks it as disabled.
    """
    service = _get_agent_tool_service(db)
    agent_tool = await service.disable_tool_for_agent(agent_id, tool_id)
    if not agent_tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool {tool_id} not enabled for agent {agent_id}"
        )
    return agent_tool
# =============================================================================
# Tool Usage Logging Endpoints
# =============================================================================


@router.post("/usage/logs", response_model=ToolUsageLogResponse, status_code=status.HTTP_201_CREATED)
async def log_tool_usage(
    log_data: ToolUsageLogCreate,
    db: AsyncSession = Depends(get_db_session),
) -> ToolUsageLogResponse | None:
    """
    Log a tool usage event.
    
    Used for analytics and performance monitoring.
    """
    service = _get_usage_service(db)
    return await service.log_usage(
        tool_id=log_data.tool_id,
        agent_id=log_data.agent_id,
        session_id=log_data.session_id,
        success=log_data.success,
        execution_time_ms=log_data.execution_time_ms,
        error_message=log_data.error_message,
        metadata=log_data.metadata,
    )


# =============================================================================
# Tool Execution Endpoint
# =============================================================================


@router.post("/execute", response_model=ToolExecutionResponse)
async def execute_tool(
    request: ToolExecutionRequest,
    db: AsyncSession = Depends(get_db_session),
) -> ToolExecutionResponse:
    """
    Execute a tool on behalf of an agent.
    
    This endpoint allows agents to execute tools with proper configuration
    resolution, validation, and usage logging.
    """
    service = ToolExecutionService(db)
    result = await service.execute_tool_for_agent(
        agent_id=int(request.agent_id),  # type: ignore[arg-type]
        tool_slug=request.tool_slug,
        arguments=request.arguments,
        session_id=request.session_id,
    )
    return ToolExecutionResponse(
        success=result.success,
        tool_slug=result.tool_slug,
        tool_name=result.tool_name,
        result=result.result,
        error=result.error,
        error_type=result.error_type,
        execution_time_ms=result.execution_time_ms,
        tokens_used=result.tokens_used,
        metadata=result.metadata,
    )




@router.get("/usage/logs", response_model=ToolUsageLogListResponse)
async def get_usage_logs(
    tool_id: Optional[str] = Query(None, description="Filter by tool"),
    agent_id: Optional[str] = Query(None, description="Filter by agent"),
    session_id: Optional[str] = Query(None, description="Filter by session"),
    success: Optional[bool] = Query(None, description="Filter by success status"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Result offset"),
    db: AsyncSession = Depends(get_db_session),
) -> ToolUsageLogListResponse:
    """
    Get tool usage logs with filtering.
    
    Useful for debugging and analytics.
    """
    service = _get_usage_service(db)
    logs, total = await service.get_usage_logs(
        tool_id=tool_id,
        agent_id=agent_id,
        session_id=session_id,
        success=success,
        limit=limit,
        offset=offset,
    )
    return ToolUsageLogListResponse(logs=logs, total=total)


@router.get("/usage/stats", response_model=ToolUsageStatsResponse)
async def get_usage_stats(
    tool_id: Optional[str] = Query(None, description="Filter by tool"),
    agent_id: Optional[str] = Query(None, description="Filter by agent"),
    days: int = Query(7, ge=1, le=365, description="Number of days to analyze"),
    db: AsyncSession = Depends(get_db_session),
) -> ToolUsageStatsResponse:
    """
    Get tool usage statistics.
    
    Returns aggregated usage data for monitoring and analytics.
    """
    service = _get_usage_service(db)
    stats = await service.get_usage_stats(tool_id, agent_id, days)
    return ToolUsageStatsResponse(
        stats=stats.get("stats", []),
        period_start=cast(datetime, stats.get("cutoff_date")),
        period_end=datetime.now(timezone.utc),
    )