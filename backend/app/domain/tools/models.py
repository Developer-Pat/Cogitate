"""
Tools domain models.

SQLAlchemy ORM models for the Agent Tools Management System.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional, List, Dict, Any

if TYPE_CHECKING:
    from app.domain.tools.team_tools import TeamTool

from sqlalchemy import (
    String,
    Text,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
    JSON,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
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
# Tool Categories (Hierarchical)
# =============================================================================


class ToolCategory(Base):
    """
    Hierarchical tool categories.
    
    Supports parent-child relationships for organizing tools.
    """

    __tablename__ = "tool_categories"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=generate_uuid,
    )
    parent_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("tool_categories.id", ondelete="CASCADE"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
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
    parent: Mapped[Optional["ToolCategory"]] = relationship(
        "ToolCategory",
        back_populates="children",
        remote_side=[id],
    )
    children: Mapped[List["ToolCategory"]] = relationship(
        "ToolCategory",
        back_populates="parent",
    )
    tools: Mapped[List["Tool"]] = relationship(
        "Tool",
        back_populates="category",
    )

    __table_args__ = (
        Index("idx_tool_categories_parent", "parent_id"),
    )

    def __repr__(self) -> str:
        return f"<ToolCategory(id={self.id}, name={self.name}, slug={self.slug})>"


# =============================================================================
# Tool Definitions
# =============================================================================


class AgentToolGrant(Base):
    """A grant allowing an agent to execute a KEYED tool.

    Phase C — the keyed tier's access object (study 11). The slug
    stays identity; the grant is separate access. An agent may
    execute a keyed tool only when a grant exists (granted_by:
    user | exa | system; scope: session | permanent | run:<id>).
    """

    __tablename__ = "agent_tool_grants"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=generate_uuid,
    )
    agent_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True,
        comment="The agent that holds the grant",
    )
    tool_id: Mapped[str] = mapped_column(
        String(36), nullable=False,
        comment="The keyed tool the grant covers",
    )
    granted_by: Mapped[str] = mapped_column(
        String(20), nullable=False, default="user",
        comment="user | exa | system",
    )
    scope: Mapped[str] = mapped_column(
        String(64), nullable=False, default="permanent",
        comment="session | permanent | run:<workflow_id>",
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="NULL = permanent; session/run grants expire",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "agent_id", "tool_id", "scope", name="uq_grant_agent_tool_scope",
        ),
    )


class Tool(Base):
    """
    Tool definitions.
    
    Represents available tools that can be enabled for agents.
    Supports up to 500+ tools with rich metadata.
    """

    __tablename__ = "tools"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=generate_uuid,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[Optional[str]] = mapped_column(
        String(20), default="1.0.0", server_default=text("'1.0.0'")
    )
    category_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("tool_categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    config_schema: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    arguments_schema: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        comment="JSON Schema for tool arguments (what LLM provides)",
    )
    endpoint: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    timeout_ms: Mapped[Optional[int]] = mapped_column(
        Integer, default=30000, server_default=text("30000")
    )
    requires_auth: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("0")
    )
    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    tags: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True,
    )
    # Non-Optional: used as a boolean EXPRESSION (`where(Tool.is_active)`), which
    # mypy rejects for `bool | None`. The live column allows NULL and defaults to 1.
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("1")
    )
    is_builtin: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("0")
    )
    usage_count: Mapped[Optional[int]] = mapped_column(
        Integer, default=0, server_default=text("0")
    )
    capability: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True,
        comment="Canonical capability slug (Phase A — the ARM vocabulary)",
    )
    access_tier: Mapped[Optional[str]] = mapped_column(
        String(10), nullable=True,
        comment="gras | keyed override; NULL = derive from capability",
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
    category: Mapped[Optional["ToolCategory"]] = relationship(
        "ToolCategory",
        back_populates="tools",
    )
    agent_tools: Mapped[List["AgentTool"]] = relationship(
        "AgentTool",
        back_populates="tool",
        cascade="all, delete-orphan",
    )
    team_tools: Mapped[List["TeamTool"]] = relationship(
        "TeamTool",
        back_populates="tool",
        cascade="all, delete-orphan",
    )
    usage_logs: Mapped[List["ToolUsageLog"]] = relationship(
        "ToolUsageLog",
        back_populates="tool",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_tools_category", "category_id"),
        Index("idx_tools_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<Tool(id={self.id}, name={self.name}, slug={self.slug})>"


# =============================================================================
# Agent-Tool Associations
# =============================================================================


class AgentTool(Base):
    """
    Agent-tool associations.

    Links tools to agents with configuration and priority.
    """

    __tablename__ = "agent_tools"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=generate_uuid,
    )
    agent_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
    )
    tool_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("tools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,  # the live table has always indexed it; "which agents use this tool"
    )
    # SERVER defaults, not just Python ones: a raw SQL insert (the consistency
    # repair does exactly that) never sees a Python default, and the live
    # `agent_tools` DDL has carried DEFAULT 1 / 0 / '{}' all along — the model
    # was the side that disagreed.
    # Non-Optional on purpose: call sites use it as a boolean EXPRESSION
    # (`and_(AgentTool.is_enabled, ...)`), which mypy rejects for `bool | None`.
    # The live column allows NULL; a fresh schema says what the app means.
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("1")
    )
    priority: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    config: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        server_default=text("'{}'"),
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
    tool: Mapped["Tool"] = relationship(
        "Tool",
        back_populates="agent_tools",
    )

    __table_args__ = (
        UniqueConstraint("agent_id", "tool_id", name="uq_agent_tool"),
        Index("idx_agent_tools_agent", "agent_id"),
        Index("idx_agent_tools_enabled", "is_enabled"),
    )

    def __repr__(self) -> str:
        return f"<AgentTool(agent_id={self.agent_id}, tool_id={self.tool_id})>"


# =============================================================================
# Tool Usage Logs (Analytics)
# =============================================================================


class ToolUsageLog(Base):
    """
    Tool usage logs for analytics.
    
    Tracks tool invocations for performance monitoring and usage statistics.
    """

    __tablename__ = "tool_usage_logs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=generate_uuid,
    )
    tool_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("tools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,  # the live table has always indexed it ("usage for this tool")
    )
    agent_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )
    session_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )
    # Non-Optional: used as a boolean EXPRESSION (`case((ToolUsageLog.success, 1))`),
    # which mypy rejects for `bool | None`. The live column allows NULL.
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    execution_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    log_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        default=dict,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    tool: Mapped["Tool"] = relationship(
        "Tool",
        back_populates="usage_logs",
    )

    __table_args__ = (
        Index("idx_tool_usage_logs_created", "created_at"),
        Index("idx_tool_usage_logs_success", "success"),
    )

    def __repr__(self) -> str:
        return f"<ToolUsageLog(id={self.id}, tool_id={self.tool_id}, success={self.success})>"
