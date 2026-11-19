"""
Collections domain models.

Defines ORM models for collections and collection items.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional, List

if TYPE_CHECKING:
    from app.domain.tools.team_tools import TeamTool

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Collection(Base):
    """
    Collection database model.

    Represents a curated collection of entities (agents, tools, providers, macros, templates).
    Collections are user-specific and can be filtered by entity type.
    """

    __tablename__ = "collections"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # User identifier (e.g., "default" until auth is implemented)
    user_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Collection metadata
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Entity type filter (agent, tool, provider, macro_set, template)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Visual customization
    color: Mapped[str] = mapped_column(String(20), nullable=False, default="#3B82F6")
    icon: Mapped[str] = mapped_column(String(50), nullable=False, default="folder")

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    items: Mapped[List["CollectionItem"]] = relationship(
        "CollectionItem",
        back_populates="collection",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    team_tools: Mapped[List["TeamTool"]] = relationship(
        "TeamTool",
        back_populates="team",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Indexes
    __table_args__ = (
        Index('ix_collections_user_entity_type', 'user_key', 'entity_type'),
        Index('ix_collections_name_user', 'user_key', 'name'),
    )

    def __repr__(self) -> str:
        """String representation of collection."""
        return f"<Collection(id={self.id}, name='{self.name}', entity_type='{self.entity_type}')>"


class CollectionItem(Base):
    """
    Collection Item database model.

    Represents a single entity (agent, tool, provider, macro, template)
    that has been added to a collection.
    """

    __tablename__ = "collection_items"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # Foreign keys
    collection_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("collections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Entity reference
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Timestamps
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    collection: Mapped["Collection"] = relationship(
        "Collection", back_populates="items"
    )

    # Indexes
    __table_args__ = (
        Index('ix_collection_items_entity', 'entity_type', 'entity_id'),
        Index('ix_collection_items_collection_entity', 'collection_id', 'entity_type', 'entity_id', unique=True),
    )

    def __repr__(self) -> str:
        """String representation of collection item."""
        return f"<CollectionItem(id={self.id}, collection_id={self.collection_id}, entity='{self.entity_name}')>"
