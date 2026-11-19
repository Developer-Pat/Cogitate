"""
Agent Lists API router.

REST API endpoints for agent list management.
"""

import logging
from typing import Optional, cast
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.services.agent_list_service import AgentListService
from app.domain.agent_lists.schemas import (
    AgentListCreate,
    AgentListUpdate,
    AgentListResponse,
    AgentListListResponse,
    AgentListAgentsResponse,
    AgentInListResponse,
)

logger = logging.getLogger(__name__)


def _announce(event: str, payload: dict) -> None:
    """THE CROSS-WINDOW SYNC (2026-08-25, the roadmap Phase 6):
    agent-list:<id>:<event> — the frontend's sync reloads the open pages."""
    try:
        from app.domain.messaging.services import publish
        publish(f"agent-list:{payload.get('list_id')}:{event}", payload)
    except Exception as e:  # pragma: no cover
        logger.error(f"  ❌ agent-list:{event} publish failed: {e}")


router = APIRouter(prefix="/agent-lists", tags=["Agent Lists"])


@router.get("", response_model=AgentListListResponse)
async def list_agent_lists(
    user_key: str = Query(default="default", description="User key"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db_session)
):
    """
    List all agent lists for a user.

    Returns agent lists ordered by default status (default first) and name.
    """
    service = AgentListService(db)
    agent_lists, total = await service.list_agent_lists(user_key, limit, offset)

    return AgentListListResponse(
        agent_lists=[service.to_response(al) for al in agent_lists],
        total=total
    )


@router.get("/{list_id}", response_model=AgentListResponse)
async def get_agent_list(
    list_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get a single agent list by ID.
    """
    service = AgentListService(db)
    agent_list = await service.get_agent_list(list_id)

    if not agent_list:
        raise HTTPException(status_code=404, detail="Agent list not found")

    return service.to_response(agent_list)


@router.get("/{list_id}/agents", response_model=AgentListAgentsResponse)
async def get_agents_in_list(
    list_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get all agents in an agent list.

    Returns agents in the order they appear in the list.
    """
    service = AgentListService(db)
    agents = await service.get_agents_in_list(list_id)

    return AgentListAgentsResponse(
        agents=[cast(AgentInListResponse, service.agent_to_response(agent)) for agent in agents],
        total=len(agents)
    )


@router.post("", response_model=AgentListResponse, status_code=201)
async def create_agent_list(
    data: AgentListCreate,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Create a new agent list.

    If is_default is True, this list becomes the default and any existing
    default list is unset.
    """
    service = AgentListService(db)
    agent_list = await service.create_agent_list(data)
    _announce("created", {"list_id": agent_list.id, "name": getattr(agent_list, "name", None), "event": "created"})
    return service.to_response(agent_list)


@router.put("/{list_id}", response_model=AgentListResponse)
async def update_agent_list(
    list_id: str,
    data: AgentListUpdate,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Update an existing agent list.

    Can update name, description, agent IDs, and default status.
    """
    service = AgentListService(db)
    agent_list = await service.update_agent_list(list_id, data)

    if not agent_list:
        raise HTTPException(status_code=404, detail="Agent list not found")

    _announce("updated", {"list_id": agent_list.id, "name": getattr(agent_list, "name", None), "event": "updated"})
    return service.to_response(agent_list)


@router.delete("/{list_id}", status_code=204)
async def delete_agent_list(
    list_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Delete an agent list.

    Cannot delete the last default agent list for a user.
    """
    service = AgentListService(db)
    success = await service.delete_agent_list(list_id)

    if not success:
        raise HTTPException(status_code=404, detail="Agent list not found")

    _announce("deleted", {"list_id": list_id, "event": "deleted"})


@router.post("/{list_id}/agents/{agent_id}", response_model=AgentListResponse)
async def add_agent_to_list(
    list_id: str,
    agent_id: int,
    position: Optional[int] = Query(default=None, ge=0, description="Position to insert"),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Add an agent to an agent list.

    If position is specified, the agent is inserted at that position.
    Otherwise, the agent is appended to the end.
    """
    service = AgentListService(db)
    agent_list = await service.add_agent_to_list(list_id, agent_id, position)

    if not agent_list:
        raise HTTPException(status_code=404, detail="Agent list not found")

    return service.to_response(agent_list)


@router.delete("/{list_id}/agents/{agent_id}", response_model=AgentListResponse)
async def remove_agent_from_list(
    list_id: str,
    agent_id: int,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Remove an agent from an agent list.
    """
    service = AgentListService(db)
    agent_list = await service.remove_agent_from_list(list_id, agent_id)

    if not agent_list:
        raise HTTPException(status_code=404, detail="Agent list not found")

    return service.to_response(agent_list)
