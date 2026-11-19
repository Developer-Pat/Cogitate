"""
Tool Permission domain models.

Defines ORM models for tool-collection permission associations.
"""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    func,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def generate_uuid() -> str:
    """Generate a UUID string for default values.

    Returns hex-only format (no dashes) to maintain consistency
    with existing database records that were seeded without dashes.
    """
    import uuid
    return uuid.uuid4().hex


class ToolCollectionPermission(Base):
    """
    Tool-Collection Permission database model.

    Represents permission levels for collections to access specific tools.
    This enables collection-based access control for tools.
    """

    __tablename__ = "tool_collection_permissions"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)

    # Foreign keys
    tool_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    collection_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("collections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Permission level
    # Values: 'read', 'execute', 'write', 'admin', 'deny'
    permission_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default='read',
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    # Note: We don't define back_populates here to avoid circular dependencies
    # The relationship is managed through foreign keys only

    # Indexes
    __table_args__ = (
        Index('idx_tool_permissions_level', 'permission_level'),
        # Unique constraint to prevent duplicate permissions
        Index('idx_tool_permissions_tool_collection', 'tool_id', 'collection_id', unique=True),
    )

    def __repr__(self) -> str:
        """String representation of tool collection permission."""
        return f"<ToolCollectionPermission(tool_id={self.tool_id}, collection_id={self.collection_id}, permission={self.permission_level})>"
