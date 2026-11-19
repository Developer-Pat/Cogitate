"""
Agent Template API endpoints.

Provides REST API for agent template CRUD operations.
"""

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.domain.agents.schemas import (
    AgentTemplateCreate,
    AgentTemplateUpdate,
    AgentTemplateResponse,
    AgentTemplateListResponse,
    AgentTemplateApplyRequest,
    AgentResponse,
    AgentTemplateSaveFromAgentRequest,
)
from app.domain.agents.services import AgentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/templates", tags=["agent-templates"])


def get_agent_service(db: Annotated[AsyncSession, Depends(get_db)]) -> AgentService:
    """Dependency to get agent service."""
    return AgentService(db)


@router.get("", response_model=AgentTemplateListResponse)
async def list_templates(
    public: Annotated[
        Optional[bool],
        Query(description="Filter by public status (true/false, omit for all)")
    ] = None,
    search: Annotated[
        Optional[str],
        Query(min_length=1, description="Search in name and description")
    ] = None,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 10,
    service: Annotated[AgentService, Depends(get_agent_service)] = None,  # type: ignore[assignment]
) -> AgentTemplateListResponse:
    """
    List all agent templates with optional filters.

    Args:
        public: Filter by public status (true/false, omit for all)
        search: Search term in name and description
        page: Page number (only when paginating — FULL list by default)
        page_size: Items per page (only when paginating)
        service: Agent service (injected)

    Returns:
        The full template list (or the requested page when paging)
    """
    if page is not None and page_size is not None:
        skip = (page - 1) * page_size
        templates, total = await service.list_templates(
            is_public=public,
            search=search,
            skip=skip,
            limit=page_size,
        )
    else:
        templates, total = await service.list_templates(
            is_public=public,
            search=search,
        )

    return AgentTemplateListResponse(
        templates=[AgentTemplateResponse.model_validate(t) for t in templates],
        total=total,
    )


@router.get("/{template_id}", response_model=AgentTemplateResponse)
async def get_template(
    template_id: int,
    service: Annotated[AgentService, Depends(get_agent_service)],
) -> AgentTemplateResponse:
    """
    Get a specific template by ID.

    Args:
        template_id: Template ID

    Returns:
        Template details

    Raises:
        HTTPException: 404 if template not found
    """
    template = await service.get_template_by_id(template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template with id {template_id} not found",
        )
    return AgentTemplateResponse.model_validate(template)


@router.post("", response_model=AgentTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    template_data: AgentTemplateCreate,
    service: Annotated[AgentService, Depends(get_agent_service)],
) -> AgentTemplateResponse:
    """
    Create a new agent template.

    Args:
        template_data: Template creation data
        service: Agent service (injected)

    Returns:
        Created template
    """
    template = await service.create_template(template_data)
    return AgentTemplateResponse.model_validate(template)


@router.put("/{template_id}", response_model=AgentTemplateResponse)
async def update_template(
    template_id: int,
    template_data: AgentTemplateUpdate,
    service: Annotated[AgentService, Depends(get_agent_service)],
) -> AgentTemplateResponse:
    """
    Update an existing template.

    Args:
        template_id: Template ID
        template_data: Template update data
        service: Agent service (injected)

    Returns:
        Updated template

    Raises:
        HTTPException: 404 if template not found
    """
    template = await service.update_template(template_id, template_data)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template with id {template_id} not found",
        )
    return AgentTemplateResponse.model_validate(template)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: int,
    service: Annotated[AgentService, Depends(get_agent_service)],
) -> None:
    """
    Delete a template.

    Args:
        template_id: Template ID
        service: Agent service (injected)

    Raises:
        HTTPException: 404 if template not found
    """
    success = await service.delete_template(template_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template with id {template_id} not found",
        )


@router.post("/{template_id}/apply", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def apply_template(
    template_id: int,
    apply_data: AgentTemplateApplyRequest,
    service: Annotated[AgentService, Depends(get_agent_service)],
) -> AgentResponse:
    """
    Create a new agent from a template.

    This endpoint creates a new agent using the configuration from the specified template.
    The template's usage count is incremented.

    Args:
        template_id: Template ID to use
        apply_data: Agent name and optional description
        service: Agent service (injected)

    Returns:
        Created agent

    Raises:
        HTTPException: 404 if template not found
    """
    agent = await service.apply_template_to_agent(
        template_id=template_id,
        agent_name=apply_data.name,
        description=apply_data.description,
    )
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template with id {template_id} not found",
        )
    return AgentResponse.model_validate(agent)


@router.post("/from-agent/{agent_id}", response_model=AgentTemplateResponse, status_code=status.HTTP_201_CREATED)
async def save_agent_as_template(
    agent_id: int,
    template_data: AgentTemplateSaveFromAgentRequest,
    service: Annotated[AgentService, Depends(get_agent_service)],
) -> AgentTemplateResponse:
    """
    Save an existing agent configuration as a new template.

    This endpoint creates a new template using the current configuration of an agent.
    Useful for sharing successful agent configurations.

    Args:
        agent_id: ID of agent to save as template
        template_data: Template name, description, visibility, and tags
        service: Agent service (injected)

    Returns:
        Created template

    Raises:
        HTTPException: 404 if agent not found
    """
    try:
        template = await service.save_agent_as_template(
            agent_id=agent_id,
            template_name=template_data.name,
            template_description=template_data.description,
            is_public=template_data.is_public,
            tags=template_data.tags,
        )
        return AgentTemplateResponse.model_validate(template)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
