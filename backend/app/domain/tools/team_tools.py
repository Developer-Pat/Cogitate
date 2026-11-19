"""
Team Tools domain models.

SQLAlchemy ORM models for team-tool assignments.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional, Dict, Any

if TYPE_CHECKING:
    from app.domain.collections.models import Collection
    from app.domain.tools.models import Tool

from sqlalchemy import (
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Index,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


def generate_uuid() -> str:
    """Generate a UUID string for default values.

    Returns hex-only format (no dashes) to maintain consistency
    with existing database records that were seeded without dashes.
    """
    import uuid
    return uuid.uuid4().hex


# =============================================================================
# Team-Tool Assignments
# =============================================================================


class TeamTool(Base):
    """
    Team-tool assignments.

    Links tools to teams (collections with entity_type='agent') with configuration.
    Tools assigned to teams are automatically available to all team members.
    
    Supports:
    - Direct tool assignment (source_type='direct')
    - Priority-based conflict resolution (last team wins)
    - Agent-level override (is_active=False on agent_tools overrides team assignment)
    """

    __tablename__ = "team_tools"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    team_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("collections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tool_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="direct",
    )
    source_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
        comment="source_id",
    )
    priority: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Priority for conflict resolution (higher = more important)",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Whether this assignment is active",
    )
    config: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        comment="Tool-specific configuration for this team",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    team: Mapped["Collection"] = relationship(
        "Collection",
        back_populates="team_tools",
    )
    tool: Mapped["Tool"] = relationship(
        "Tool",
        back_populates="team_tools",
    )

    __table_args__ = (
        Index("ix_team_tools_source", "source_type", "source_id"),
        Index("ix_team_tools_team_tool", "team_id", "tool_id"),
        Index("ix_team_tools_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<TeamTool(id={self.id}, team_id={self.team_id}, tool_id={self.tool_id}, source_type={self.source_type})>"
