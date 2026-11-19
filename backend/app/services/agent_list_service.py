"""
Agent List service.

Business logic for agent list management.
"""

import uuid
import logging
from datetime import datetime, UTC
from typing import Optional, List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from app.infrastructure.database.models import AgentList, Agent
from app.domain.agent_lists.schemas import (
    AgentListCreate,
    AgentListUpdate,
    AgentListResponse,
)

logger = logging.getLogger(__name__)


class AgentListService:
    """Service for managing agent lists."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_agent_lists(
        self,
        user_key: str = "default",
        limit: int = 100,
        offset: int = 0
    ) -> tuple[List[AgentList], int]:
        """
        List all agent lists for a user.

        Args:
            user_key: User identifier
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            Tuple of (agent lists, total count)
        """
        # Get total count
        count_query = select(AgentList).where(AgentList.user_key == user_key)
        count_result = await self.db.execute(count_query)
        total = len(count_result.scalars().all())

        # Get lists
        query = (
            select(AgentList)
            .where(AgentList.user_key == user_key)
            .order_by(AgentList.is_default.desc(), AgentList.name)
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(query)
        agent_lists = list(result.scalars().all())

        return agent_lists, total

    async def get_agent_list(self, list_id: str) -> Optional[AgentList]:
        """
        Get a single agent list by ID.

        Args:
            list_id: Agent list ID

        Returns:
            AgentList or None
        """
        query = select(AgentList).where(AgentList.id == list_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_default_agent_list(self, user_key: str = "default") -> Optional[AgentList]:
        """
        Get the default agent list for a user.

        Args:
            user_key: User identifier

        Returns:
            Default AgentList or None
        """
        query = select(AgentList).where(
            AgentList.user_key == user_key,
            AgentList.is_default
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_agents_in_list(self, list_id: str) -> List[Agent]:
        """
        Get all agents in an agent list.

        Args:
            list_id: Agent list ID

        Returns:
            List of Agent objects
        """
        agent_list = await self.get_agent_list(list_id)
        if not agent_list or not agent_list.agent_ids:
            return []

        query = select(Agent).where(Agent.id.in_(agent_list.agent_ids))
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def create_agent_list(self, data: AgentListCreate) -> AgentList:
        """
        Create a new agent list.

        Args:
            data: Agent list creation data

        Returns:
            Created AgentList
        """
        # If this is set as default, unset other defaults
        if data.is_default:
            await self.db.execute(
                update(AgentList)
                .where(AgentList.user_key == data.user_key)
                .values(is_default=False)
            )

        agent_list = AgentList(
            id=str(uuid.uuid4()),
            name=data.name,
            description=data.description,
            user_key=data.user_key,
            agent_ids=data.agent_ids,
            is_default=data.is_default,
        )

        self.db.add(agent_list)
        await self.db.commit()
        await self.db.refresh(agent_list)

        logger.info(f"Created agent list: {agent_list.name} ({agent_list.id})")
        return agent_list

    async def update_agent_list(
        self,
        list_id: str,
        data: AgentListUpdate
    ) -> Optional[AgentList]:
        """
        Update an existing agent list.

        Args:
            list_id: Agent list ID
            data: Agent list update data

        Returns:
            Updated AgentList or None
        """
        # Check if list exists
        existing = await self.get_agent_list(list_id)
        if not existing:
            return None

        # If setting as default, unset other defaults
        if data.is_default and not existing.is_default:
            await self.db.execute(
                update(AgentList)
                .where(AgentList.user_key == existing.user_key)
                .where(AgentList.id != list_id)
                .values(is_default=False)
            )

        # Update fields
        update_data = {
            k: v for k, v in data.model_dump().items()
            if v is not None
        }

        if update_data:
            await self.db.execute(
                update(AgentList)
                .where(AgentList.id == list_id)
                .values(**update_data)
            )
            await self.db.commit()

        # Refresh and return
        await self.db.refresh(existing)
        return existing

    async def delete_agent_list(self, list_id: str) -> bool:
        """
        Delete an agent list.

        Args:
            list_id: Agent list ID

        Returns:
            True if deleted, False if not found
        """
        agent_list = await self.get_agent_list(list_id)
        if not agent_list:
            return False

        # Don't allow deleting the last default list
        if agent_list.is_default:
            count_query = select(AgentList).where(
                AgentList.user_key == agent_list.user_key,
                AgentList.is_default
            )
            count_result = await self.db.execute(count_query)
            if len(count_result.scalars().all()) <= 1:
                raise ValueError("Cannot delete the last default agent list")

        await self.db.execute(
            delete(AgentList).where(AgentList.id == list_id)
        )
        await self.db.commit()

        logger.info(f"Deleted agent list: {list_id}")
        return True

    async def add_agent_to_list(
        self,
        list_id: str,
        agent_id: int,
        position: Optional[int] = None
    ) -> Optional[AgentList]:
        """
        Add an agent to an agent list.

        Args:
            list_id: Agent list ID
            agent_id: Agent ID to add
            position: Position to insert (None for append)

        Returns:
            Updated AgentList or None
        """
        agent_list = await self.get_agent_list(list_id)
        if not agent_list:
            return None

        # Don't add duplicates
        if agent_id in (agent_list.agent_ids or []):
            return agent_list

        agent_ids = agent_list.agent_ids or []
        if position is not None and 0 <= position <= len(agent_ids):
            agent_ids.insert(position, agent_id)
        else:
            agent_ids.append(agent_id)

        agent_list.agent_ids = agent_ids
        agent_list.updated_at = datetime.now(UTC)

        await self.db.commit()
        await self.db.refresh(agent_list)

        logger.info(f"Added agent {agent_id} to list {list_id}")
        return agent_list

    async def remove_agent_from_list(
        self,
        list_id: str,
        agent_id: int
    ) -> Optional[AgentList]:
        """
        Remove an agent from an agent list.

        Args:
            list_id: Agent list ID
            agent_id: Agent ID to remove

        Returns:
            Updated AgentList or None
        """
        agent_list = await self.get_agent_list(list_id)
        if not agent_list:
            return None

        if agent_id not in (agent_list.agent_ids or []):
            return agent_list

        assert agent_list.agent_ids is not None
        agent_list.agent_ids = [
            aid for aid in agent_list.agent_ids if aid != agent_id
        ]
        agent_list.updated_at = datetime.now(UTC)

        await self.db.commit()
        await self.db.refresh(agent_list)

        logger.info(f"Removed agent {agent_id} from list {list_id}")
        return agent_list

    def to_response(self, agent_list: AgentList) -> AgentListResponse:
        """Convert AgentList to response schema."""
        return AgentListResponse(
            id=agent_list.id,
            name=agent_list.name,
            description=agent_list.description,
            user_key=agent_list.user_key,
            agent_ids=agent_list.agent_ids or [],
            agent_count=len(agent_list.agent_ids or []),
            is_default=agent_list.is_default,
            created_at=agent_list.created_at,
            updated_at=agent_list.updated_at,
        )

    def agent_to_response(self, agent: Agent) -> Dict[str, Any]:
        """Convert Agent to response schema."""
        return {
            "id": agent.id,
            "name": agent.name,
            "description": agent.description,
            "provider": agent.provider,
            "model": agent.model,
            "profile_image_url": agent.profile_image_url,
            "is_active": agent.is_active,
        }
