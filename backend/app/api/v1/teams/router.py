"""
Teams API Router.

Provides REST endpoints for team management and team-tool assignments.
Teams are collections with entity_type='agent' that represent groups of agents.
"""

import logging
from typing import Optional, List, cast

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.domain.collections.schemas import (
    CollectionCreate,
    CollectionUpdate,
    CollectionResponse,
    CollectionItemCreate,
    CollectionItemResponse,
)
from app.domain.collections.service import CollectionService
from app.domain.tools.team_tools_schemas import (
    TeamToolCreate,
    TeamToolResponse,
    TeamToolListResponse,
    TeamToolUpdate,
    TeamSyncRequest,
    TeamSyncWithConflicts,
)
from app.domain.tools.team_tools_service import TeamToolsService

logger = logging.getLogger(__name__)


def _announce(event: str, payload: dict) -> None:
    """THE CROSS-WINDOW TEAM SYNC (2026-08-25, the roadmap Phase 4):
    the teams' CRUD + the members/tools mutations publish
    team:<id>:<event>; the frontend's sync reloads the open page."""
    try:
        from app.domain.messaging.services import publish
        publish(f"team:{payload.get('team_id')}:{event}", payload)
    except Exception as e:  # pragma: no cover
        logger.error(f"  ❌ team:{event} publish failed: {e}")

router = APIRouter(prefix="/teams", tags=["teams"])


# =============================================================================
# Helper Functions
# =============================================================================


def _get_collection_service(db: AsyncSession) -> CollectionService:
    """Get collection service instance."""
    return CollectionService(db)


def _get_team_tools_service(db: AsyncSession) -> TeamToolsService:
    """Get team tools service instance."""
    return TeamToolsService(db)


# =============================================================================
# Team Management Endpoints (Collection-based)
# =============================================================================


@router.post("", response_model=CollectionResponse, status_code=status.HTTP_201_CREATED)
async def create_team(
    team_data: CollectionCreate,
    db: AsyncSession = Depends(get_db_session),
) -> CollectionResponse:
    """
    Create a new team.

    Teams are collections with entity_type='agent' that represent groups of agents.
    Tools assigned to teams are automatically available to all team members.
    """
    service = _get_collection_service(db)

    # Force entity_type to 'agent' for teams
    team_data.entity_type = "agent"

    try:
        team = await service.create_collection(team_data)
        _announce("created", {"team_id": team.id, "name": getattr(team, "name", None), "event": "created"})
        logger.info(f"Created team: {team.id} ({team.name})")
        return cast(CollectionResponse, team)
    except Exception as e:
        logger.error(f"Failed to create team: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create team: {str(e)}"
        )


@router.get("", response_model=List[CollectionResponse])
async def list_teams(
    search: Optional[str] = Query(None, description="Search by name or description"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    limit: int = Query(100, ge=1, le=500, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Result offset"),
    all: bool = Query(False, description="Return all teams without pagination limits"),
    db: AsyncSession = Depends(get_db_session),
) -> List[CollectionResponse]:
    """
    List all teams.

    Teams are collections with entity_type='agent'.
    Use `all=true` to return all teams without pagination limits.
    """
    # Override pagination if all=true
    if all:
        limit = 100000
        offset = 0
    service = _get_collection_service(db)
    user_key = "default"

    collections, total = await service.list_collections(
        user_key=user_key,
        entity_type="agent",
        search=search,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )

    return cast(List[CollectionResponse], collections)


@router.get("/{team_id}", response_model=CollectionResponse)
async def get_team(
    team_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> CollectionResponse:
    """
    Get a team by ID.

    Returns the team with all its members and assigned tools.
    """
    service = _get_collection_service(db)
    team = await service.get_collection(team_id)

    if not team or team.entity_type != "agent":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team not found: {team_id}"
        )

    return cast(CollectionResponse, team)


@router.put("/{team_id}", response_model=CollectionResponse)
async def update_team(
    team_id: str,
    team_data: CollectionUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> CollectionResponse:
    """
    Update a team.

    Can update name, description, color, icon, and active status.
    """
    service = _get_collection_service(db)
    team = await service.update_collection(team_id, team_data)

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team not found: {team_id}"
        )
    _announce("updated", {"team_id": team_id, "name": getattr(team, "name", None), "event": "updated"})

    return cast(CollectionResponse, team)


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(
    team_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """
    Delete a team.

    This will also remove all team-tool assignments.
    """
    service = _get_collection_service(db)
    success = await service.delete_collection(team_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team not found: {team_id}"
        )
    _announce("deleted", {"team_id": team_id, "event": "deleted"})


# =============================================================================
# Team Member Management
# =============================================================================


@router.post("/{team_id}/members", response_model=CollectionItemResponse, status_code=status.HTTP_201_CREATED)
async def add_member_to_team(
    team_id: str,
    member_data: CollectionItemCreate,
    db: AsyncSession = Depends(get_db_session),
) -> CollectionItemResponse:
    """
    Add a member (agent) to a team.

    When an agent is added to a team, they automatically receive all team tools.
    """
    collection_service = _get_collection_service(db)
    team_tools_service = _get_team_tools_service(db)

    # Verify team exists
    team = await collection_service.get_collection(team_id)
    if not team or team.entity_type != "agent":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team not found: {team_id}"
        )

    # Force entity_type to 'agent' for members
    member_data.entity_type = "agent"

    # Add member to team
    member = await collection_service.add_item_to_collection(team_id, member_data)

    if not member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to add member to team"
        )

    # Auto-sync team tools to new member
    await team_tools_service.sync_team_tools_to_agents(
        team_id=team_id,
        agent_ids=[member_data.entity_id],
    )

    logger.info(f"Added member {member_data.entity_id} to team {team_id}")
    _announce("updated", {"team_id": team_id, "event": "updated"})
    return cast(CollectionItemResponse, member)


@router.delete("/{team_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member_from_team(
    team_id: str,
    member_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """
    Remove a member from a team.

    This removes the agent from the team. Team tools remain assigned to other members.
    """
    service = _get_collection_service(db)

    # Verify team exists
    team = await service.get_collection(team_id)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team not found: {team_id}"
        )

    success = await service.remove_item_from_collection(team_id, member_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Member not found: {member_id}"
        )


@router.get("/{team_id}/members", response_model=List[CollectionItemResponse])
async def get_team_members(
    team_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> List[CollectionItemResponse]:
    """
    Get all members of a team.

    Returns the agents that belong to this team.
    """
    service = _get_collection_service(db)

    # Verify team exists
    team = await service.get_collection(team_id)
    if not team or team.entity_type != "agent":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team not found: {team_id}"
        )

    items = await service.get_collection_items(team_id)
    return cast(List[CollectionItemResponse], items)


# =============================================================================
# Team Tools Management
# =============================================================================


@router.get("/{team_id}/tools", response_model=TeamToolListResponse)
async def get_team_tools(
    team_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> TeamToolListResponse:
    """
    Get all tools assigned to a team.

    Returns the directly assigned tools.
    """
    service = _get_team_tools_service(db)

    # Verify team exists
    collection_service = _get_collection_service(db)
    team = await collection_service.get_collection(team_id)
    if not team or team.entity_type != "agent":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team not found: {team_id}"
        )

    team_tools = await service.get_team_tools(team_id)

    # Fetch tool summaries separately using raw SQL to avoid ORM relationship issues
    tool_ids = [tt.tool_id.replace('-', '') for tt in team_tools]
    tool_map = {}
    if tool_ids:
        # Build placeholders for each ID
        placeholders = ",".join([f":id{i}" for i in range(len(tool_ids))])
        params = {f"id{i}": tid for i, tid in enumerate(tool_ids)}
        query = sa_text(f"SELECT id, name, slug, description, icon, color, is_active FROM tools WHERE id IN ({placeholders})")
        result = await db.execute(query, params)
        for row in result.mappings().all():
            tool_map[row["id"]] = dict(row)

    # Convert to response format
    tools = []
    for tt in team_tools:
        tool_id_normalized = tt.tool_id.replace('-', '')
        tool_data_dict = tool_map.get(tool_id_normalized)
        tool_data = {
            "id": tt.id,
            "team_id": tt.team_id,
            "tool_id": tt.tool_id,
            "source_type": tt.source_type,
            "source_id": tt.source_id,
            "priority": tt.priority,
            "is_active": tt.is_active,
            "config": tt.config,
            "created_at": tt.created_at,
            "updated_at": tt.updated_at,
        }
        if tool_data_dict:
            tool_data["tool"] = {
                "id": tool_data_dict["id"],
                "name": tool_data_dict["name"],
                "slug": tool_data_dict["slug"],
                "description": tool_data_dict["description"],
                "icon": tool_data_dict["icon"],
                "color": tool_data_dict["color"],
                "is_active": bool(tool_data_dict["is_active"]),
            }
        tools.append(TeamToolResponse.model_validate(tool_data))

    return TeamToolListResponse(tools=tools, total=len(tools))


@router.post("/{team_id}/tools", response_model=TeamToolResponse, status_code=status.HTTP_201_CREATED)
async def assign_tool_to_team(
    team_id: str,
    tool_data: TeamToolCreate,
    db: AsyncSession = Depends(get_db_session),
) -> TeamToolResponse:
    """
    Assign a tool to a team.

    The tool will be automatically assigned to all current team members.
    Future members will also receive this tool automatically.
    """
    collection_service = _get_collection_service(db)
    service = _get_team_tools_service(db)

    # Verify team exists
    team = await collection_service.get_collection(team_id)
    if not team or team.entity_type != "agent":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team not found: {team_id}"
        )

    team_tool = await service.assign_tool_to_team(team_id, tool_data)

    if not team_tool:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to assign tool to team"
        )

    # Auto-sync to team members
    await service.sync_team_tools_to_agents(team_id=team_id)

    return TeamToolResponse.model_validate(team_tool)


@router.put("/{team_id}/tools/{tool_id}", response_model=TeamToolResponse)
async def update_team_tool(
    team_id: str,
    tool_id: str,
    update_data: TeamToolUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> TeamToolResponse:
    """
    Update team tool configuration.

    Can update priority, active status, and tool-specific config.
    """
    service = _get_team_tools_service(db)

    team_tool = await service.update_team_tool(team_id, tool_id, update_data)

    if not team_tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool assignment not found: {tool_id} in team {team_id}"
        )

    return TeamToolResponse.model_validate(team_tool)


@router.delete("/{team_id}/tools/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_tool_from_team(
    team_id: str,
    tool_id: str,
    source_type: Optional[str] = Query(None, description="Filter by source type ('direct' or 'toolbox')"),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """
    Remove a tool from a team.

    This removes the tool from all team members (unless they have overrides).
    """
    service = _get_team_tools_service(db)

    # Verify team exists
    collection_service = _get_collection_service(db)
    team = await collection_service.get_collection(team_id)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team not found: {team_id}"
        )

    success = await service.remove_tool_from_team(team_id, tool_id, source_type)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool not found in team: {tool_id}"
        )

    # Auto-sync to team members
    await service.sync_team_tools_to_agents(team_id=team_id)


# =============================================================================
# Team Toolbox Management
# =============================================================================


# =============================================================================
# Team Sync
# =============================================================================


@router.post("/{team_id}/sync", response_model=TeamSyncWithConflicts)
async def sync_team_tools(
    team_id: str,
    sync_request: Optional[TeamSyncRequest] = None,
    db: AsyncSession = Depends(get_db_session),
) -> TeamSyncWithConflicts:
    """
    Sync team tools to team members.

    This manually triggers the auto-assignment logic to ensure all team members
    have the correct tools. Useful after bulk changes or to resolve inconsistencies.

    Detects conflicts when multiple teams assign the same tool to an agent.
    Applies "last team wins" rule for conflict resolution.
    """
    service = _get_team_tools_service(db)

    # Verify team exists
    collection_service = _get_collection_service(db)
    team = await collection_service.get_collection(team_id)
    if not team or team.entity_type != "agent":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team not found: {team_id}"
        )

    agent_ids = sync_request.agent_ids if sync_request else None

    result = await service.sync_team_tools_to_agents(
        team_id=team_id,
        agent_ids=agent_ids,
    )

    return result


# Import for toolbox assign response
