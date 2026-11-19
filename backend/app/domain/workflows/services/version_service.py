"""
Workflow version service layer.

Provides business logic for:
- Managing workflow versions (create, update, delete)
- Version activation and deactivation
- Version comparison and analytics
- Database integration for version persistence

Features:
- Version CRUD operations
- Version activation/deactivation
- Version comparison with metrics
- Comprehensive logging for diagnostics
"""

import logging
import sqlite3
import json
import uuid
from typing import Dict, Any, Optional, List

from app.domain.workflows.schemas.version_config import (
    WorkflowVersion,
    VersionCreate,
    VersionUpdate,
    VersionComparisonResult,
)

logger = logging.getLogger(__name__)


# Database path — resolve from the app's canonical BASE_DIR so we always
# use the same cogitate.db as the SQLAlchemy engine, regardless of CWD.
from app.core.config import Paths, get_settings
from pathlib import Path
DB_PATH = Paths.from_settings(get_settings()).shared_db


class VersionService:
    """
    Service for managing workflow versions.

    This service handles:
    1. Creating workflow versions
    2. Updating version configurations
    3. Deleting versions
    4. Activating/deactivating versions
    5. Version comparison and analytics
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

    def _generate_id(self) -> str:
        """Generate unique version ID."""
        return f"version-{uuid.uuid4().hex[:12]}"

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    def create_version(
        self,
        template_id: str,
        config: VersionCreate
    ) -> WorkflowVersion:
        """
        Create a new workflow version.

        Args:
            template_id: ID of the workflow template
            config: Version configuration

        Returns:
            Created version configuration

        Raises:
            sqlite3.IntegrityError: If version already exists for template
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            version_id = self._generate_id()
            config_json = json.dumps(config.config)

            # Deactivate all existing versions for this template
            cursor.execute(
                """
                UPDATE workflow_versions
                SET is_active = 0
                WHERE template_id = ?
                """,
                (template_id,)
            )

            cursor.execute(
                """
                INSERT INTO workflow_versions (
                    id, template_id, version, config, changelog, is_active, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    version_id,
                    template_id,
                    config.version,
                    config_json,
                    config.changelog,
                    1,  # New versions are active by default
                    config.created_by,
                )
            )
            conn.commit()

            logger.info(f"✅ Created version {config.version} for template {template_id}")

            return WorkflowVersion(
                id=version_id,
                template_id=template_id,
                version=config.version,
                config=config.config,
                changelog=config.changelog,
                is_active=True,
                created_by=config.created_by,
            )

        except sqlite3.IntegrityError as e:
            logger.error(f"❌ Version {config.version} already exists for template {template_id}: {e}")
            raise
        finally:
            conn.close()

    def get_version(
        self,
        template_id: str,
        version: str
    ) -> Optional[WorkflowVersion]:
        """
        Get a specific version by template ID and version string.

        Args:
            template_id: ID of the workflow template
            version: Version string (e.g., 'v1.0')

        Returns:
            Version configuration or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT id, template_id, version, config, changelog, is_active,
                       created_by, created_at
                FROM workflow_versions
                WHERE template_id = ? AND version = ?
                """,
                (template_id, version)
            )
            row = cursor.fetchone()

            if not row:
                return None

            return WorkflowVersion(
                id=row["id"],
                template_id=row["template_id"],
                version=row["version"],
                config=json.loads(row["config"]),
                changelog=row["changelog"],
                is_active=bool(row["is_active"]),
                created_by=row["created_by"],
            )
        finally:
            conn.close()

    def get_version_by_id(self, version_id: str) -> Optional[WorkflowVersion]:
        """
        Get a version by its unique ID.

        Args:
            version_id: Unique version ID

        Returns:
            Version configuration or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT id, template_id, version, config, changelog, is_active,
                       created_by, created_at
                FROM workflow_versions
                WHERE id = ?
                """,
                (version_id,)
            )
            row = cursor.fetchone()

            if not row:
                return None

            return WorkflowVersion(
                id=row["id"],
                template_id=row["template_id"],
                version=row["version"],
                config=json.loads(row["config"]),
                changelog=row["changelog"],
                is_active=bool(row["is_active"]),
                created_by=row["created_by"],
            )
        finally:
            conn.close()

    def list_versions(
        self,
        template_id: str,
        active_only: bool = False
    ) -> List[WorkflowVersion]:
        """
        List all versions for a template.

        Args:
            template_id: ID of the workflow template
            active_only: Only return active versions

        Returns:
            List of version configurations
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            query = """
                SELECT id, template_id, version, config, changelog, is_active,
                       created_by, created_at
                FROM workflow_versions
                WHERE template_id = ?
            """
            params = [template_id]

            if active_only:
                query += " AND is_active = 1"

            query += " ORDER BY created_at DESC"

            cursor.execute(query, params)
            rows = cursor.fetchall()

            versions = []
            for row in rows:
                versions.append(WorkflowVersion(
                    id=row["id"],
                    template_id=row["template_id"],
                    version=row["version"],
                    config=json.loads(row["config"]),
                    changelog=row["changelog"],
                    is_active=bool(row["is_active"]),
                    created_by=row["created_by"],
                ))

            return versions
        finally:
            conn.close()

    def update_version(
        self,
        template_id: str,
        version: str,
        update: VersionUpdate
    ) -> Optional[WorkflowVersion]:
        """
        Update an existing version.

        Args:
            template_id: ID of the workflow template
            version: Version string to update
            update: Update configuration

        Returns:
            Updated version or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            updates = []
            params = []

            if update.config is not None:
                updates.append("config = ?")
                params.append(json.dumps(update.config))

            if update.changelog is not None:
                updates.append("changelog = ?")
                params.append(update.changelog)

            if update.is_active is not None:
                updates.append("is_active = ?")
                params.append(str(1 if update.is_active else 0))

            if not updates:
                return self.get_version(template_id, version)

            params.append(template_id)
            params.append(version)

            cursor.execute(
                f"""
                UPDATE workflow_versions
                SET {', '.join(updates)}
                WHERE template_id = ? AND version = ?
                """,
                params
            )
            conn.commit()

            if cursor.rowcount == 0:
                logger.warning(f"⚠️ Version {version} not found for template {template_id}")
                return None

            logger.info(f"✅ Updated version {version} for template {template_id}")
            return self.get_version(template_id, version)

        finally:
            conn.close()

    def delete_version(
        self,
        template_id: str,
        version: str
    ) -> bool:
        """
        Delete a version.

        Args:
            template_id: ID of the workflow template
            version: Version string to delete

        Returns:
            True if deleted, False if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "DELETE FROM workflow_versions WHERE template_id = ? AND version = ?",
                (template_id, version)
            )
            conn.commit()

            deleted = cursor.rowcount > 0

            if deleted:
                logger.info(f"✅ Deleted version {version} for template {template_id}")
            else:
                logger.warning(f"⚠️ Version {version} not found for template {template_id}")

            return deleted
        finally:
            conn.close()

    # =========================================================================
    # Version Activation
    # =========================================================================

    def activate_version(
        self,
        template_id: str,
        version: str
    ) -> bool:
        """
        Activate a specific version (deactivates all others).

        Args:
            template_id: ID of the workflow template
            version: Version string to activate

        Returns:
            True if activated, False if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # First check if version exists
            cursor.execute(
                "SELECT id FROM workflow_versions WHERE template_id = ? AND version = ?",
                (template_id, version)
            )
            if not cursor.fetchone():
                logger.warning(f"⚠️ Version {version} not found for template {template_id}")
                return False

            # Deactivate all versions
            cursor.execute(
                """
                UPDATE workflow_versions
                SET is_active = 0
                WHERE template_id = ?
                """,
                (template_id,)
            )

            # Activate the specified version
            cursor.execute(
                """
                UPDATE workflow_versions
                SET is_active = 1
                WHERE template_id = ? AND version = ?
                """,
                (template_id, version)
            )
            conn.commit()

            logger.info(f"✅ Activated version {version} for template {template_id}")
            return True

        finally:
            conn.close()

    def deactivate_version(
        self,
        template_id: str,
        version: str
    ) -> bool:
        """
        Deactivate a specific version.

        Args:
            template_id: ID of the workflow template
            version: Version string to deactivate

        Returns:
            True if deactivated, False if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                UPDATE workflow_versions
                SET is_active = 0
                WHERE template_id = ? AND version = ?
                """,
                (template_id, version)
            )
            conn.commit()

            deactivated = cursor.rowcount > 0

            if deactivated:
                logger.info(f"✅ Deactivated version {version} for template {template_id}")
            else:
                logger.warning(f"⚠️ Version {version} not found for template {template_id}")

            return deactivated

        finally:
            conn.close()

    def get_active_version(self, template_id: str) -> Optional[WorkflowVersion]:
        """
        Get the currently active version for a template.

        Args:
            template_id: ID of the workflow template

        Returns:
            Active version or None if no active version
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT id, template_id, version, config, changelog, is_active,
                       created_by, created_at
                FROM workflow_versions
                WHERE template_id = ? AND is_active = 1
                """,
                (template_id,)
            )
            row = cursor.fetchone()

            if not row:
                return None

            return WorkflowVersion(
                id=row["id"],
                template_id=row["template_id"],
                version=row["version"],
                config=json.loads(row["config"]),
                changelog=row["changelog"],
                is_active=True,
                created_by=row["created_by"],
            )
        finally:
            conn.close()

    # =========================================================================
    # Version Comparison
    # =========================================================================

    def compare_versions(
        self,
        template_id: str,
        v1: str,
        v2: str
    ) -> Optional[VersionComparisonResult]:
        """
        Compare two versions based on their configurations and A/B test results.

        Args:
            template_id: ID of the workflow template
            v1: First version string
            v2: Second version string

        Returns:
            Comparison result or None if versions not found
        """
        version1 = self.get_version(template_id, v1)
        version2 = self.get_version(template_id, v2)

        if not version1 or not version2:
            logger.warning(f"⚠️ Cannot compare: versions {v1} or {v2} not found for {template_id}")
            return None

        # Get A/B test results for these versions
        v1_metrics = self._get_version_metrics(template_id, v1)
        v2_metrics = self._get_version_metrics(template_id, v2)

        # Determine recommendation based on metrics
        recommendation = self._determine_recommendation(v1_metrics, v2_metrics, v1, v2)

        logger.info(f"✅ Compared versions {v1} vs {v2} for template {template_id}")

        return VersionComparisonResult(
            template_id=template_id,
            v1={
                "version": v1,
                "avg_execution_time_ms": v1_metrics.get("avg_execution_time_ms", 0),
                "avg_tokens_used": v1_metrics.get("avg_tokens_used", 0),
                "success_rate": v1_metrics.get("success_rate", 0.0),
                "total_executions": v1_metrics.get("total_executions", 0),
            },
            v2={
                "version": v2,
                "avg_execution_time_ms": v2_metrics.get("avg_execution_time_ms", 0),
                "avg_tokens_used": v2_metrics.get("avg_tokens_used", 0),
                "success_rate": v2_metrics.get("success_rate", 0.0),
                "total_executions": v2_metrics.get("total_executions", 0),
            },
            recommendation=recommendation,
        )

    def _get_version_metrics(
        self,
        template_id: str,
        version: str
    ) -> Dict[str, Any]:
        """
        Get aggregated metrics for a version from A/B test results.

        Args:
            template_id: ID of the workflow template
            version: Version string

        Returns:
            Dictionary of aggregated metrics
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT
                    COUNT(*) as total_executions,
                    AVG(execution_time_ms) as avg_execution_time_ms,
                    AVG(tokens_used) as avg_tokens_used,
                    AVG(CASE WHEN success = 1 THEN 1.0 ELSE 0.0 END) as success_rate
                FROM ab_test_results
                WHERE template_id = ? AND version = ?
                """,
                (template_id, version)
            )
            row = cursor.fetchone()

            if not row or row["total_executions"] == 0:
                return {
                    "total_executions": 0,
                    "avg_execution_time_ms": 0,
                    "avg_tokens_used": 0,
                    "success_rate": 0.0,
                }

            return {
                "total_executions": row["total_executions"] or 0,
                "avg_execution_time_ms": round(row["avg_execution_time_ms"] or 0, 2),
                "avg_tokens_used": round(row["avg_tokens_used"] or 0, 2),
                "success_rate": round(row["success_rate"] or 0.0, 4),
            }
        finally:
            conn.close()

    def _determine_recommendation(
        self,
        v1_metrics: Dict[str, Any],
        v2_metrics: Dict[str, Any],
        v1: str,
        v2: str
    ) -> Optional[str]:
        """
        Determine which version to recommend based on metrics.

        Args:
            v1_metrics: Metrics for version 1
            v2_metrics: Metrics for version 2
            v1: Version 1 string
            v2: Version 2 string

        Returns:
            Recommended version string or None if inconclusive
        """
        # If no data, return None
        if v1_metrics["total_executions"] == 0 and v2_metrics["total_executions"] == 0:
            return None

        # If only one has data, recommend that one
        if v1_metrics["total_executions"] == 0:
            return v2
        if v2_metrics["total_executions"] == 0:
            return v1

        # Score based on: faster execution, fewer tokens, higher success rate
        v1_score = 0
        v2_score = 0

        # Execution time (lower is better)
        if v1_metrics["avg_execution_time_ms"] < v2_metrics["avg_execution_time_ms"]:
            v1_score += 1
        else:
            v2_score += 1

        # Token usage (lower is better)
        if v1_metrics["avg_tokens_used"] < v2_metrics["avg_tokens_used"]:
            v1_score += 1
        else:
            v2_score += 1

        # Success rate (higher is better)
        if v1_metrics["success_rate"] > v2_metrics["success_rate"]:
            v1_score += 1
        else:
            v2_score += 1

        if v1_score > v2_score:
            return v1
        elif v2_score > v1_score:
            return v2
        else:
            # Tie - prefer higher success rate
            if v1_metrics["success_rate"] >= v2_metrics["success_rate"]:
                return v1
            return v2
