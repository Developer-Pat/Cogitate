"""
Workflow execution identity — the start, complete and error records.

Verifies:
1. record_execution_start inserts a 'started' row with template_id,
   input_data, agent link (metadata), started_at.
2. record_execution_complete updates to 'completed' with output,
   completed_at, elapsed_seconds.
3. Failure recording sets status='error' + error_message.
4. The write-path is non-fatal: a missing table never raises
   (execution identity must not break workflow execution).
"""

import json
import os
import sqlite3
from pathlib import Path

from app.core.config import Paths, get_settings
from app.workflows.execution_history import (
    record_execution_start,
    record_execution_complete,
    get_execution,
    delete_execution,
)

# THE ONE-RESOLVER DOCTRINE, and no parent-walk: `parents[3] / "cogitate.db"`
# reached the production database by counting directories.
DB_PATH = str(Paths.from_settings(get_settings()).shared_db)


def _cleanup(test_id: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM workflow_execution_history WHERE id = ?", (test_id,))
        conn.commit()
    finally:
        conn.close()


def test_execution_start_record():
    test_id = "test-exec-start-001"
    _cleanup(test_id)
    try:
        record_execution_start(
            execution_id=test_id,
            template_id="tpl-demo",
            input_data={"query": "hello"},
            agent_id="agent-7",
        )
        rec = get_execution(test_id)
        assert rec is not None, "execution row should exist"
        assert rec["status"] == "started"
        assert rec["template_id"] == "tpl-demo"
        assert json.loads(rec["input_data"]) == {"query": "hello"}
        meta = json.loads(rec["metadata"] or "{}")
        assert meta.get("agent_id") == "agent-7"
        assert rec["started_at"]
        assert rec["completed_at"] is None
        assert rec["elapsed_seconds"] is None
    finally:
        _cleanup(test_id)


def test_execution_complete_record():
    test_id = "test-exec-complete-001"
    _cleanup(test_id)
    try:
        record_execution_start(execution_id=test_id, template_id="tpl-demo", input_data={})
        record_execution_complete(test_id, status="completed", output_data={"result": "ok"})
        rec = get_execution(test_id)
        assert rec is not None
        assert rec["status"] == "completed"
        assert json.loads(rec["output_data"]) == {"result": "ok"}
        assert rec["completed_at"] is not None
        assert rec["elapsed_seconds"] is not None and rec["elapsed_seconds"] >= 0
    finally:
        _cleanup(test_id)


def test_execution_error_record():
    test_id = "test-exec-error-001"
    _cleanup(test_id)
    try:
        record_execution_start(execution_id=test_id, template_id="tpl-demo", input_data={})
        record_execution_complete(test_id, status="error", error_message="boom")
        rec = get_execution(test_id)
        assert rec is not None
        assert rec["status"] == "error"
        assert rec["error_message"] == "boom"
    finally:
        _cleanup(test_id)


def test_missing_table_is_non_fatal():
    """The write-path must never raise — even if the table is missing."""
    # Point at a nonexistent DB by temporarily overriding the module's path
    import app.workflows.execution_history as eh

    original = eh.DB_PATH
    eh.DB_PATH = Path("/tmp/definitely-not-a-cogitate-db.db")
    try:
        # Should log a warning, not raise
        record_execution_start(execution_id="x", template_id="tpl", input_data={})
        record_execution_complete("x", status="completed")
        record_execution_start(execution_id="y", template_id="tpl", input_data={})
    finally:
        eh.DB_PATH = original
    # If we got here without exceptions, the non-fatal guarantee holds
    assert True


def test_delete_execution_removes_record():
    test_id = "test-exec-delete-001"
    _cleanup(test_id)
    try:
        record_execution_start(execution_id=test_id, template_id="tpl-demo", input_data={})
        assert get_execution(test_id) is not None
        deleted = delete_execution(test_id)
        assert deleted is True
        assert get_execution(test_id) is None
        # Deleting again returns False
        assert delete_execution(test_id) is False
    finally:
        _cleanup(test_id)


def test_a_fresh_record_is_inside_every_retention_window():
    """The prune itself lives in `tests/workflows/test_retention.py`, on ITS OWN database file (a
    prune run from here would reach into the shared copy and mark rows other tests are reading).

    What this file guards is the neighbouring claim, measured rather than asserted by running the
    sweep: a row written NOW is inside both windows, so the maintenance path cannot take a live
    record out from under an operator who is looking at it."""
    import datetime as _dt

    from app.workflows.retention import DEFAULT_POLICY

    test_id = "test-exec-prune-001"
    _cleanup(test_id)
    try:
        record_execution_start(execution_id=test_id, template_id="tpl-demo", input_data={})
        row = get_execution(test_id)
        assert row is not None and row["started_at"]

        started = _dt.datetime.fromisoformat(row["started_at"].replace("Z", "+00:00"))
        age_days = (_dt.datetime.now(_dt.timezone.utc) - started).total_seconds() / 86400

        assert age_days < DEFAULT_POLICY.run_days, "a fresh run is inside the keep window"
        assert age_days * 24 < DEFAULT_POLICY.abandoned_hours, "and inside the abandon grace"
    finally:
        _cleanup(test_id)
