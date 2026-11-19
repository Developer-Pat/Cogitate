"""
Dashboard API endpoints.

Provides statistics and activity data for the dashboard.
"""

import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.infrastructure.database.models import Agent, ChatSession, ChatMessage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats")
async def get_dashboard_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Get dashboard statistics.

    Returns:
        dict: Dashboard statistics including:
            - total_agents: Total number of agents
            - active_agents: Number of active agents
            - total_sessions: Total chat sessions
            - total_messages: Total messages across all sessions
            - sessions_today: Sessions created today
            - messages_today: Messages sent today
    """
    # Get agent counts
    total_agents_query = select(func.count()).select_from(Agent)
    total_agents = await db.scalar(total_agents_query)

    active_agents_query = select(func.count()).select_from(Agent).where(
        Agent.is_active == True  # noqa: E712
    )
    active_agents = await db.scalar(active_agents_query)

    # Get session counts
    total_sessions_query = select(func.count()).select_from(ChatSession)
    total_sessions = await db.scalar(total_sessions_query)

    # Get message counts
    total_messages_query = select(func.count()).select_from(ChatMessage)
    total_messages = await db.scalar(total_messages_query)

    # Get today's counts
    today_start = datetime.now().replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    sessions_today_query = select(func.count()).select_from(ChatSession).where(
        ChatSession.created_at >= today_start
    )
    sessions_today = await db.scalar(sessions_today_query)

    messages_today_query = select(func.count()).select_from(ChatMessage).where(
        ChatMessage.created_at >= today_start
    )
    messages_today = await db.scalar(messages_today_query)

    return {
        "total_agents": total_agents,
        "active_agents": active_agents,
        "total_sessions": total_sessions,
        "total_messages": total_messages,
        "sessions_today": sessions_today,
        "messages_today": messages_today,
    }


@router.get("/activity")
async def get_recent_activity(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 10,
):
    """
    Get recent activity for the dashboard.

    Args:
        limit: Number of recent activities to return

    Returns:
        dict: Recent activity including:
            - recent_sessions: Recently updated sessions
            - active_agents_list: List of active agents
    """
    # Get recent sessions
    recent_sessions_query = (
        select(ChatSession, Agent.name.label("agent_name"))
        .join(Agent, ChatSession.agent_id == Agent.id)
        .order_by(ChatSession.updated_at.desc())
        .limit(limit)
    )
    recent_sessions_result = await db.execute(recent_sessions_query)
    recent_sessions = [
        {
            "id": session.id,
            "title": session.title or "Untitled",
            "agent_name": agent_name,
            "updated_at": session.updated_at.isoformat(),
            "message_count": len(session.messages),
        }
        for session, agent_name in recent_sessions_result.all()
    ]

    # Get active agents
    active_agents_query = select(Agent).where(Agent.is_active == True).limit(5)  # noqa: E712
    active_agents_result = await db.execute(active_agents_query)
    active_agents_list = [
        {
            "id": agent.id,
            "name": agent.name,
            "provider": agent.provider,
            "model": agent.model,
        }
        for agent in active_agents_result.scalars().all()
    ]

    return {
        "recent_sessions": recent_sessions,
        "active_agents": active_agents_list,
    }
