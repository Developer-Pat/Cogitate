"""
Workflow trigger service layer.

Provides business logic for:
- Managing workflow triggers (webhook, schedule, database)
- Creating, updating, and deleting triggers
- Querying active triggers
- Trigger execution tracking

Features:
- Trigger CRUD operations
- Trigger activation/deactivation
- Trigger type validation
- Comprehensive logging for diagnostics
"""

import logging
import sqlite3
import json
from typing import Optional, List
from datetime import datetime, UTC
from urllib.parse import urlparse
from pathlib import Path

from app.core.config import get_settings
from app.domain.workflows.schemas.trigger_config import (
    WorkflowTrigger,
    WorkflowTriggerCreate,
    WorkflowTriggerUpdate,
)

logger = logging.getLogger(__name__)


# Resolve database path from the application's settings so that the
# TriggerService always connects to the same ``cogitate.db`` as the
# rest of the application (SQLAlchemy engine).  Previously this was a
# hardcoded relative path that resolved to ``backend/cogitate.db``,
# which lacked the ``workflow_triggers`` table.
_settings = get_settings()
_parsed = urlparse(_settings.database_url)
DB_PATH = _parsed.path  # e.g. <install-root>/cogitate.db


class TriggerService:
    """
    Service for managing workflow triggers.

    This service handles:
    1. Creating workflow triggers
    2. Updating trigger configurations
    3. Deleting triggers
    4. Querying active triggers
    5. Trigger execution tracking
    """

    @property
    def db_path(self) -> Path:
        """The shared database, resolved on EVERY read.

        This was a module-level constant captured at import. That cannot follow
        a redirected installation: under test the harness points DATABASE_URL at
        a copy of a migrated DB, and a path bound at import (or in __init__)
        keeps naming the original — producing "no such table" against the wrong
        file. The resolver was always correct; it was just applied too early.
        """
        from app.core.config import Paths, get_settings

        override: Path | None = getattr(self, "_db_path_override", None)
        if override is not None:
            return override
        return Paths.from_settings(get_settings()).shared_db

    @db_path.setter
    def db_path(self, value) -> None:
        """An explicit override — the test seam.

        Kept deliberately: tests point a service at their own database.
        The resolver above is the DEFAULT, not a cage.
        """
        self._db_path_override = value

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    def create_trigger(self, config: WorkflowTriggerCreate) -> WorkflowTrigger:
        """
        Create a new workflow trigger.

        Args:
            config: Workflow trigger configuration

        Returns:
            Created trigger configuration

        Raises:
            sqlite3.IntegrityError: If trigger ID already exists
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Serialize config to JSON
            config_json = json.dumps(config.config)

            cursor.execute(
                """
                INSERT INTO workflow_triggers (
                    id, workflow_id, trigger_type, config, is_active, name, description
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    config.id,
                    config.workflow_id,
                    config.trigger_type,
                    config_json,
                    1 if config.is_active else 0,
                    config.name,
                    config.description,
                )
            )
            conn.commit()

            logger.info(f"✅ Created trigger: {config.id} ({config.trigger_type}) for workflow {config.workflow_id}")

            return WorkflowTrigger(
                id=config.id,
                workflow_id=config.workflow_id,
                trigger_type=config.trigger_type,
                config=config.config,
                is_active=config.is_active,
                name=config.name,
                description=config.description,
            )

        except sqlite3.IntegrityError as e:
            logger.error(f"❌ Trigger {config.id} already exists: {e}")
            raise
        finally:
            conn.close()

    def get_trigger(self, trigger_id: str) -> Optional[WorkflowTrigger]:
        """
        Get a trigger by ID.

        Args:
            trigger_id: Trigger ID

        Returns:
            Trigger configuration or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT id, workflow_id, trigger_type, config, is_active, name, description,
                       created_at, updated_at
                FROM workflow_triggers
                WHERE id = ?
                """,
                (trigger_id,)
            )
            row = cursor.fetchone()

            if not row:
                return None

            return WorkflowTrigger(
                id=row["id"],
                workflow_id=row["workflow_id"],
                trigger_type=row["trigger_type"],
                config=json.loads(row["config"]),
                is_active=bool(row["is_active"]),
                name=row["name"],
                description=row["description"] or "",
            )
        finally:
            conn.close()

    def get_all_triggers(
        self,
        include_inactive: bool = False,
        trigger_type: Optional[str] = None,
        workflow_id: Optional[str] = None
    ) -> List[WorkflowTrigger]:
        """
        Get all triggers with optional filtering.

        Args:
            include_inactive: Include inactive triggers
            trigger_type: Filter by trigger type
            workflow_id: Filter by workflow ID

        Returns:
            List of trigger configurations
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            query = "SELECT id, workflow_id, trigger_type, config, is_active, name, description FROM workflow_triggers WHERE 1=1"
            params = []

            if not include_inactive:
                query += " AND is_active = 1"

            if trigger_type:
                query += " AND trigger_type = ?"
                params.append(trigger_type)

            if workflow_id:
                query += " AND workflow_id = ?"
                params.append(workflow_id)

            query += " ORDER BY created_at DESC"

            cursor.execute(query, params)
            rows = cursor.fetchall()

            triggers = []
            for row in rows:
                triggers.append(WorkflowTrigger(
                    id=row["id"],
                    workflow_id=row["workflow_id"],
                    trigger_type=row["trigger_type"],
                    config=json.loads(row["config"]),
                    is_active=bool(row["is_active"]),
                    name=row["name"],
                    description=row["description"] or "",
                ))

            return triggers
        finally:
            conn.close()

    def update_trigger(
        self,
        trigger_id: str,
        update: WorkflowTriggerUpdate
    ) -> Optional[WorkflowTrigger]:
        """
        Update a trigger.

        Args:
            trigger_id: Trigger ID to update
            update: Update configuration

        Returns:
            Updated trigger configuration or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Build dynamic update query
            updates = []
            params = []

            if update.workflow_id is not None:
                updates.append("workflow_id = ?")
                params.append(update.workflow_id)

            if update.trigger_type is not None:
                updates.append("trigger_type = ?")
                params.append(update.trigger_type)

            if update.config is not None:
                updates.append("config = ?")
                params.append(json.dumps(update.config))

            if update.is_active is not None:
                updates.append("is_active = ?")
                params.append(str(1 if update.is_active else 0))

            if update.name is not None:
                updates.append("name = ?")
                params.append(update.name)

            if update.description is not None:
                updates.append("description = ?")
                params.append(update.description)

            if not updates:
                # No updates, just return current state
                return self.get_trigger(trigger_id)

            updates.append("updated_at = ?")
            params.append(datetime.now(UTC).isoformat())
            params.append(trigger_id)

            cursor.execute(
                f"""
                UPDATE workflow_triggers
                SET {', '.join(updates)}
                WHERE id = ?
                """,
                params
            )
            conn.commit()

            if cursor.rowcount == 0:
                logger.warning(f"⚠️ Trigger {trigger_id} not found for update")
                return None

            logger.info(f"✅ Updated trigger: {trigger_id}")
            return self.get_trigger(trigger_id)

        finally:
            conn.close()

    def delete_trigger(self, trigger_id: str) -> bool:
        """
        Delete a trigger.

        Args:
            trigger_id: Trigger ID to delete

        Returns:
            True if deleted, False if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "DELETE FROM workflow_triggers WHERE id = ?",
                (trigger_id,)
            )
            conn.commit()

            deleted = cursor.rowcount > 0

            if deleted:
                logger.info(f"✅ Deleted trigger: {trigger_id}")
            else:
                logger.warning(f"⚠️ Trigger {trigger_id} not found for deletion")

            return deleted
        finally:
            conn.close()

    def activate_trigger(self, trigger_id: str) -> bool:
        """
        Activate a trigger.

        Args:
            trigger_id: Trigger ID to activate

        Returns:
            True if activated, False if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                UPDATE workflow_triggers
                SET is_active = 1, updated_at = ?
                WHERE id = ?
                """,
                (datetime.now(UTC).isoformat(), trigger_id)
            )
            conn.commit()

            activated = cursor.rowcount > 0

            if activated:
                logger.info(f"✅ Activated trigger: {trigger_id}")
            else:
                logger.warning(f"⚠️ Trigger {trigger_id} not found for activation")

            return activated
        finally:
            conn.close()

    def deactivate_trigger(self, trigger_id: str) -> bool:
        """
        Deactivate a trigger.

        Args:
            trigger_id: Trigger ID to deactivate

        Returns:
            True if deactivated, False if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                UPDATE workflow_triggers
                SET is_active = 0, updated_at = ?
                WHERE id = ?
                """,
                (datetime.now(UTC).isoformat(), trigger_id)
            )
            conn.commit()

            deactivated = cursor.rowcount > 0

            if deactivated:
                logger.info(f"✅ Deactivated trigger: {trigger_id}")
            else:
                logger.warning(f"⚠️ Trigger {trigger_id} not found for deactivation")

            return deactivated
        finally:
            conn.close()

    def get_active_triggers_by_type(
        self,
        trigger_type: str
    ) -> List[WorkflowTrigger]:
        """
        Get all active triggers of a specific type.

        Args:
            trigger_type: Type of triggers to get

        Returns:
            List of active trigger configurations
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT id, workflow_id, trigger_type, config, is_active, name, description
                FROM workflow_triggers
                WHERE trigger_type = ? AND is_active = 1
                ORDER BY created_at DESC
                """,
                (trigger_type,)
            )
            rows = cursor.fetchall()

            triggers = []
            for row in rows:
                triggers.append(WorkflowTrigger(
                    id=row["id"],
                    workflow_id=row["workflow_id"],
                    trigger_type=row["trigger_type"],
                    config=json.loads(row["config"]),
                    is_active=bool(row["is_active"]),
                    name=row["name"],
                    description=row["description"] or "",
                ))

            return triggers
        finally:
            conn.close()

    def get_active_triggers_by_workflow(
        self,
        workflow_id: str
    ) -> List[WorkflowTrigger]:
        """
        Get all active triggers for a specific workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            List of active trigger configurations
        """
        return self.get_all_triggers(
            include_inactive=False,
            workflow_id=workflow_id
        )
