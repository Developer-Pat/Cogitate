"""
Macros export/import service.

Handles exporting and importing of individual macro sets and meta topics.
Supports sharing, templates, and data migration.

Meta topics are now stored in ``main DB`` (via ``MetaTopic``),
while macro sets remain in ``cogitate.db`` (via ``MacroSet``).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Literal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.infrastructure.database.models import MacroSet
from app.infrastructure.database.models import MetaTopic as MetaTopic
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

EXPORT_VERSION = "1.0"


class MacroExportService:
    """Service for exporting and importing macro sets and meta topics."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # Export Operations
    # =========================================================================

    async def export_macro_set(self, macro_set_id: int) -> Dict[str, Any]:
        """
        Export a single macro set as JSON.

        Args:
            macro_set_id: ID of the macro set to export

        Returns:
            Export data dictionary

        Raises:
            ValueError: If macro set not found
        """
        result = await self.db.execute(
            select(MacroSet).where(MacroSet.id == macro_set_id)
        )
        macro_set = result.scalar_one_or_none()

        if not macro_set:
            raise ValueError(f"Macro set {macro_set_id} not found")

        export_data = {
            "export_type": "macro_set",
            "version": EXPORT_VERSION,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "data": {
                "topic": macro_set.topic,
                "name": macro_set.name,
                "description": macro_set.description,
                "f1_macro": macro_set.f1_macro,
                "f2_macro": macro_set.f2_macro,
                "f3_macro": macro_set.f3_macro,
                "f4_macro": macro_set.f4_macro,
                "f5_macro": macro_set.f5_macro,
                "is_active": macro_set.is_active,
                "sort_order": macro_set.sort_order,
            },
        }

        logger.info(f"Exported macro set: {macro_set.name} (topic: {macro_set.topic})")
        return export_data

    async def export_meta_topic(self, meta_topic_id: int) -> Dict[str, Any]:
        """
        Export a meta topic with all referenced macro sets.

        Meta topics are read from ``main DB`` (via ``AsyncSessionLocal``),
        while referenced macro sets are read from ``cogitate.db`` (via ``self.db``).

        Args:
            meta_topic_id: ID of the meta topic to export

        Returns:
            Export data dictionary

        Raises:
            ValueError: If meta topic not found
        """
        async with AsyncSessionLocal() as meta_db:
            result = await meta_db.execute(
                select(MetaTopic).where(MetaTopic.id == meta_topic_id)
            )
            meta_topic = result.scalar_one_or_none()

            if not meta_topic:
                raise ValueError(f"Meta topic {meta_topic_id} not found")

            # Export referenced macro sets (from cogitate.db via self.db)
            referenced_macro_sets = []
            topic_mappings_raw: list[dict[str, Any]] = meta_topic.topic_mappings or []  # type: ignore[assignment]
            topic_mappings: list[dict[str, Any]] = (
                topic_mappings_raw if isinstance(topic_mappings_raw, list) else []
            )

            for mapping in topic_mappings:
                if isinstance(mapping, dict):
                    topic = mapping.get("topic")
                else:
                    topic = mapping.topic if hasattr(mapping, "topic") else None

                if topic:
                    # Get macro set for this topic from cogitate.db
                    macro_set_result = await self.db.execute(
                        select(MacroSet)
                        .where(MacroSet.topic == topic)
                        .where(MacroSet.is_active)
                    )
                    macro_set = macro_set_result.scalar_one_or_none()

                    if macro_set:
                        referenced_macro_sets.append({
                            "topic": macro_set.topic,
                            "name": macro_set.name,
                            "description": macro_set.description,
                            "f1_macro": macro_set.f1_macro,
                            "f2_macro": macro_set.f2_macro,
                            "f3_macro": macro_set.f3_macro,
                            "f4_macro": macro_set.f4_macro,
                            "f5_macro": macro_set.f5_macro,
                            "is_active": macro_set.is_active,
                            "sort_order": macro_set.sort_order,
                        })

            export_data = {
                "export_type": "meta_topic",
                "version": EXPORT_VERSION,
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "name": meta_topic.name,
                    "description": meta_topic.description,
                    "topic_mappings": meta_topic.topic_mappings,
                    "is_active": meta_topic.is_active,
                    "referenced_macro_sets": referenced_macro_sets,
                },
            }

            logger.info(
                f"Exported meta topic: {meta_topic.name} "
                f"with {len(referenced_macro_sets)} referenced macro sets"
            )
            return export_data

    async def export_all_macro_sets(
        self,
        user_key: str = "default"
    ) -> Dict[str, Any]:
        """
        Export all macro sets for a user.

        Args:
            user_key: User identifier

        Returns:
            Export data dictionary
        """
        result = await self.db.execute(
            select(MacroSet)
            .where(MacroSet.user_key == user_key)
            .order_by(MacroSet.topic)
        )
        macro_sets = result.scalars().all()

        export_data = {
            "export_type": "all_macro_sets",
            "version": EXPORT_VERSION,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "user_key": user_key,
            "macro_sets_count": len(macro_sets),
            "data": [
                {
                    "topic": ms.topic,
                    "name": ms.name,
                    "description": ms.description,
                    "f1_macro": ms.f1_macro,
                    "f2_macro": ms.f2_macro,
                    "f3_macro": ms.f3_macro,
                    "f4_macro": ms.f4_macro,
                    "f5_macro": ms.f5_macro,
                    "is_active": ms.is_active,
                    "sort_order": ms.sort_order,
                }
                for ms in macro_sets
            ],
        }

        logger.info(f"Exported {len(macro_sets)} macro sets for user {user_key}")
        return export_data

    # =========================================================================
    # Import Operations
    # =========================================================================

    async def import_macro_set(
        self,
        data: Dict[str, Any],
        user_key: str = "default",
        conflict_strategy: Literal["skip", "overwrite", "merge"] = "skip"
    ) -> Optional[MacroSet]:
        """
        Import a macro set from export data.

        Args:
            data: Export data dictionary
            user_key: User identifier
            conflict_strategy: How to handle conflicts
                - "skip": Don't import if macro set exists
                - "overwrite": Replace existing macro set
                - "merge": Update existing macro set with new data

        Returns:
            Imported or updated MacroSet, or None if skipped

        Raises:
            ValueError: If export data is invalid
        """
        # Validate export data
        if data.get("export_type") != "macro_set":
            raise ValueError("Invalid export type: expected 'macro_set'")

        if "data" not in data:
            raise ValueError("Missing 'data' in export")

        macro_data = data["data"]

        # Check for existing macro set with same topic
        existing_result = await self.db.execute(
            select(MacroSet)
            .where(MacroSet.user_key == user_key)
            .where(MacroSet.topic == macro_data["topic"])
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            if conflict_strategy == "skip":
                logger.info(
                    f"Skipping import of macro set '{macro_data['topic']}' (already exists)"
                )
                return None
            elif conflict_strategy == "overwrite":
                # Delete existing
                await self.db.delete(existing)
                await self.db.commit()
                logger.info(f"Deleted existing macro set: {existing.name}")
            elif conflict_strategy == "merge":
                # Update existing
                for key, value in macro_data.items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)
                existing.updated_at = datetime.now(timezone.utc)
                await self.db.commit()
                await self.db.refresh(existing)
                logger.info(f"Merged macro set: {existing.name}")
                return existing

        # Create new macro set
        macro_set = MacroSet(
            user_key=user_key,
            topic=macro_data["topic"],
            name=macro_data["name"],
            description=macro_data.get("description"),
            f1_macro=macro_data.get("f1_macro"),
            f2_macro=macro_data.get("f2_macro"),
            f3_macro=macro_data.get("f3_macro"),
            f4_macro=macro_data.get("f4_macro"),
            f5_macro=macro_data.get("f5_macro"),
            is_active=macro_data.get("is_active", True),
            sort_order=macro_data.get("sort_order", 0),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        self.db.add(macro_set)
        await self.db.commit()
        await self.db.refresh(macro_set)

        logger.info(f"Imported macro set: {macro_set.name} (topic: {macro_set.topic})")
        return macro_set

    async def import_meta_topic(
        self,
        data: Dict[str, Any],
        user_key: str = "default",
        conflict_strategy: Literal["skip", "overwrite", "merge"] = "skip",
        import_referenced_macros: bool = True
    ) -> Optional[MetaTopic]:
        """
        Import a meta topic from export data.

        Meta topics are stored in ``main DB`` (via ``AsyncSessionLocal``),
        while referenced macro sets are stored in ``cogitate.db`` (via ``self.db``).

        Args:
            data: Export data dictionary
            user_key: User identifier
            conflict_strategy: How to handle conflicts
            import_referenced_macros: Whether to import referenced macro sets

        Returns:
            Imported or updated MetaTopic, or None if skipped

        Raises:
            ValueError: If export data is invalid
        """
        # Validate export data
        if data.get("export_type") != "meta_topic":
            raise ValueError("Invalid export type: expected 'meta_topic'")

        if "data" not in data:
            raise ValueError("Missing 'data' in export")

        meta_data = data["data"]

        async with AsyncSessionLocal() as meta_db:
            # Check for existing meta topic with same name
            existing_result = await meta_db.execute(
                select(MetaTopic)
                .where(MetaTopic.name == meta_data["name"])
            )
            existing = existing_result.scalar_one_or_none()

            if existing:
                if conflict_strategy == "skip":
                    logger.info(
                        f"Skipping import of meta topic '{meta_data['name']}' (already exists)"
                    )
                    return None
                elif conflict_strategy == "overwrite":
                    # Delete existing
                    await meta_db.delete(existing)
                    await meta_db.commit()
                    logger.info(f"Deleted existing meta topic: {existing.name}")
                elif conflict_strategy == "merge":
                    # Update existing
                    existing.name = meta_data["name"]
                    existing.description = meta_data.get("description")
                    existing.topic_mappings = meta_data.get("topic_mappings", [])
                    existing.is_active = meta_data.get("is_active", True)
                    existing.updated_at = datetime.now(timezone.utc)
                    await meta_db.commit()
                    await meta_db.refresh(existing)
                    logger.info(f"Merged meta topic: {existing.name}")

                    # Import referenced macros if requested (cogitate.db)
                    if import_referenced_macros:
                        await self._import_referenced_macros(
                            meta_data.get("referenced_macro_sets", []),
                            user_key,
                            conflict_strategy
                        )

                    return existing

            # Create new meta topic
            meta_topic = MetaTopic(
                name=meta_data["name"],
                description=meta_data.get("description"),
                topic_mappings=meta_data.get("topic_mappings", []),
                is_active=meta_data.get("is_active", True),
                namespace="agent",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

            meta_db.add(meta_topic)
            await meta_db.commit()
            await meta_db.refresh(meta_topic)

            logger.info(f"Imported meta topic: {meta_topic.name}")

            # Import referenced macros if requested (cogitate.db)
            if import_referenced_macros:
                await self._import_referenced_macros(
                    meta_data.get("referenced_macro_sets", []),
                    user_key,
                    conflict_strategy
                )

            return meta_topic

    async def _import_referenced_macros(
        self,
        macro_sets_data: List[Dict[str, Any]],
        user_key: str,
        conflict_strategy: Literal["skip", "overwrite", "merge"] = "skip"
    ) -> int:
        """
        Import referenced macro sets from meta topic export.

        Args:
            macro_sets_data: List of macro set data
            user_key: User identifier
            conflict_strategy: How to handle conflicts

        Returns:
            Number of macro sets imported
        """
        imported_count = 0

        for ms_data in macro_sets_data:
            # Create export wrapper
            export_wrapper = {
                "export_type": "macro_set",
                "version": EXPORT_VERSION,
                "data": ms_data,
            }

            result = await self.import_macro_set(
                export_wrapper,
                user_key,
                conflict_strategy
            )

            if result:
                imported_count += 1

        logger.info(f"Imported {imported_count} referenced macro sets")
        return imported_count

    async def import_from_file(
        self,
        file_path: str,
        user_key: str = "default",
        conflict_strategy: Literal["skip", "overwrite", "merge"] = "skip"
    ) -> Dict[str, Any]:
        """
        Import macro set(s) from a JSON file.

        Args:
            file_path: Path to JSON export file
            user_key: User identifier
            conflict_strategy: How to handle conflicts

        Returns:
            Import result with counts

        Raises:
            FileNotFoundError: If file doesn't exist
            json.JSONDecodeError: If file is not valid JSON
        """
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        export_type = data.get("export_type")

        if export_type == "macro_set":
            ms_result = await self.import_macro_set(data, user_key, conflict_strategy)
            return {
                "success": ms_result is not None,
                "imported": 1 if ms_result else 0,
                "skipped": 0 if ms_result else 1,
                "type": "macro_set",
            }
        elif export_type == "meta_topic":
            mt_result = await self.import_meta_topic(data, user_key, conflict_strategy)
            return {
                "success": mt_result is not None,
                "imported": 1 if mt_result else 0,
                "skipped": 0 if mt_result else 1,
                "type": "meta_topic",
            }
        elif export_type == "all_macro_sets":
            imported = 0
            skipped = 0

            for ms_data in data.get("data", []):
                export_wrapper = {
                    "export_type": "macro_set",
                    "version": EXPORT_VERSION,
                    "data": ms_data,
                }

                result = await self.import_macro_set(
                    export_wrapper,
                    user_key,
                    conflict_strategy
                )

                if result:
                    imported += 1
                else:
                    skipped += 1

            return {
                "success": True,
                "imported": imported,
                "skipped": skipped,
                "type": "all_macro_sets",
            }
        else:
            raise ValueError(f"Unknown export type: {export_type}")
