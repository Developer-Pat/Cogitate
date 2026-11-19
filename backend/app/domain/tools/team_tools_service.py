"""
Team Tools domain service.

Provides business logic for team-tool assignment management.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional, List, Dict

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.tools.team_tools import TeamTool
from app.domain.tools.models import Tool, AgentTool
from app.domain.collections.models import Collection, CollectionItem
from app.domain.tools.team_tools_schemas import (
    TeamToolCreate,
    TeamToolUpdate,
    ConflictInfo,
    TeamSyncWithConflicts,
)

logger = logging.getLogger(__name__)


class TeamToolsService:
    """
    Service for managing team-tool assignments.

    Provides CRUD operations and auto-assignment logic for team tools.
    """

    def __init__(self, db: AsyncSession):
        """Initialize team tools service."""
        self.db = db

    # =========================================================================
    # Team Tool CRUD Operations
    # =========================================================================

    async def assign_tool_to_team(
        self,
        team_id: str,
        tool_data: TeamToolCreate,
    ) -> Optional[TeamTool]:
        """
        Assign a tool to a team.

        Args:
            team_id: Team (collection) ID
            tool_data: Tool assignment data

        Returns:
            Created team tool or None if team not found
        """
        # Verify team exists
        team = await self.db.get(Collection, team_id)
        if not team or team.entity_type != "agent":
            logger.warning(f"Team not found or invalid entity type: {team_id}")
            return None

        # Verify tool exists
        tool = await self.db.get(Tool, tool_data.tool_id)
        if not tool:
            logger.warning(f"Tool not found: {tool_data.tool_id}")
            return None

        # Check if tool already assigned from this source
        existing = await self.db.execute(
            select(TeamTool).where(
                and_(
                    TeamTool.team_id == team_id,
                    TeamTool.tool_id == tool_data.tool_id,
                    TeamTool.source_type == tool_data.source_type,
                    TeamTool.source_id == tool_data.source_id,
                )
            )
        )
        if existing.scalar_one_or_none():
            logger.info(f"Tool already assigned to team from this source: {team_id}, {tool_data.tool_id}")
            return None

        # Create team tool assignment
        team_tool = TeamTool(
            id=str(uuid.uuid4()),
            team_id=team_id,
            tool_id=tool_data.tool_id,
            source_type=tool_data.source_type,
            source_id=tool_data.source_id,
            priority=tool_data.priority,
            is_active=tool_data.is_active,
            config=tool_data.config,
        )

        self.db.add(team_tool)
        await self.db.commit()
        await self.db.refresh(team_tool)

        logger.info(f"Assigned tool {tool_data.tool_id} to team {team_id}")
        return team_tool

    async def get_team_tools(
        self,
        team_id: str,
    ) -> List[TeamTool]:
        """
        Get all tools assigned to a team.

        Args:
            team_id: Team ID

        Returns:
            List of team tools
        """
        result = await self.db.execute(
            select(TeamTool)
            .options(selectinload(TeamTool.tool))
            .where(TeamTool.team_id == team_id)
            .where(TeamTool.is_active)
            .order_by(TeamTool.priority.desc(), TeamTool.created_at)
        )
        return list(result.scalars().all())

    async def remove_tool_from_team(
        self,
        team_id: str,
        tool_id: str,
        source_type: Optional[str] = None,
    ) -> bool:
        """
        Remove a tool from a team.

        Args:
            team_id: Team ID
            tool_id: Tool ID
            source_type: Optional filter by source type ('direct')

        Returns:
            True if removed, False if not found
        """
        filters = [
            TeamTool.team_id == team_id,
            TeamTool.tool_id == tool_id,
        ]
        if source_type:
            filters.append(TeamTool.source_type == source_type)

        result = await self.db.execute(
            select(TeamTool).where(and_(*filters))
        )
        team_tool = result.scalar_one_or_none()

        if not team_tool:
            return False

        await self.db.delete(team_tool)
        await self.db.commit()

        logger.info(f"Removed tool {tool_id} from team {team_id}")
        return True

    async def update_team_tool(
        self,
        team_id: str,
        tool_id: str,
        update_data: TeamToolUpdate,
    ) -> Optional[TeamTool]:
        """
        Update team tool configuration.

        Args:
            team_id: Team ID
            tool_id: Tool ID
            update_data: Update data

        Returns:
            Updated team tool or None if not found
        """
        result = await self.db.execute(
            select(TeamTool)
            .where(
                and_(
                    TeamTool.team_id == team_id,
                    TeamTool.tool_id == tool_id,
                )
            )
        )
        team_tool = result.scalar_one_or_none()

        if not team_tool:
            return None

        # Update fields
        data = update_data.model_dump(exclude_unset=True)
        for field, value in data.items():
            setattr(team_tool, field, value)

        team_tool.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(team_tool)

        logger.info(f"Updated team tool config: {team_id}, {tool_id}")
        return team_tool

    # =========================================================================
    # Toolbox Assignment Operations
    # =========================================================================


    # =========================================================================
    # Auto-Assignment Logic
    # =========================================================================

    async def sync_team_tools_to_agents(
        self,
        team_id: str,
        agent_ids: Optional[List[str]] = None,
    ) -> TeamSyncWithConflicts:
        """
        Sync team tools to team members (agents).

        Auto-assigns all active team tools to all team members.
        Detects conflicts when multiple teams assign the same tool.
        Applies "last team wins" rule for conflicts.

        Args:
            team_id: Team ID
            agent_ids: Optional specific agent IDs to sync. If None, sync all members.

        Returns:
            Sync result with conflict information
        """
        # Get team
        team = await self.db.get(Collection, team_id)
        if not team:
            return TeamSyncWithConflicts.model_construct()

        # Get team members (agents in this collection)
        if agent_ids:
            members = agent_ids
        else:
            result = await self.db.execute(
                select(CollectionItem.entity_id)
                .where(
                    and_(
                        CollectionItem.collection_id == team_id,
                        CollectionItem.entity_type == "agent",
                    )
                )
            )
            members = [row[0] for row in result.all()]

        if not members:
            logger.info(f"No members in team {team_id}")
            return TeamSyncWithConflicts.model_construct()

        # Get team's active tools (with tool relationship eagerly loaded)
        team_tools = await self.get_team_tools(team_id)
        if not team_tools:
            logger.info(f"No active tools in team {team_id}")
            return TeamSyncWithConflicts.model_construct()

        # Ensure all tool relationships are loaded to avoid "Unknown" tool names
        for tt in team_tools:
            if tt.tool is None:
                logger.warning(f"TeamTool {tt.id} has missing tool record (tool_id={tt.tool_id})")

        # Find all teams each agent belongs to (for conflict detection)
        agent_team_map = await self._get_agent_team_map(members)

        synced_agents = []
        tools_assigned = 0
        tools_removed = 0
        conflicts_detected = 0
        conflicts = []

        for agent_id in members:
            agent_synced = await self._sync_agent_tools(
                agent_id=agent_id,
                team_id=team_id,
                team_tools=team_tools,
                agent_team_map=agent_team_map,
            )
            synced_agents.append(agent_id)
            tools_assigned += agent_synced["assigned"]
            tools_removed += agent_synced["removed"]
            conflicts_detected += agent_synced["conflicts"]

            # Record conflicts
            for conflict in agent_synced["conflict_details"]:
                conflicts.append(ConflictInfo(**conflict))

        return TeamSyncWithConflicts(
            synced_agents=synced_agents,
            tools_assigned=tools_assigned,
            tools_removed=tools_removed,
            conflicts_detected=conflicts_detected,
            conflicts=conflicts,
        )

    async def _get_agent_team_map(
        self,
        agent_ids: List[str],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get mapping of agents to their teams.

        Args:
            agent_ids: List of agent IDs

        Returns:
            Dict mapping agent_id to list of team info
        """
        result = await self.db.execute(
            select(CollectionItem.entity_id, CollectionItem.collection_id, Collection.name)
            .join(Collection, CollectionItem.collection_id == Collection.id)
            .where(
                and_(
                    CollectionItem.entity_id.in_(agent_ids),
                    CollectionItem.entity_type == "agent",
                    Collection.entity_type == "agent",  # Teams have entity_type='agent'
                )
            )
        )
        rows = result.all()

        agent_team_map: Dict[str, List[Dict[str, Any]]] = {}
        for agent_id, team_id, team_name in rows:
            if agent_id not in agent_team_map:
                agent_team_map[agent_id] = []
            agent_team_map[agent_id].append({
                "team_id": team_id,
                "team_name": team_name,
            })

        return agent_team_map

    async def _sync_agent_tools(
        self,
        agent_id: str,
        team_id: str,
        team_tools: List[TeamTool],
        agent_team_map: Dict[str, List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """
        Sync tools for a single agent.

        Args:
            agent_id: Agent ID
            team_id: Team ID
            team_tools: List of team tools
            agent_team_map: Mapping of agents to teams

        Returns:
            Dict with sync statistics
        """
        assigned = 0
        removed = 0
        conflicts = 0
        conflict_details = []
        seen_conflicts: set = set()  # Deduplicate by (agent_id, tool_id)

        # Get agent's current tools
        result = await self.db.execute(
            select(AgentTool).where(AgentTool.agent_id == agent_id)
        )
        agent_tools = {at.tool_id: at for at in result.scalars().all()}

        # Get all teams this agent belongs to
        agent_teams = agent_team_map.get(agent_id, [])

        # Pre-fetch all conflicting teams' tools to avoid repeated DB queries
        conflicting_team_tools: Dict[str, List[TeamTool]] = {}
        for t in agent_teams:
            if t["team_id"] != team_id:
                conflicting_team_tools[t["team_id"]] = await self.get_team_tools(t["team_id"])

        # For each team tool, check if it should be assigned
        for team_tool in team_tools:
            # Check for conflicts (other teams with same tool)
            conflicting_teams = [
                t for t in agent_teams
                if t["team_id"] != team_id
            ]

            is_conflict = False
            winning_team_id = team_id

            # Check if those teams also have this tool
            for other_team in conflicting_teams:
                other_team_tools = conflicting_team_tools.get(other_team["team_id"], [])
                for other_tt in other_team_tools:
                    if other_tt.tool_id == team_tool.tool_id:
                        # Conflict detected - "last team wins" (by created_at)
                        is_conflict = True
                        if other_tt.created_at > team_tool.created_at:
                            winning_team_id = other_team["team_id"]
                        break

            # Record conflict only once per tool
            if is_conflict:
                conflict_key = (agent_id, team_tool.tool_id)
                if conflict_key not in seen_conflicts:
                    seen_conflicts.add(conflict_key)
                    conflicts += 1

                    # Build list of all teams that have this tool
                    teams_with_tool = [{"team_id": team_id, "team_name": "Current Team"}]
                    for other_team in conflicting_teams:
                        other_team_tools = conflicting_team_tools.get(other_team["team_id"], [])
                        for other_tt in other_team_tools:
                            if other_tt.tool_id == team_tool.tool_id:
                                teams_with_tool.append({
                                    "team_id": other_team["team_id"],
                                    "team_name": other_team["team_name"],
                                })
                                break

                    conflict_details.append({
                        "agent_id": agent_id,
                        "tool_id": team_tool.tool_id,
                        "tool_name": team_tool.tool.name if team_tool.tool else f"Tool {team_tool.tool_id}",
                        "conflicting_teams": teams_with_tool,
                        "resolution": "last_team_wins",
                        "winning_team_id": winning_team_id,
                    })

                # If another team wins, skip assigning this tool
                if winning_team_id != team_id:
                    continue

            # Assign tool if not already present or update if needed
            if team_tool.tool_id not in agent_tools:
                # Create new agent-tool association
                agent_tool = AgentTool(
                    id=str(uuid.uuid4()),
                    agent_id=agent_id,
                    tool_id=team_tool.tool_id,
                    is_enabled=True,
                    priority=team_tool.priority,
                    config=team_tool.config,
                )
                self.db.add(agent_tool)
                assigned += 1
                logger.debug(f"Assigned tool {team_tool.tool_id} to agent {agent_id}")
            else:
                # Tool exists - check if it's from this team or needs update
                existing = agent_tools[team_tool.tool_id]
                # Update config from team assignment
                if existing.config != team_tool.config:
                    existing.config = team_tool.config
                    existing.priority = team_tool.priority
                    assigned += 1  # Count as updated

        return {
            "assigned": assigned,
            "removed": removed,
            "conflicts": conflicts,
            "conflict_details": conflict_details,
        }

    # =========================================================================
    # Conflict Detection
    # =========================================================================

    async def detect_tool_conflicts(
        self,
        agent_id: str,
    ) -> List[ConflictInfo]:
        """
        Detect tool assignment conflicts for an agent.

        Args:
            agent_id: Agent ID

        Returns:
            List of conflict information
        """
        # Get all teams this agent belongs to
        result = await self.db.execute(
            select(CollectionItem.collection_id, Collection.name)
            .join(Collection, CollectionItem.collection_id == Collection.id)
            .where(
                and_(
                    CollectionItem.entity_id == agent_id,
                    CollectionItem.entity_type == "agent",
                    Collection.entity_type == "agent",
                )
            )
        )
        teams = result.all()

        if not teams:
            return []

        team_ids = [row[0] for row in teams]

        # Get all team tools for these teams
        result = await self.db.execute(
            select(TeamTool)
            .options(selectinload(TeamTool.tool))
            .where(
                and_(
                    TeamTool.team_id.in_(team_ids),
                    TeamTool.is_active,
                )
            )
            .order_by(TeamTool.created_at)
        )
        all_team_tools = result.scalars().all()

        # Group by tool_id to find conflicts
        tool_teams: Dict[str, List[TeamTool]] = {}
        for tt in all_team_tools:
            if tt.tool_id not in tool_teams:
                tool_teams[tt.tool_id] = []
            tool_teams[tt.tool_id].append(tt)

        conflicts = []
        for tool_id, tt_list in tool_teams.items():
            if len(tt_list) > 1:
                # Multiple teams have this tool - conflict
                # Last team wins (by created_at)
                tt_list_sorted = sorted(tt_list, key=lambda x: x.created_at)
                winner = tt_list_sorted[-1]

                conflicts.append(ConflictInfo(
                    agent_id=agent_id,
                    tool_id=tool_id,
                    tool_name=winner.tool.name if winner.tool else f"Tool {tool_id}",
                    conflicting_teams=[
                        {"team_id": tt.team_id, "team_name": f"Team {tt.team_id}"}
                        for tt in tt_list
                    ],
                    resolution="last_team_wins",
                    winning_team_id=winner.team_id,
                ))

        return conflicts
