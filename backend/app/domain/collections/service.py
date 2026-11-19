"""
Collections domain service.

Provides business logic for collection management.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Tuple

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.collections.models import Collection, CollectionItem
from app.domain.collections.schemas import (
    CollectionCreate,
    CollectionUpdate,
    CollectionItemCreate,
)

logger = logging.getLogger(__name__)


class CollectionService:
    """
    Service for managing collections and collection items.

    Provides CRUD operations and query methods for collections.
    """

    def __init__(self, db: AsyncSession):
        """Initialize collection service."""
        self.db = db

    # =========================================================================
    # Collection CRUD Operations
    # =========================================================================

    async def create_collection(
        self,
        collection_data: CollectionCreate,
    ) -> Collection:
        """
        Create a new collection.

        Args:
            collection_data: Collection creation data

        Returns:
            Created collection instance
        """
        collection = Collection(
            id=str(uuid.uuid4()),
            user_key=collection_data.user_key or "default",
            name=collection_data.name,
            description=collection_data.description,
            entity_type=collection_data.entity_type,
            color=collection_data.color,
            icon=collection_data.icon,
        )

        self.db.add(collection)
        await self.db.commit()
        await self.db.refresh(collection)

        logger.info(f"Created collection: {collection.id} ({collection.name})")
        return collection

    async def get_collection(
        self,
        collection_id: str,
    ) -> Optional[Collection]:
        """
        Get a collection by ID.

        Args:
            collection_id: Collection ID

        Returns:
            Collection instance or None if not found
        """
        result = await self.db.execute(
            select(Collection).where(Collection.id == collection_id)
        )
        return result.scalar_one_or_none()

    async def list_collections(
        self,
        user_key: str = "default",
        entity_type: Optional[str] = None,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[Collection], int]:
        """
        List collections with filtering and pagination.

        Args:
            user_key: User identifier
            entity_type: Filter by entity type
            search: Search by name or description
            is_active: Filter by active status
            limit: Maximum results
            offset: Result offset

        Returns:
            Tuple of (collections list, total count)
        """
        # Build base query
        query = select(Collection).where(Collection.user_key == user_key)

        # Apply filters
        if entity_type:
            query = query.where(Collection.entity_type == entity_type)

        if is_active is not None:
            query = query.where(Collection.is_active == is_active)

        if search:
            search_filter = and_(
                Collection.name.ilike(f"%{search}%"),
            )
            query = query.where(search_filter)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        query = query.order_by(Collection.name).offset(offset).limit(limit)

        result = await self.db.execute(query)
        collections = result.scalars().all()

        return list(collections), total

    async def update_collection(
        self,
        collection_id: str,
        collection_data: CollectionUpdate,
    ) -> Optional[Collection]:
        """
        Update a collection.

        Args:
            collection_id: Collection ID
            collection_data: Update data

        Returns:
            Updated collection or None if not found
        """
        collection = await self.get_collection(collection_id)
        if not collection:
            return None

        # Update fields
        update_data = collection_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(collection, field, value)

        collection.updated_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(collection)

        logger.info(f"Updated collection: {collection.id}")
        return collection

    async def delete_collection(
        self,
        collection_id: str,
    ) -> bool:
        """
        Delete a collection.

        Args:
            collection_id: Collection ID

        Returns:
            True if deleted, False if not found
        """
        collection = await self.get_collection(collection_id)
        if not collection:
            return False

        await self.db.delete(collection)
        await self.db.commit()

        logger.info(f"Deleted collection: {collection_id}")
        return True

    # =========================================================================
    # Collection Item Operations
    # =========================================================================

    async def add_item_to_collection(
        self,
        collection_id: str,
        item_data: CollectionItemCreate,
    ) -> Optional[CollectionItem]:
        """
        Add an item to a collection.

        Args:
            collection_id: Collection ID
            item_data: Item creation data

        Returns:
            Created collection item or None if collection not found
        """
        collection = await self.get_collection(collection_id)
        if not collection:
            return None

        # Check if item already exists
        existing = await self.db.execute(
            select(CollectionItem).where(
                and_(
                    CollectionItem.collection_id == collection_id,
                    CollectionItem.entity_id == item_data.entity_id,
                    CollectionItem.entity_type == item_data.entity_type,
                )
            )
        )
        if existing.scalar_one_or_none():
            logger.info(f"Item already in collection: {collection_id}, {item_data.entity_id}")
            return None

        # Create new item
        item = CollectionItem(
            id=str(uuid.uuid4()),
            collection_id=collection_id,
            entity_id=item_data.entity_id,
            entity_type=item_data.entity_type,
            entity_name=item_data.entity_name,
        )

        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)

        logger.info(f"Added item to collection: {item.id} -> {collection_id}")
        return item

    async def remove_item_from_collection(
        self,
        collection_id: str,
        item_id: str,
    ) -> bool:
        """
        Remove an item from a collection.

        Args:
            collection_id: Collection ID
            item_id: Item ID

        Returns:
            True if removed, False if not found
        """
        result = await self.db.execute(
            select(CollectionItem).where(
                and_(
                    CollectionItem.id == item_id,
                    CollectionItem.collection_id == collection_id,
                )
            )
        )
        item = result.scalar_one_or_none()

        if not item:
            return False

        await self.db.delete(item)
        await self.db.commit()

        logger.info(f"Removed item from collection: {item_id} from {collection_id}")
        return True

    async def get_collection_items(
        self,
        collection_id: str,
    ) -> List[CollectionItem]:
        """
        Get all items in a collection.

        Args:
            collection_id: Collection ID

        Returns:
            List of collection items
        """
        result = await self.db.execute(
            select(CollectionItem)
            .where(CollectionItem.collection_id == collection_id)
            .order_by(CollectionItem.added_at.desc())
        )
        return list(result.scalars().all())

    async def find_collections_containing_entity(
        self,
        user_key: str,
        entity_type: str,
        entity_id: str,
    ) -> List[Collection]:
        """
        Find all collections containing a specific entity.

        Args:
            user_key: User identifier
            entity_type: Entity type
            entity_id: Entity ID

        Returns:
            List of collections containing the entity
        """
        result = await self.db.execute(
            select(Collection)
            .options(selectinload(Collection.items))
            .join(CollectionItem)
            .where(
                and_(
                    Collection.user_key == user_key,
                    CollectionItem.entity_type == entity_type,
                    CollectionItem.entity_id == entity_id,
                )
            )
        )
        return list(result.scalars().all())

    async def is_entity_in_collection(
        self,
        collection_id: str,
        entity_type: str,
        entity_id: str,
    ) -> bool:
        """
        Check if an entity is in a collection.

        Args:
            collection_id: Collection ID
            entity_type: Entity type
            entity_id: Entity ID

        Returns:
            True if entity is in collection, False otherwise
        """
        result = await self.db.execute(
            select(CollectionItem).where(
                and_(
                    CollectionItem.collection_id == collection_id,
                    CollectionItem.entity_type == entity_type,
                    CollectionItem.entity_id == entity_id,
                )
            )
        )
        return result.scalar_one_or_none() is not None
