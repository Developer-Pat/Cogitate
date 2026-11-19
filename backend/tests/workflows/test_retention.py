"""Run retention — the windows, the preview, and the prune that honours them.

A run occupies three places at once: the identity ROW, the debug SNAPSHOTS inside its metadata,
and the checkpoint THREAD it owns. Measured on this install before any of it was reclaimable:
4.85 MB of snapshots per list request and 53 threads nothing could delete. These tests pin the
policy resolution (config, tolerant to a stale blob), the preview that changes nothing, and the
prune that acts on all three.

ISOLATION. Every test runs against its OWN database file, built from the live table's own DDL —
fidelity from the real schema, isolation so a prune under test cannot touch a row another test
put there. `execution_history` reads its module-level `DB_PATH` at call time, so patching that
one name redirects every primitive.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

import pytest

from app.core.config import Paths, get_settings
from app.workflows.retention import (
    DEFAULT_POLICY,
    POLICY_SETTINGS_KEY,
    RetentionPolicy,
    prune_runs,
    resolve_policy,
)

TEMPLATE_ID = "tpl-retention-probe"
LIVE_DB = str(Paths.from_settings(get_settings()).shared_db)


# ── the sandbox ─────────────────────────────────────────────────────────────────────────


@pytest.fixture()
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A private database carrying the LIVE table's schema, and every primitive pointed at it."""
    import app.workflows.execution_history as eh

    db = tmp_path / "retention.db"
    source = sqlite3.connect(LIVE_DB)
    try:
        ddl = source.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='workflow_execution_history'"
        ).fetchone()[0]
    finally:
        source.close()

    target = sqlite3.connect(db)
    target.execute(ddl)
    target.commit()
    target.close()

    monkeypatch.setattr(eh, "DB_PATH", db)
    yield db


def _iso(*, days_ago: float = 0) -> str:
    return (datetime.now(UTC) - timedelta(days=days_ago)).isoformat().replace("+00:00", "Z")


def _make_row(
    execution_id: str,
    *,
    started_days_ago: float = 0,
    status: str = "completed",
    snapshots: bool = False,
) -> None:
    """A row of a chosen AGE and shape — the historical states the windows are about.

    Raw SQL on purpose: `record_execution_start` always stamps "now", and a test about aging has
    to state the age it is testing.
    """
    import app.workflows.execution_history as eh

    metadata: dict[str, Any] = {"trace_level": "debug", "agent_id": "agent-7"}
    if snapshots:
        metadata["node_snapshots"] = [{"node": "plan", "state": {"x": "y" * 400}} for _ in range(5)]

    conn = sqlite3.connect(eh.DB_PATH)
    try:
        conn.execute(
            """
            INSERT INTO workflow_execution_history
                (id, template_id, status, input_data, error_message, started_at, completed_at,
                 elapsed_seconds, metadata)
            VALUES (?, ?, ?, '{}', NULL, ?, ?, 1.0, ?)
            """,
            (
                execution_id,
                TEMPLATE_ID,
                status,
                _iso(days_ago=started_days_ago),
                None if status == "started" else _iso(days_ago=started_days_ago),
                json.dumps(metadata),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _row(execution_id: str) -> dict[str, Any] | None:
    from app.workflows.execution_history import get_execution

    return get_execution(execution_id)


def _status_of(execution_id: str) -> str:
    row = _row(execution_id)
    assert row is not None
    return str(row["status"])


def _metadata_of(execution_id: str) -> dict[str, Any]:
    row = _row(execution_id)
    assert row is not None
    return json.loads(row["metadata"])


# ── the policy is CONFIG ────────────────────────────────────────────────────────────────


def test_the_defaults_are_declared_once_and_used_when_nothing_is_configured():
    policy = resolve_policy(None)

    assert policy == DEFAULT_POLICY
    assert (policy.enabled, policy.snapshot_days, policy.run_days) == (False, 7, 90)
    assert policy.abandoned_hours == 24


def test_a_partial_section_resolves_field_by_field():
    policy = resolve_policy({POLICY_SETTINGS_KEY: {"snapshot_days": 2}})

    assert policy.snapshot_days == 2
    assert policy.run_days == DEFAULT_POLICY.run_days
    assert policy.enabled is False


def test_a_section_that_would_loosen_a_window_falls_back_instead():
    """A settings blob written by another build can hold a stale or hostile value. The model's
    own constraints are the guard: `run_days: -5` must not become a window that prunes a store."""
    assert resolve_policy({POLICY_SETTINGS_KEY: {"run_days": -5}}).run_days == DEFAULT_POLICY.run_days
    assert resolve_policy({POLICY_SETTINGS_KEY: "not a section"}).run_days == DEFAULT_POLICY.run_days
    assert resolve_policy({POLICY_SETTINGS_KEY: {"nonsense": 1}}).run_days == DEFAULT_POLICY.run_days


# ── the preview ─────────────────────────────────────────────────────────────────────────


def test_a_preview_reports_the_same_numbers_and_changes_nothing(isolated_db: Path):
    _make_row("old", started_days_ago=200, snapshots=True)
    _make_row("mid", started_days_ago=30, snapshots=True)
    _make_row("stuck", started_days_ago=10, status="started")

    report = prune_runs(RetentionPolicy(), dry_run=True)

    assert report.dry_run is True
    assert "old" in report.pruned_ids
    assert report.snapshots_stripped == 2  # `old` and `mid`: both past the 7-day snapshot window
    assert report.snapshot_bytes_freed > 0
    assert "stuck" in report.abandoned_ids

    # NOTHING happened: every row is there, the snapshots are still inside them, and the stuck
    # run still claims to be running.
    assert _row("old") is not None
    assert "node_snapshots" in _metadata_of("mid")
    assert _status_of("stuck") == "started"


# ── the prune ───────────────────────────────────────────────────────────────────────────


def test_the_prune_acts_on_all_three_and_keeps_the_row_inside_the_window(isolated_db: Path):
    _make_row("old", started_days_ago=200, snapshots=True)
    _make_row("mid", started_days_ago=30, snapshots=True)
    _make_row("fresh", started_days_ago=1, snapshots=True)

    report = prune_runs(RetentionPolicy(), dry_run=False)

    # THE ROW past its keep-window is gone …
    assert _row("old") is None
    # … while the one inside it survives, WITH its snapshots (too young to strip)
    assert _row("fresh") is not None
    assert "node_snapshots" in _metadata_of("fresh")
    # … and the middle one kept its row and lost only the blob
    assert _row("mid") is not None
    assert "node_snapshots" not in _metadata_of("mid")
    # everything else the row carried is untouched by the strip
    assert _metadata_of("mid")["agent_id"] == "agent-7"
    assert report.snapshot_bytes_freed > 0
    assert report.errors == []


def test_a_stuck_run_is_marked_abandoned_rather_than_deleted(isolated_db: Path):
    """A status correction, not a deletion: the row stays, the lie goes."""
    _make_row("stuck", started_days_ago=10, status="started")
    _make_row("recent", started_days_ago=0, status="started")

    report = prune_runs(RetentionPolicy(), dry_run=False)

    assert "stuck" in report.abandoned_ids
    assert _status_of("stuck") == "abandoned"
    assert _row("stuck") is not None
    # inside the grace period: a run started minutes ago might genuinely be running
    assert _status_of("recent") == "started"


def test_the_pruned_runs_checkpoint_thread_goes_with_its_row(isolated_db: Path):
    """The thread lives in ANOTHER store, with no foreign key to the history table — which is
    exactly why nothing reclaimed one before, and why the pair must be deleted together."""
    from langgraph.graph import END, START, StateGraph

    from app.workflows.checkpointing.config import CheckpointerManager
    from app.workflows.state.workflow_state import WorkflowState

    execution_id = "thread-owner"
    _make_row(execution_id, started_days_ago=200)
    saver = CheckpointerManager.get_checkpointer()
    config = {"configurable": {"thread_id": execution_id}}

    def node(state: dict[str, Any]) -> dict[str, Any]:
        return {"template_id": TEMPLATE_ID}

    graph = StateGraph(WorkflowState)
    graph.add_node("only", node)
    graph.add_edge(START, "only")
    graph.add_edge("only", END)
    graph.compile(checkpointer=saver).invoke(
        {"workflow_id": execution_id, "template_id": TEMPLATE_ID, "messages": []}, config
    )
    assert saver.get_tuple(config) is not None, "the test's own thread was not created"

    report = prune_runs(RetentionPolicy(), dry_run=False)

    assert execution_id in report.pruned_ids
    assert report.threads_pruned >= 1
    assert saver.get_tuple(config) is None, "the run's journal outlived the run"


def test_the_list_stops_shipping_the_debug_snapshots(isolated_db: Path):
    """The payload was 4.85 MB for the newest 50 rows — all of it `node_snapshots`."""
    from app.workflows.execution_history import list_executions

    _make_row("listed", started_days_ago=1, snapshots=True)

    listed = {r["id"]: r for r in list_executions(template_id=TEMPLATE_ID, limit=50)}["listed"]
    listed_metadata = json.loads(listed["metadata"])

    assert "node_snapshots" not in listed_metadata
    assert listed_metadata["agent_id"] == "agent-7"  # the rest of the row still travels
    # and the row itself still carries them: the detail read and the prune look there
    assert "node_snapshots" in _metadata_of("listed")


def test_applying_a_prune_must_be_decided_rather_than_merely_requested():
    """The house rule for a destructive verb: `confirm` is not a gate (any caller can send it) —
    it is the difference between a request that DECIDED and one that arrived, so a stray call, a
    retry with dropped parameters or a script defaulting to everything fails instead of deleting.
    A preview needs no such decision."""
    import asyncio

    from fastapi import HTTPException

    from app.workflows.api.workflow_router import run_retention_prune

    with pytest.raises(HTTPException) as refused:
        asyncio.run(run_retention_prune(dry_run=False, confirm=False))
    assert refused.value.status_code == 400
    assert "confirm=true" in str(refused.value.detail)

    # A PREVIEW needs no decision and must run end to end (its own path through the endpoint, the
    # settings read and the primitives) — a refused apply that is the only thing exercised leaves
    # the happy path untested, which is how a name error hides behind a passing suite.
    preview = asyncio.run(run_retention_prune(dry_run=True, confirm=False))
    assert preview["dry_run"] is True
    assert preview["errors"] == []


def test_a_failing_step_is_reported_rather_than_raised(isolated_db: Path):
    """A maintenance sweep that raises stops the housekeeping it exists to do."""
    import app.workflows.retention as retention

    def explode(cutoff: str) -> list[dict[str, Any]]:
        raise RuntimeError("boom")

    original = retention.list_prunable_executions
    retention.list_prunable_executions = explode
    try:
        report = retention.prune_runs(RetentionPolicy(), dry_run=False)
    finally:
        retention.list_prunable_executions = original

    assert any("boom" in e for e in report.errors)
    assert report.rows_pruned == 0
