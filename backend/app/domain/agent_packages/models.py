"""
Agent Packages domain models.

THE AGENT PACKAGE (2026-08-24, the design in local/agent-package/):
the BLUEPRINT an agent is provisioned from — advisory definitional
metadata. The agent OWNS its copies (kit_id, skills, llm_spec);
the package is the reusable spec. The package never owns the agent.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Dict

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
    JSON,
    func,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AgentPackage(Base):
    """A canned, reusable agent spec (the blueprint).

    Bundles the toolkit ref (kit_id), the skillset (skills), and
    the LLM capability contract (llm_spec). Advisory — nothing is
    hard-enforced; a provisioner (Exa) reads the spec and creates
    an agent whose OWN fields copy these values.
    """

    __tablename__ = "agent_packages"

    # Primary key: the client-assigned string (UUID) — the pattern
    # of collections (no autoincrement; the app assigns).
    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # THE TOOLKIT ref: a tool-typed collection (entity_type='tool').
    # The package references the kit; the provisioned AGENT owns its
    # copy via agents.kit_id.
    kit_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("collections.id", ondelete="SET NULL"),
        nullable=True,
    )

    # THE SKILLSET: the skill names the package recommends.
    skills: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True,
        comment="Recommended skill names (the skillset)",
    )

    # THE LLM CAPABILITY CONTRACT (advisory): kind (chat/workflow),
    # thinking (none/low/medium/high), location (local/cloud/any),
    # min_context.
    llm_spec: Mapped[Optional[Dict]] = mapped_column(
        JSON, nullable=True,
        comment="The advisory LLM contract: kind, thinking, location, min_context",
    )

    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False,
    )

    __table_args__ = (
        Index("ix_agent_packages_active", "is_active"),
    )
