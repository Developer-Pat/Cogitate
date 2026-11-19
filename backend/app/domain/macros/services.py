"""
Macros domain services.

Handles CRUD operations for macro sets and meta topics,
including slot mapping resolution for extended keyboards.

Now split into two service classes:
- ``AgentMacroService`` — operates on ``cogitate.db`` (``MacroSet`` / ``MetaTopic``)
- ``SystemMacroService`` — operates on ``main DB`` (``MacroSet`` / ``MetaTopic``)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.infrastructure.database.models import MacroSet, MetaTopic
# All macros use MacroSet/MetaTopic
from app.domain.macros.schemas import (
    MacroSetCreate,
    MacroSetUpdate,
    MacroSetResponse,
    MetaTopicCreate,
    MetaTopicUpdate,
    MetaTopicResponse,
    MetaTopicLoadResponse,
)
from app.domain.macros.db_retry_utils import retry_on_db_lock

logger = logging.getLogger(__name__)

# Default user key until authentication is implemented
DEFAULT_USER_KEY = "default"


# =============================================================================
# Agent Macro Service — operates on cogitate.db (MacroSet / MetaTopic)
# =============================================================================


class AgentMacroService:
    """Service for managing agent macro sets and meta topics in ``cogitate.db``.

    All operations use ``MacroSet`` / ``MetaTopic`` models via ``self.db``.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # -------------------------------------------------------------------------
    # Macro Set Operations
    # -------------------------------------------------------------------------

    @retry_on_db_lock(max_retries=3, base_delay=0.25)
    async def create_macro_set(self, macro_set_data: MacroSetCreate) -> MacroSetResponse:
        """Create a new macro set in ``cogitate.db``."""
        macro_set = MacroSet(
            user_key=macro_set_data.user_key,
            topic=macro_set_data.topic,
            name=macro_set_data.name,
            description=macro_set_data.description,
            f1_macro=macro_set_data.f1_macro,
            f2_macro=macro_set_data.f2_macro,
            f3_macro=macro_set_data.f3_macro,
            f4_macro=macro_set_data.f4_macro,
            f5_macro=macro_set_data.f5_macro,
            is_active=macro_set_data.is_active,
            sort_order=macro_set_data.sort_order,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(macro_set)
        await self.db.commit()
        await self.db.refresh(macro_set)
        logger.info(f"Created macro set: {macro_set.name} (topic: {macro_set.topic}, namespace: {macro_set.namespace})")
        return MacroSetResponse.model_validate(macro_set)

    async def get_macro_set(self, macro_set_id: int) -> Optional[MacroSetResponse]:
        """Get a macro set by ID from ``cogitate.db``."""
        result = await self.db.execute(
            select(MacroSet).where(MacroSet.id == macro_set_id)
        )
        macro_set = result.scalar_one_or_none()
        if macro_set:
            return MacroSetResponse.model_validate(macro_set)
        return None

    async def search_macro_sets(
        self, query: str, user_key: str = DEFAULT_USER_KEY
    ) -> List[MacroSetResponse]:
        """Search macro sets by name, topic, description, or macro content (f1_macro–f5_macro), case-insensitive."""
        search_pattern = f"%{query}%"
        query_stmt = (
            select(MacroSet)
            .where(MacroSet.user_key == user_key)
            .where(
                MacroSet.name.ilike(search_pattern)
                | MacroSet.topic.ilike(search_pattern)
                | MacroSet.description.ilike(search_pattern)
                | MacroSet.f1_macro.ilike(search_pattern)
                | MacroSet.f2_macro.ilike(search_pattern)
                | MacroSet.f3_macro.ilike(search_pattern)
                | MacroSet.f4_macro.ilike(search_pattern)
                | MacroSet.f5_macro.ilike(search_pattern)
            )
            .order_by(MacroSet.sort_order, MacroSet.name)
        )
        result = await self.db.execute(query_stmt)
        macro_sets = result.scalars().all()
        return [MacroSetResponse.model_validate(ms) for ms in macro_sets]

    async def list_macro_sets(
        self, user_key: str = DEFAULT_USER_KEY, topic: Optional[str] = None,
        all_sets: bool = False,
    ) -> List[MacroSetResponse]:
        """List macro sets with optional topic filter."""
        query = select(MacroSet)
        if not all_sets:
            query = query.where(MacroSet.user_key == user_key)
        if topic:
            query = query.where(MacroSet.topic == topic)
        query = query.order_by(MacroSet.sort_order, MacroSet.name)
        result = await self.db.execute(query)
        macro_sets = result.scalars().all()
        return [MacroSetResponse.model_validate(ms) for ms in macro_sets]

    @retry_on_db_lock(max_retries=3, base_delay=0.25)
    async def update_macro_set(
        self, macro_set_id: int, macro_set_data: MacroSetUpdate
    ) -> Optional[MacroSetResponse]:
        """Update a macro set in ``cogitate.db``."""
        result = await self.db.execute(
            select(MacroSet).where(MacroSet.id == macro_set_id)
        )
        macro_set = result.scalar_one_or_none()
        if not macro_set:
            return None

        update_data = macro_set_data.model_dump(exclude_unset=True)
        # Remove mode_slug from update data (not a column in MacroSet)
        update_data.pop('mode_slug', None)
        for field, value in update_data.items():
            setattr(macro_set, field, value)

        macro_set.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(macro_set)

        logger.info(f"Updated macro set: {macro_set.name}")
        return MacroSetResponse.model_validate(macro_set)

    @retry_on_db_lock(max_retries=3, base_delay=0.25)
    async def delete_macro_set(self, macro_set_id: int) -> bool:
        """Delete a macro set from ``cogitate.db``."""
        result = await self.db.execute(
            select(MacroSet).where(MacroSet.id == macro_set_id)
        )
        macro_set = result.scalar_one_or_none()
        if not macro_set:
            return False

        await self.db.delete(macro_set)
        await self.db.commit()
        logger.info(f"Deleted macro set: {macro_set.name}")
        return True

    async def list_topics(self, user_key: str = DEFAULT_USER_KEY) -> List[str]:
        """List all unique topics for a user."""
        result = await self.db.execute(
            select(MacroSet.topic)
            .where(MacroSet.user_key == user_key)
            .distinct()
            .order_by(MacroSet.topic)
        )
        topics = result.scalars().all()
        return list(topics)

    async def get_macro_set_by_topic(
        self, user_key: str, topic: str
    ) -> Optional[MacroSetResponse]:
        """Get macro set by topic."""
        result = await self.db.execute(
            select(MacroSet)
            .where(MacroSet.user_key == user_key)
            .where(MacroSet.topic == topic)
            .where(MacroSet.is_active)
        )
        macro_set = result.scalar_one_or_none()
        if macro_set:
            return MacroSetResponse.model_validate(macro_set)
        return None

    # -------------------------------------------------------------------------
    # Meta Topic Operations
    # -------------------------------------------------------------------------

    @retry_on_db_lock(max_retries=3, base_delay=0.25)
    async def create_meta_topic(self, meta_topic_data: MetaTopicCreate) -> MetaTopicResponse:
        """Create a new meta topic in ``cogitate.db``."""
        # topic_mappings is a Text column — JSON-serialize the
        # TopicMapping list (the raw-list form crashes SQLite binding;
        # same fix as the router, 2026-08-13 — these service methods
        # are currently unreachable from the API but must not be traps)
        import json as _json
        topic_mappings_json = _json.dumps([
            {"topic": tm.topic, "slot_start": tm.slot_start}
            for tm in meta_topic_data.topic_mappings
        ])

        meta_topic = MetaTopic(
            user_key=meta_topic_data.user_key,
            name=meta_topic_data.name,
            description=meta_topic_data.description,
            topic_mappings=topic_mappings_json,
            is_active=meta_topic_data.is_active,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(meta_topic)
        await self.db.commit()
        await self.db.refresh(meta_topic)

        logger.info(f"Created meta topic: {meta_topic.name} (namespace: {meta_topic.namespace})")
        return MetaTopicResponse.model_validate(meta_topic)

    async def get_meta_topic(self, meta_topic_id: int) -> Optional[MetaTopicResponse]:
        """Get a meta topic by ID from ``cogitate.db``."""
        result = await self.db.execute(
            select(MetaTopic).where(MetaTopic.id == meta_topic_id)
        )
        meta_topic = result.scalar_one_or_none()
        if meta_topic:
            return MetaTopicResponse.model_validate(meta_topic)
        return None

    async def list_meta_topics(
        self, user_key: str = DEFAULT_USER_KEY
    ) -> List[MetaTopicResponse]:
        """List all meta topics for a user."""
        result = await self.db.execute(
            select(MetaTopic)
            .where(MetaTopic.user_key == user_key)
            .order_by(MetaTopic.name)
        )
        meta_topics = result.scalars().all()
        return [MetaTopicResponse.model_validate(mt) for mt in meta_topics]

    @retry_on_db_lock(max_retries=3, base_delay=0.25)
    async def update_meta_topic(
        self, meta_topic_id: int, meta_topic_data: MetaTopicUpdate
    ) -> Optional[MetaTopicResponse]:
        """Update a meta topic in ``cogitate.db``."""
        result = await self.db.execute(
            select(MetaTopic).where(MetaTopic.id == meta_topic_id)
        )
        meta_topic = result.scalar_one_or_none()
        if not meta_topic:
            return None

        update_data = meta_topic_data.model_dump(exclude_unset=True)
        # Remove mode_slug from update data (not a column in MetaTopic)
        update_data.pop('mode_slug', None)

        # topic_mappings is a Text column — JSON-serialize (raw list
        # crashes SQLite binding; same fix as the router, 2026-08-13)
        if "topic_mappings" in update_data:
            import json as _json
            update_data["topic_mappings"] = _json.dumps([
                {"topic": tm.topic, "slot_start": tm.slot_start}
                for tm in (update_data["topic_mappings"] or [])
            ])

        for field, value in update_data.items():
            setattr(meta_topic, field, value)

        meta_topic.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(meta_topic)

        logger.info(f"Updated meta topic: {meta_topic.name}")
        return MetaTopicResponse.model_validate(meta_topic)

    @retry_on_db_lock(max_retries=3, base_delay=0.25)
    async def delete_meta_topic(self, meta_topic_id: int) -> bool:
        """Delete a meta topic from ``cogitate.db``."""
        result = await self.db.execute(
            select(MetaTopic).where(MetaTopic.id == meta_topic_id)
        )
        meta_topic = result.scalar_one_or_none()
        if not meta_topic:
            return False

        await self.db.delete(meta_topic)
        await self.db.commit()
        logger.info(f"Deleted meta topic: {meta_topic.name}")
        return True

    # -------------------------------------------------------------------------
    # Slot Mapping Resolution
    # -------------------------------------------------------------------------

    async def load_meta_topic(self, meta_topic_id: int) -> MetaTopicLoadResponse:
        """Load a meta topic and resolve all macros to extended slots."""
        # Get meta topic
        meta_topic = await self.get_meta_topic(meta_topic_id)
        if not meta_topic:
            raise ValueError(f"Meta topic {meta_topic_id} not found")

        # Resolve macros and track topic mappings
        extended_macros: Dict[str, str] = {}
        topic_mappings_with_range: List[Dict[str, str]] = []

        for mapping_data in meta_topic.topic_mappings:
            # Handle both dict and TopicMapping objects
            if isinstance(mapping_data, dict):
                topic = mapping_data.get("topic")
                slot_start = mapping_data.get("slot_start")
            else:
                topic = mapping_data.topic
                slot_start = mapping_data.slot_start

            if not topic or not slot_start:
                logger.warning(f"Invalid mapping: {mapping_data}")
                continue

            # Get macro set for this topic
            macro_set = await self.get_macro_set_by_topic(
                meta_topic.user_key, topic
            )

            if not macro_set:
                logger.warning(f"Macro set not found for topic: {topic}")
                continue

            # Extract macros from macro set
            macros = [
                macro_set.f1_macro,
                macro_set.f2_macro,
                macro_set.f3_macro,
                macro_set.f4_macro,
                macro_set.f5_macro,
            ]

            # Calculate starting slot number
            start_num = self._parse_slot_number(slot_start)
            if start_num is None:
                logger.warning(f"Invalid slot start: {slot_start}")
                continue

            # Map macros to extended slots
            for i, macro in enumerate(macros):
                slot_num = start_num + i
                slot_key = f"F{slot_num}"
                if macro:  # Only map if macro is defined
                    extended_macros[slot_key] = macro

            # Track topic mapping with slot range (always reported in
            # F-slot form so M-slot and F-slot meta topics look alike)
            end_num = start_num + 4  # F1-F5 means 5 slots
            topic_mappings_with_range.append({
                "topic": topic,
                "slot_start": f"F{start_num}",
                "slot_end": f"F{end_num}",
                "start_num": str(start_num),
                "end_num": str(end_num)
            })

        return MetaTopicLoadResponse(
            meta_topic_id=meta_topic_id,
            name=meta_topic.name,
            extended_macros=extended_macros,
            slot_count=len(extended_macros),
            topic_mappings=topic_mappings_with_range,
        )

    @staticmethod
    def _parse_slot_number(slot_str: str) -> Optional[int]:
        """Parse slot string to number.

        Accepts both F-slots (e.g., 'F1' -> 1) and legacy M-slots
        (e.g., 'M1' -> 1, 'M2' -> 6).  M-slots are the legacy
        topic-position convention: topic ``n`` occupies F-slots
        ``5*(n-1)+1`` .. ``5*(n-1)+5`` (5 slots per topic), matching
        the extended-keyboard layout used by F-slot meta topics
        (F1, F6, F11, ...).
        """
        if not slot_str or len(slot_str) < 2:
            return None
        prefix = slot_str[0].upper()
        try:
            num = int(slot_str[1:])
        except ValueError:
            return None
        if prefix == "F":
            return num
        if prefix == "M":
            return (num - 1) * 5 + 1
        return None


# =============================================================================
