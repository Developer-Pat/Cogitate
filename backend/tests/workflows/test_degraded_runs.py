"""Degraded runs — the second axis beside a run's execution outcome.

A graph that ended normally can still have failed inside it: a node absorbs a failure so the
run will not hang or die, and the run is honestly `completed` — with something wrong inside it.
These tests pin the two halves of that: the VERDICT the frame reads off the final state, and
the ROW it records (`degraded` on the metadata annotation, lifted for the list's reader).

The keying rule is the whole design, so it is tested from both sides: the verdict is keyed on
`metadata.status` (a node's own declaration) and never on `execution_result.error`, which the
batch families fill with per-ITEM errors — keying on that would mark healthy batch runs degraded.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.core.config import Paths, get_settings
from app.workflows.api.workflow_router import (
    _final_metadata,
    _mark_run_degraded,
    _run_verdict,
)
from app.workflows.execution_history import (
    get_execution,
    list_executions,
    record_execution_complete,
    record_execution_start,
)
from app.workflows.state.workflow_state import LLMResolution, RunMetadata, WorkflowState

RUN_ID = "wf-degraded-probe"
TEMPLATE_ID = "tpl-degraded-probe"
DB_PATH = str(Paths.from_settings(get_settings()).shared_db)

STATEMENT = "Phi4 Mini (ollama) is not functioning properly — the provider reported: boom."


def _metadata(**fields: Any) -> RunMetadata:
    base: dict[str, Any] = {"workflow_id": RUN_ID, "template_id": TEMPLATE_ID}
    base.update(fields)
    return RunMetadata(**base)


def _compiled_run(metadata: RunMetadata, *, execution_result: Any = None) -> tuple[Any, dict]:
    """Run a one-node graph that ends with this metadata; return (graph, config)."""

    def node(state: dict[str, Any]) -> dict[str, Any]:
        update: dict[str, Any] = {"metadata": metadata}
        if execution_result is not None:
            update["execution_result"] = execution_result
        return update

    graph = StateGraph(WorkflowState)
    graph.add_node("the_node", node)
    graph.add_edge(START, "the_node")
    graph.add_edge("the_node", END)
    compiled = graph.compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": RUN_ID}}
    compiled.invoke({"workflow_id": RUN_ID, "template_id": TEMPLATE_ID, "messages": []}, config)

    return compiled, config


def _verdict_from(metadata: RunMetadata, *, execution_result: Any = None) -> Any:
    """The whole read: the checkpoint, then the rule."""
    compiled, config = _compiled_run(metadata, execution_result=execution_result)
    return _run_verdict(_final_metadata(compiled, config))


# ── the read ────────────────────────────────────────────────────────────────────────────


def test_the_final_metadata_is_read_from_the_checkpoint():
    """The debug trace level returns a `RetryResult`, not the state, so the frame reads the
    CHECKPOINT — and one read serves both trace levels."""
    compiled, config = _compiled_run(_metadata(status="running"))

    read = _final_metadata(compiled, config)

    assert read is not None and read.workflow_id == RUN_ID


def test_an_unreadable_state_is_no_verdict_rather_than_a_guess():
    """A checkpoint read that fails must not invent or drop an outcome."""

    class NoState:
        def get_state(self, config: Any) -> Any:
            raise RuntimeError("no checkpointer")

    metadata = _final_metadata(NoState(), {"configurable": {"thread_id": RUN_ID}})

    assert metadata is None
    assert _run_verdict(metadata) is None


# ── the rule ────────────────────────────────────────────────────────────────────────────


def test_a_clean_run_has_no_verdict():
    assert _verdict_from(_metadata(status="running")) is None


def test_an_absorbed_failure_is_its_statement():
    """What a `recoverable` node writes: the run is marked, and the sentence names the service."""
    verdict = _verdict_from(
        _metadata(
            status="error",
            error="boom",
            failure_statement=STATEMENT,
            llm_resolution=LLMResolution(provider="ollama", model="phi4-mini:latest"),
        )
    )
    assert verdict == STATEMENT


def test_an_absorbed_failure_without_a_statement_falls_back_to_its_own_error():
    assert _verdict_from(_metadata(status="error", error="the node failed")) == "the node failed"


def test_an_absorbed_failure_that_says_nothing_still_degrades_the_run():
    """The run is worse for it either way — a surface must not read "degraded but silent"."""
    verdict = _verdict_from(_metadata(status="error"))
    assert verdict is not None and verdict.strip()


def test_per_item_errors_do_not_degrade_a_healthy_run():
    """THE KEYING RULE. A batch run carries per-item failures in `execution_result.error`; its
    own metadata says `running`, so nothing was absorbed and the run is healthy."""
    verdict = _verdict_from(
        _metadata(status="running"),
        execution_result={"error": "No files found for BossAgent dispatch"},
    )
    assert verdict is None


def test_a_tolerated_failure_leaves_the_run_clean():
    """The monitor family: the failure is in its own `errors` list and the run is not marked."""
    verdict = _verdict_from(
        _metadata(status="running"),
        execution_result={"errors": ["the feed is down"], "new_items": []},
    )
    assert verdict is None


# ── the state the frame leaves behind ───────────────────────────────────────────────────


def test_a_degraded_run_leaves_a_state_that_agrees_with_its_row():
    """`/status` reads the STATE. If the frame left the node's `error` in place, the panel would
    report a failure for a run the list shows as `completed` — the disagreement this arc exists
    to remove, in the other direction."""
    compiled, config = _compiled_run(
        _metadata(
            status="error",
            error="boom",
            failure_statement=STATEMENT,
            llm_resolution=LLMResolution(provider="ollama", model="phi4-mini:latest", rung="primary"),
        )
    )
    read = _final_metadata(compiled, config)

    _mark_run_degraded(compiled, config, read)
    after = _final_metadata(compiled, config)

    assert after.status == "completed", "the run's outcome in the state must match the row"
    assert after.degraded is True
    # the EVIDENCE stays — it is what makes the flag useful
    assert after.failure_statement == STATEMENT
    assert after.error == "boom"
    # a copy, never a constructor: the run's identity survives (llm_resolution above all)
    assert after.llm_resolution == read.llm_resolution
    assert after.template_id == TEMPLATE_ID


def test_marking_leaves_a_metadata_that_is_not_run_metadata_alone():
    """A hand-built state carries a dict; marking must not raise on it."""

    class FakeGraph:
        def update_state(self, config: Any, values: Any) -> None:  # pragma: no cover
            raise AssertionError("must not be called for a non-RunMetadata value")

    _mark_run_degraded(FakeGraph(), {}, {"status": "error"})  # no exception == the assertion


# ── the row ─────────────────────────────────────────────────────────────────────────────


def _cleanup(execution_id: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM workflow_execution_history WHERE id = ?", (execution_id,))
        conn.commit()
    finally:
        conn.close()


def test_a_degraded_run_is_recorded_completed_with_the_flag_and_the_message():
    execution_id = "test-exec-degraded-001"
    _cleanup(execution_id)
    try:
        record_execution_start(execution_id=execution_id, template_id=TEMPLATE_ID, input_data={})
        record_execution_complete(
            execution_id,
            status="completed",
            error_message=STATEMENT,
            degraded=True,
        )

        row = get_execution(execution_id)
        assert row is not None
        # THE TWO AXES: the execution outcome is unchanged, the cleanliness rides beside it
        assert row["status"] == "completed"
        assert row["error_message"] == STATEMENT
        assert json.loads(row["metadata"])["degraded"] is True
    finally:
        _cleanup(execution_id)


def test_a_healthy_run_records_the_flag_as_false():
    execution_id = "test-exec-healthy-001"
    _cleanup(execution_id)
    try:
        record_execution_start(execution_id=execution_id, template_id=TEMPLATE_ID, input_data={})
        record_execution_complete(execution_id, status="completed")

        row = get_execution(execution_id)
        assert row is not None
        assert row["error_message"] is None
        # written rather than omitted, so a reader never INFERS "not degraded" from absence
        assert json.loads(row["metadata"])["degraded"] is False
    finally:
        _cleanup(execution_id)


def test_the_list_serves_the_flag_without_the_reader_parsing_json():
    degraded_id, clean_id = "test-exec-list-degraded", "test-exec-list-clean"
    for execution_id in (degraded_id, clean_id):
        _cleanup(execution_id)
    try:
        for execution_id, degraded in ((degraded_id, True), (clean_id, False)):
            record_execution_start(execution_id=execution_id, template_id=TEMPLATE_ID, input_data={})
            record_execution_complete(
                execution_id, status="completed", degraded=degraded,
                error_message="absorbed" if degraded else None,
            )

        rows = {r["id"]: r for r in list_executions(template_id=TEMPLATE_ID, limit=50)}

        assert rows[degraded_id]["degraded"] is True
        assert rows[clean_id]["degraded"] is False
    finally:
        for execution_id in (degraded_id, clean_id):
            _cleanup(execution_id)


def test_a_row_predating_the_flag_reads_as_not_degraded():
    """176 rows existed before the flag did. Absence is not degradation, and a metadata blob
    that will not parse must never take the list endpoint down."""
    execution_id = "test-exec-legacy-metadata"
    _cleanup(execution_id)
    try:
        record_execution_start(execution_id=execution_id, template_id=TEMPLATE_ID, input_data={})
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute(
                "UPDATE workflow_execution_history SET status = 'completed', metadata = ? WHERE id = ?",
                ('{"agent_id": "agent-7", "trace_level": "debug"}', execution_id),
            )
            conn.commit()
        finally:
            conn.close()

        rows = {r["id"]: r for r in list_executions(template_id=TEMPLATE_ID, limit=50)}
        assert rows[execution_id]["degraded"] is False

        # a malformed column is tolerated too
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute(
                "UPDATE workflow_execution_history SET metadata = ? WHERE id = ?",
                ("not json at all", execution_id),
            )
            conn.commit()
        finally:
            conn.close()

        rows = {r["id"]: r for r in list_executions(template_id=TEMPLATE_ID, limit=50)}
        assert rows[execution_id]["degraded"] is False
    finally:
        _cleanup(execution_id)
