"""
Macros backup service.

Handles backup and restore operations for macro sets and meta topics.
Creates JSON backups to protect against data loss from accidents or software errors.

Meta topics are now stored in ``main DB`` (via ``MetaTopic``),
while macro sets remain in ``cogitate.db`` (via ``MacroSet``).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.infrastructure.database.models import MacroSet
from app.infrastructure.database.models import MetaTopic as MetaTopic
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

BACKUP_VERSION = "1.0"
BACKUP_FILENAME = "macro_backup.json"


class MacroBackupService:
    """Service for managing macro system backups."""

    def __init__(self, db: AsyncSession, backup_dir: Optional[Path] = None):
        self.db = db
        self.backup_dir = backup_dir or self._get_default_backup_dir()

    def _get_default_backup_dir(self) -> Path:
        """Get default backup directory path."""
        # Default to backend/data/backups/
        from app.core.config import Paths, get_settings
        backup_dir = Paths.from_settings(get_settings()).backups_dir
        backup_dir.mkdir(parents=True, exist_ok=True)
        return backup_dir

    def _get_backup_file_path(self) -> Path:
        """Get path to backup file."""
        return self.backup_dir / BACKUP_FILENAME

    async def create_backup(self) -> Dict[str, Any]:
        """
        Create a backup of all macro sets and meta topics.

        Macro sets are read from ``cogitate.db`` (via ``self.db``),
        meta topics are read from ``main DB`` (via ``AsyncSessionLocal``).

        Returns:
            Backup info dictionary with timestamp and file path

        Raises:
            IOError: If backup file cannot be written
        """
        logger.info("Creating macro backup...")

        # Fetch all macro sets from cogitate.db
        macro_sets_result = await self.db.execute(select(MacroSet).order_by(MacroSet.topic, MacroSet.name))
        macro_sets = macro_sets_result.scalars().all()

        # Fetch all meta topics from main DB
        async with AsyncSessionLocal() as meta_db:
            meta_topics_result = await meta_db.execute(
                select(MetaTopic).order_by(MetaTopic.name)
            )
            meta_topics = meta_topics_result.scalars().all()

        # Build backup data structure
        backup_data = {
            "backup_version": BACKUP_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "macro_sets_count": len(macro_sets),
            "meta_topics_count": len(meta_topics),
            "macro_sets": [
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
            "meta_topics": [
                {
                    "name": mt.name,
                    "description": mt.description,
                    "topic_mappings": mt.topic_mappings,
                    "is_active": mt.is_active,
                }
                for mt in meta_topics
            ],
        }

        # Write backup file
        backup_path = self._get_backup_file_path()
        try:
            with open(backup_path, "w", encoding="utf-8") as f:
                json.dump(backup_data, f, indent=2, ensure_ascii=False)

            logger.info(
                f"Backup created successfully: {backup_path} "
                f"({len(macro_sets)} macro sets, {len(meta_topics)} meta topics)"
            )

            return {
                "success": True,
                "backup_path": str(backup_path),
                "created_at": backup_data["created_at"],
                "macro_sets_count": len(macro_sets),
                "meta_topics_count": len(meta_topics),
                "file_size_bytes": backup_path.stat().st_size,
            }

        except IOError as e:
            logger.error(f"Failed to write backup file: {e}")
            raise

    async def restore_backup(self) -> Dict[str, Any]:
        """
        Restore macro sets and meta topics from backup.

        This will:
        1. Delete all existing macro sets and meta topics
        2. Recreate them from the backup file

        Macro sets are restored to ``cogitate.db`` (via ``self.db``),
        meta topics are restored to ``main DB`` (via ``AsyncSessionLocal``).

        Returns:
            Restore info dictionary with counts and status

        Raises:
            FileNotFoundError: If backup file doesn't exist
            json.JSONDecodeError: If backup file is corrupted
        """
        backup_path = self._get_backup_file_path()

        if not backup_path.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_path}")

        logger.info(f"Restoring from backup: {backup_path}")

        # Read backup file
        with open(backup_path, "r", encoding="utf-8") as f:
            backup_data = json.load(f)

        # Validate backup version
        backup_version = backup_data.get("backup_version")
        if backup_version != BACKUP_VERSION:
            logger.warning(f"Backup version mismatch: expected {BACKUP_VERSION}, got {backup_version}")

        # Delete existing macro sets from cogitate.db
        logger.info("Deleting existing macro sets...")
        from sqlalchemy import text
        await self.db.execute(text("DELETE FROM macro_sets"))
        await self.db.commit()

        # Delete existing meta topics from main DB
        logger.info("Deleting existing meta topics from main DB...")
        async with AsyncSessionLocal() as meta_db:
            await meta_db.execute(text("DELETE FROM meta_topics"))
            await meta_db.commit()

        # Restore macro sets to cogitate.db
        macro_sets_count = 0
        for ms_data in backup_data.get("macro_sets", []):
            macro_set = MacroSet(
                user_key="default",  # Default user until auth is implemented
                **ms_data,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            self.db.add(macro_set)
            macro_sets_count += 1

        await self.db.commit()

        # Restore meta topics to main DB
        meta_topics_count = 0
        async with AsyncSessionLocal() as meta_db:
            for mt_data in backup_data.get("meta_topics", []):
                meta_topic = MetaTopic(
                    name=mt_data["name"],
                    description=mt_data.get("description", ""),
                    topic_mappings=mt_data.get("topic_mappings", []),
                    is_active=mt_data.get("is_active", True),
                    namespace="agent",  # Restored meta topics are agent-scoped
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                meta_db.add(meta_topic)
                meta_topics_count += 1

            await meta_db.commit()

        logger.info(
            f"Restore completed successfully: "
            f"{macro_sets_count} macro sets, {meta_topics_count} meta topics"
        )

        return {
            "success": True,
            "macro_sets_restored": macro_sets_count,
            "meta_topics_restored": meta_topics_count,
            "backup_created_at": backup_data.get("created_at"),
        }

    async def get_backup_info(self) -> Optional[Dict[str, Any]]:
        """
        Get information about the latest backup.

        Returns:
            Backup info dictionary or None if no backup exists
        """
        backup_path = self._get_backup_file_path()

        if not backup_path.exists():
            return None

        try:
            with open(backup_path, "r", encoding="utf-8") as f:
                backup_data = json.load(f)

            return {
                "exists": True,
                "backup_path": str(backup_path),
                "created_at": backup_data.get("created_at"),
                "backup_version": backup_data.get("backup_version"),
                "macro_sets_count": backup_data.get("macro_sets_count", 0),
                "meta_topics_count": backup_data.get("meta_topics_count", 0),
                "file_size_bytes": backup_path.stat().st_size,
            }

        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error reading backup info: {e}")
            return {
                "exists": True,
                "backup_path": str(backup_path),
                "error": str(e),
            }

    async def delete_backup(self) -> bool:
        """
        Delete the backup file.

        Returns:
            True if deleted, False if file didn't exist
        """
        backup_path = self._get_backup_file_path()

        if not backup_path.exists():
            return False

        try:
            backup_path.unlink()
            logger.info(f"Backup deleted: {backup_path}")
            return True
        except IOError as e:
            logger.error(f"Failed to delete backup: {e}")
            raise
