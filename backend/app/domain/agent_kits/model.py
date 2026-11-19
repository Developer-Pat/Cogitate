from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AgentKit(Base):
    """THE PLURAL KIT OWNERSHIP (2026-09-04, the agent-kits build P1).

    The agent_kits JOIN table — an agent owns N toolkits (rows of
    agent_id + kit_id). Both directions are answerable ("what does
    Bob own?" AND "who owns the Search Kit?"), the DB enforces real
    references (agents.id + collections.id), and the DYNAMIC future
    (acquiring/discarding kits at runtime) = adding/removing rows.

    The singular agents.kit_id slot is RETIRED semantically (kept
    as the display-primary / back-compat read — create_all cannot
    drop columns); THIS join is the truth.
    """

    __tablename__ = "agent_kits"

    agent_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True,
    )
    kit_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True,
        comment="The tool-typed collection (kit) the agent owns",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    def __repr__(self) -> str:
        return f"<AgentKit(agent_id={self.agent_id}, kit_id={self.kit_id!r})>"
