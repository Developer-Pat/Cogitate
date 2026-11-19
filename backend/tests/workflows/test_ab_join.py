"""
The A/B result join to its execution record, and the degradation for unknown ones.

Verifies:
1. record_result enriches execution_time_ms from the execution
   record's elapsed when the caller omits timing.
2. get_raw_results joins to workflow_execution_history and exposes
   execution_status / execution_agent_id.
3. The join degrades gracefully for execution_ids with no record
   (pre-identity rows) — fields are None, no failure.
"""

import json
import sqlite3
from pathlib import Path

import pytest

from app.core.config import Paths, get_settings
from app.domain.workflows.services.ab_test_service import ABTestService
from app.workflows.execution_history import (
    record_execution_start,
    record_execution_complete,
    get_execution,
)
from app.workflows.execution_history import delete_execution

# THE ONE-RESOLVER DOCTRINE: no parent-walk. `parents[3] / "cogitate.db"`
# reached the production database by counting directories, so these tests wrote
# there — and passed only because the code under test read the same file.
DB_PATH = str(Paths.from_settings(get_settings()).shared_db)


@pytest.fixture
def service():
    return ABTestService()


def _cleanup(exec_id: str, test_id: str = "test-ab-join-001") -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM ab_test_results WHERE ab_test_id = ?", (test_id,))
        conn.execute("DELETE FROM ab_test_configs WHERE id = ?", (test_id,))
        conn.execute("DELETE FROM workflow_execution_history WHERE id = ?", (exec_id,))
        conn.commit()
    finally:
        conn.close()


def _make_test(service, test_id: str = "test-ab-join-001") -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO ab_test_configs "
            "(id, template_id, name, versions, traffic_split, is_active, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (test_id, "tpl-demo", "join test", json.dumps(["v1", "v2"]), json.dumps({"v1": 50, "v2": 50}), 1),
        )
        conn.commit()
    finally:
        conn.close()


def test_record_result_enriches_from_execution(service):
    exec_id = "test-ab-exec-001"
    _cleanup(exec_id)
    try:
        record_execution_start(execution_id=exec_id, template_id="tpl-demo", input_data={}, agent_id="agent-9")
        record_execution_complete(exec_id, status="completed", output_data={})
        # No timing supplied by caller — enrichment should read elapsed
        _make_test(service)
        service.record_result(
            "test-ab-join-001",
            type("R", (), {"version": "v1", "execution_id": exec_id,
                           "execution_time_ms": None, "tokens_used": 5,
                           "quality_score": 0.5, "success": True, "error_message": None})(),
        )
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            "SELECT execution_time_ms FROM ab_test_results WHERE execution_id = ?",
            (exec_id,),
        ).fetchone()
        conn.close()
        # Enriched value may be 0 if elapsed rounds to 0ms; key check is not-None
        assert row is not None and row[0] is not None
    finally:
        _cleanup(exec_id)


def test_get_raw_results_joins_execution(service):
    exec_id = "test-ab-exec-002"
    _cleanup(exec_id)
    try:
        record_execution_start(execution_id=exec_id, template_id="tpl-demo", input_data={}, agent_id="agent-9")
        record_execution_complete(exec_id, status="completed", output_data={"ok": True})
        _make_test(service)
        svc = service
        svc.record_result(
            "test-ab-join-001",
            type("R", (), {"version": "v1", "execution_id": exec_id,
                           "execution_time_ms": 100, "tokens_used": 5,
                           "quality_score": 0.5, "success": True, "error_message": None})(),
        )
        results = svc.get_raw_results("test-ab-join-001")
        assert len(results) == 1
        r = results[0]
        assert r.execution_status == "completed"
        assert r.execution_agent_id == "agent-9"
        assert r.execution_started_at is not None
    finally:
        _cleanup(exec_id)


def test_join_degrades_for_unknown_execution(service):
    # An execution_id with no record (pre-identity rows) → joined fields None
    _make_test(service)
    svc = service
    svc.record_result(
        "test-ab-join-001",
        type("R", (), {"version": "v1", "execution_id": "no-such-execution",
                       "execution_time_ms": 100, "tokens_used": 5,
                       "quality_score": 0.5, "success": True, "error_message": None})(),
    )
    try:
        results = svc.get_raw_results("test-ab-join-001")
        assert len(results) == 1
        r = results[0]
        assert r.execution_status is None
        assert r.execution_agent_id is None
    finally:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM ab_test_results WHERE ab_test_id = ?", ("test-ab-join-001",))
        conn.execute("DELETE FROM ab_test_configs WHERE id = ?", ("test-ab-join-001",))
        conn.commit()
        conn.close()
