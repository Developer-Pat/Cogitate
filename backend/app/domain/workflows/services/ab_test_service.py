"""
A/B test service layer.

Provides business logic for:
- Managing A/B test configurations
- Recording test results
- Traffic splitting for version assignment
- Statistical comparison of versions
- Test lifecycle management (start, pause, stop)

Features:
- A/B test CRUD operations
- Traffic splitting with weighted random assignment
- Result recording and aggregation
- Statistical comparison
- Comprehensive logging for diagnostics
"""

import logging
import sqlite3
import json
import uuid
import random
from typing import Any, Dict, Optional, List
from datetime import datetime, UTC

from app.domain.workflows.schemas.version_config import (
    ABTestConfig,
    ABTestCreate,
    ABTestUpdate,
    ABTestResult,
    ABTestResultRecord,
    ABTestResultsSummary,
    ABTestComparison,
)

logger = logging.getLogger(__name__)


# Database path — resolved through `Paths` so it always names the same
# database the SQLAlchemy engine uses, regardless of CWD.
#
# Resolved at USE time, not at import time, and that is the point: a path bound
# when the module loads cannot follow a redirected installation. The engine has
# the same hazard — it is built at import from `settings.database_url`, which is
# why the test harness must set that before importing anything.
def _db_path() -> str:
    """The shared database this installation is using, right now."""
    from app.core.config import Paths, get_settings

    return str(Paths.from_settings(get_settings()).shared_db)


class ABTestService:
    """
    Service for managing A/B tests.

    This service handles:
    1. Creating A/B tests
    2. Recording test results
    3. Traffic splitting for version assignment
    4. Test lifecycle management
    5. Statistical comparison of versions
    """

    def __init__(self):
        """Initialize A/B test service.

        Deliberately holds NO path. This class is instantiated once at module
        level in `ab_tests_router.py`, so `__init__` runs at IMPORT — the exact
        thing the comment above `_db_path` warns against. Capturing it here bound
        the path before a redirected installation existed, and the service then
        opened a database without the `ab_test_configs` table.
        """

    @property
    def db_path(self) -> str:
        """The shared database, resolved on every read — never cached."""
        return _db_path()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _generate_id(self) -> str:
        """Generate unique A/B test ID."""
        return f"ab-test-{uuid.uuid4().hex[:12]}"

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    def create_test(self, config: ABTestCreate) -> ABTestConfig:
        """
        Create a new A/B test.

        Args:
            config: A/B test configuration

        Returns:
            Created test configuration

        Raises:
            sqlite3.IntegrityError: If test ID already exists
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            versions_json = json.dumps(config.versions)
            traffic_split_json = json.dumps(config.traffic_split)
            metrics_json = json.dumps(config.metrics) if config.metrics else None

            cursor.execute(
                """
                INSERT INTO ab_test_configs (
                    id, template_id, name, description, versions,
                    traffic_split, metrics, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    config.id,
                    config.template_id,
                    config.name,
                    config.description,
                    versions_json,
                    traffic_split_json,
                    metrics_json,
                    1 if config.is_active else 0,
                )
            )
            conn.commit()

            logger.info(f"✅ Created A/B test: {config.id} for template {config.template_id}")

            return ABTestConfig(
                id=config.id,
                template_id=config.template_id,
                name=config.name,
                description=config.description,
                versions=config.versions,
                traffic_split=config.traffic_split,
                metrics=config.metrics,
                is_active=config.is_active,
            )

        except sqlite3.IntegrityError as e:
            logger.error(f"❌ A/B test {config.id} already exists: {e}")
            raise
        finally:
            conn.close()

    def get_test(self, test_id: str) -> Optional[ABTestConfig]:
        """
        Get an A/B test by ID.

        Args:
            test_id: A/B test ID

        Returns:
            Test configuration or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT id, template_id, name, description, versions,
                       traffic_split, metrics, is_active, started_at, ended_at, created_at
                FROM ab_test_configs
                WHERE id = ?
                """,
                (test_id,)
            )
            row = cursor.fetchone()

            if not row:
                return None

            return ABTestConfig(
                id=row["id"],
                template_id=row["template_id"],
                name=row["name"],
                description=row["description"],
                versions=json.loads(row["versions"]),
                traffic_split=json.loads(row["traffic_split"]),
                metrics=json.loads(row["metrics"]) if row["metrics"] else None,
                is_active=bool(row["is_active"]),
            )
        finally:
            conn.close()

    def list_tests(
        self,
        active_only: bool = False
    ) -> List[ABTestConfig]:
        """
        List all A/B tests.

        Args:
            active_only: Only return active tests

        Returns:
            List of test configurations
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            query = """
                SELECT id, template_id, name, description, versions,
                       traffic_split, metrics, is_active, started_at, ended_at, created_at
                FROM ab_test_configs
                WHERE 1=1
            """
            params: list[Any] = []

            if active_only:
                query += " AND is_active = 1"

            query += " ORDER BY created_at DESC"

            cursor.execute(query, params)
            rows = cursor.fetchall()

            tests = []
            for row in rows:
                tests.append(ABTestConfig(
                    id=row["id"],
                    template_id=row["template_id"],
                    name=row["name"],
                    description=row["description"],
                    versions=json.loads(row["versions"]),
                    traffic_split=json.loads(row["traffic_split"]),
                    metrics=json.loads(row["metrics"]) if row["metrics"] else None,
                    is_active=bool(row["is_active"]),
                ))

            return tests
        finally:
            conn.close()

    def update_test(
        self,
        test_id: str,
        update: ABTestUpdate
    ) -> Optional[ABTestConfig]:
        """
        Update an A/B test.

        Args:
            test_id: A/B test ID
            update: Update configuration

        Returns:
            Updated test or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            updates = []
            params = []

            if update.name is not None:
                updates.append("name = ?")
                params.append(update.name)

            if update.description is not None:
                updates.append("description = ?")
                params.append(update.description)

            if update.traffic_split is not None:
                updates.append("traffic_split = ?")
                params.append(json.dumps(update.traffic_split))

            if update.metrics is not None:
                updates.append("metrics = ?")
                params.append(json.dumps(update.metrics))

            if update.is_active is not None:
                updates.append("is_active = ?")
                params.append(str(1 if update.is_active else 0))

            if not updates:
                return self.get_test(test_id)

            params.append(test_id)

            cursor.execute(
                f"""
                UPDATE ab_test_configs
                SET {', '.join(updates)}
                WHERE id = ?
                """,
                params
            )
            conn.commit()

            if cursor.rowcount == 0:
                logger.warning(f"⚠️ A/B test {test_id} not found for update")
                return None

            logger.info(f"✅ Updated A/B test: {test_id}")
            return self.get_test(test_id)

        finally:
            conn.close()

    def delete_test(self, test_id: str) -> bool:
        """
        Delete an A/B test.

        Args:
            test_id: A/B test ID

        Returns:
            True if deleted, False if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "DELETE FROM ab_test_configs WHERE id = ?",
                (test_id,)
            )
            conn.commit()

            deleted = cursor.rowcount > 0

            if deleted:
                logger.info(f"✅ Deleted A/B test: {test_id}")
            else:
                logger.warning(f"⚠️ A/B test {test_id} not found for deletion")

            return deleted
        finally:
            conn.close()

    # =========================================================================
    # Test Lifecycle Management
    # =========================================================================

    def start_test(self, test_id: str) -> bool:
        """
        Start an A/B test.

        Args:
            test_id: A/B test ID

        Returns:
            True if started, False if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                UPDATE ab_test_configs
                SET is_active = 1, started_at = ?, ended_at = NULL
                WHERE id = ?
                """,
                (datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"), test_id)
            )
            conn.commit()

            started = cursor.rowcount > 0

            if started:
                logger.info(f"✅ Started A/B test: {test_id}")
            else:
                logger.warning(f"⚠️ A/B test {test_id} not found for start")

            return started
        finally:
            conn.close()

    def pause_test(self, test_id: str) -> bool:
        """
        Pause an A/B test (keeps data, stops new assignments).

        Args:
            test_id: A/B test ID

        Returns:
            True if paused, False if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                UPDATE ab_test_configs
                SET is_active = 0
                WHERE id = ? AND ended_at IS NULL
                """,
                (test_id,)
            )
            conn.commit()

            paused = cursor.rowcount > 0

            if paused:
                logger.info(f"✅ Paused A/B test: {test_id}")
            else:
                logger.warning(f"⚠️ A/B test {test_id} not found or already ended")

            return paused
        finally:
            conn.close()

    def stop_test(self, test_id: str) -> bool:
        """
        Stop an A/B test (final, marks as ended).

        Args:
            test_id: A/B test ID

        Returns:
            True if stopped, False if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                UPDATE ab_test_configs
                SET is_active = 0, ended_at = ?
                WHERE id = ?
                """,
                (datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"), test_id)
            )
            conn.commit()

            stopped = cursor.rowcount > 0

            if stopped:
                logger.info(f"✅ Stopped A/B test: {test_id}")
            else:
                logger.warning(f"⚠️ A/B test {test_id} not found for stop")

            return stopped
        finally:
            conn.close()

    # =========================================================================
    # Traffic Splitting
    # =========================================================================

    def assign_version(self, test_id: str) -> Optional[str]:
        """
        Assign a version based on traffic split configuration.

        Uses weighted random selection based on traffic_split percentages.

        Args:
            test_id: A/B test ID

        Returns:
            Assigned version string or None if test not found/inactive
        """
        test = self.get_test(test_id)

        if not test:
            logger.warning(f"⚠️ A/B test {test_id} not found for version assignment")
            return None

        if not test.is_active:
            logger.warning(f"⚠️ A/B test {test_id} is not active")
            return None

        # Weighted random selection
        versions = list(test.traffic_split.keys())
        weights = [test.traffic_split[v] for v in versions]

        assigned = random.choices(versions, weights=weights, k=1)[0]

        logger.info(f"✅ Assigned version {assigned} for A/B test {test_id}")
        return assigned

    # =========================================================================
    # Result Recording
    # =========================================================================

    def record_result(
        self,
        test_id: str,
        result: ABTestResultRecord
    ) -> ABTestResult:
        """
        Record an A/B test execution result.

        Args:
            test_id: A/B test ID
            result: Result data to record

        Returns:
            Recorded result

        Raises:
            ValueError: If test not found
        """
        test = self.get_test(test_id)
        if not test:
            raise ValueError(f"A/B test {test_id} not found")

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            result_id = self._generate_id()

            # Phase C: enrich from the execution identity record when the
            # caller didn't supply timing — the record has real elapsed.
            execution_time_ms = result.execution_time_ms
            if execution_time_ms is None and result.execution_id:
                try:
                    row = cursor.execute(
                        "SELECT elapsed_seconds FROM workflow_execution_history WHERE id = ?",
                        (result.execution_id,),
                    ).fetchone()
                    if row and row["elapsed_seconds"] is not None:
                        execution_time_ms = int(row["elapsed_seconds"] * 1000)
                except Exception:
                    pass  # table may not exist in old environments; enrichment is best-effort

            cursor.execute(
                """
                INSERT INTO ab_test_results (
                    id, ab_test_id, template_id, version, execution_id,
                    execution_time_ms, tokens_used, quality_score, success, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result_id,
                    test_id,
                    test.template_id,
                    result.version,
                    result.execution_id,
                    execution_time_ms,
                    result.tokens_used,
                    result.quality_score,
                    1 if result.success else 0 if result.success is False else None,
                    result.error_message,
                )
            )
            conn.commit()

            logger.info(f"✅ Recorded result for A/B test {test_id}, version {result.version}")

            return ABTestResult(
                ab_test_id=test_id,
                template_id=test.template_id,
                version=result.version,
                execution_id=result.execution_id,
                execution_time_ms=result.execution_time_ms,
                tokens_used=result.tokens_used,
                quality_score=result.quality_score,
                success=result.success,
                error_message=result.error_message,
            )

        finally:
            conn.close()

    def get_results(
        self,
        test_id: str
    ) -> ABTestResultsSummary:
        """
        Get aggregated results for an A/B test.

        Args:
            test_id: A/B test ID

        Returns:
            Aggregated results summary

        Raises:
            ValueError: If test not found
        """
        test = self.get_test(test_id)
        if not test:
            raise ValueError(f"A/B test {test_id} not found")

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            version_results = {}
            total_executions = 0

            for version in test.versions:
                cursor.execute(
                    """
                    SELECT
                        COUNT(*) as total_executions,
                        AVG(execution_time_ms) as avg_execution_time_ms,
                        AVG(tokens_used) as avg_tokens_used,
                        AVG(CASE WHEN success = 1 THEN 1.0 ELSE 0.0 END) as success_rate
                    FROM ab_test_results
                    WHERE ab_test_id = ? AND version = ?
                    """,
                    (test_id, version)
                )
                row = cursor.fetchone()

                if row and row["total_executions"] > 0:
                    version_results[version] = {
                        "avg_execution_time_ms": round(row["avg_execution_time_ms"] or 0, 2),
                        "avg_tokens_used": round(row["avg_tokens_used"] or 0, 2),
                        "success_rate": round(row["success_rate"] or 0.0, 4),
                        "total_executions": row["total_executions"],
                    }
                    total_executions += row["total_executions"]
                else:
                    version_results[version] = {
                        "avg_execution_time_ms": 0,
                        "avg_tokens_used": 0,
                        "success_rate": 0.0,
                        "total_executions": 0,
                    }

            # Determine recommendation
            recommendation = self._determine_winner(version_results)

            return ABTestResultsSummary(
                ab_test_id=test_id,
                version_results=version_results,
                total_executions=total_executions,
                recommendation=recommendation,
            )

        finally:
            conn.close()

    def get_raw_results(
        self,
        test_id: str,
        limit: int = 100
    ) -> List[ABTestResult]:
        """
        Get raw (non-aggregated) results for an A/B test.

        Args:
            test_id: A/B test ID
            limit: Maximum number of results to return

        Returns:
            List of individual results
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT r.ab_test_id, r.template_id, r.version, r.execution_id,
                       r.execution_time_ms, r.tokens_used, r.quality_score, r.success,
                       r.error_message, r.created_at,
                       e.status AS execution_status,
                       json_extract(e.metadata, '$.agent_id') AS execution_agent_id,
                       e.started_at AS execution_started_at
                FROM ab_test_results r
                LEFT JOIN workflow_execution_history e
                       ON e.id = r.execution_id
                WHERE r.ab_test_id = ?
                ORDER BY r.created_at DESC
                LIMIT ?
                """,
                (test_id, limit)
            )
            rows = cursor.fetchall()

            results = []
            for row in rows:
                results.append(ABTestResult(
                    ab_test_id=row["ab_test_id"],
                    template_id=row["template_id"],
                    version=row["version"],
                    execution_id=row["execution_id"],
                    execution_time_ms=row["execution_time_ms"],
                    tokens_used=row["tokens_used"],
                    quality_score=row["quality_score"],
                    success=bool(row["success"]) if row["success"] is not None else None,
                    error_message=row["error_message"],
                    execution_status=row["execution_status"],
                    execution_agent_id=row["execution_agent_id"],
                    execution_started_at=row["execution_started_at"],
                ))

            return results
        finally:
            conn.close()

    def _determine_winner(
        self,
        version_results: Dict[str, Dict[str, Any]]
    ) -> Optional[str]:
        """
        Determine the winning version based on metrics.

        Args:
            version_results: Metrics aggregated by version

        Returns:
            Winning version or None if inconclusive
        """
        # Filter versions with data
        versions_with_data = {
            v: m for v, m in version_results.items()
            if m["total_executions"] > 0
        }

        if len(versions_with_data) < 2:
            return None

        # Score based on: faster execution, fewer tokens, higher success rate
        scores = {v: 0 for v in versions_with_data.keys()}
        versions = list(versions_with_data.keys())

        # Execution time (lower is better)
        min_time = min(versions_with_data[v]["avg_execution_time_ms"] for v in versions)
        for v in versions:
            if versions_with_data[v]["avg_execution_time_ms"] == min_time:
                scores[v] += 1

        # Token usage (lower is better)
        min_tokens = min(versions_with_data[v]["avg_tokens_used"] for v in versions)
        for v in versions:
            if versions_with_data[v]["avg_tokens_used"] == min_tokens:
                scores[v] += 1

        # Success rate (higher is better)
        max_rate = max(versions_with_data[v]["success_rate"] for v in versions)
        for v in versions:
            if versions_with_data[v]["success_rate"] == max_rate:
                scores[v] += 1

        # Return version with highest score
        winner = max(scores.keys(), key=lambda v: scores[v])
        logger.info(f"✅ Determined winner: {winner} for A/B test")
        return winner

    # =========================================================================
    # Version Comparison
    # =========================================================================

    def compare_versions(
        self,
        test_id: str
    ) -> Optional[ABTestComparison]:
        """
        Compare all versions in an A/B test.

        Args:
            test_id: A/B test ID

        Returns:
            Comparison result or None if test not found
        """
        test = self.get_test(test_id)
        if not test:
            return None

        results = self.get_results(test_id)

        if not results.version_results:
            return None

        # Build comparison
        comparison = {}
        baseline = None

        for version, metrics in results.version_results.items():
            if baseline is None:
                baseline = version
                comparison[version] = {
                    "avg_execution_time_ms": metrics["avg_execution_time_ms"],
                    "improvement": "baseline"
                }
            else:
                baseline_metrics = results.version_results[baseline]
                if baseline_metrics["avg_execution_time_ms"] > 0:
                    improvement = (
                        (metrics["avg_execution_time_ms"] - baseline_metrics["avg_execution_time_ms"])
                        / baseline_metrics["avg_execution_time_ms"] * 100
                    )
                    comparison[version] = {
                        "avg_execution_time_ms": metrics["avg_execution_time_ms"],
                        "improvement": f"{improvement:+.1f}% time"
                    }
                else:
                    comparison[version] = {
                        "avg_execution_time_ms": metrics["avg_execution_time_ms"],
                        "improvement": "no baseline data"
                    }

        return ABTestComparison.model_construct(
            ab_test_id=test_id,
            name=test.name,
            versions=test.versions,
            comparison=comparison,
            recommendation=results.recommendation,
        )
