"""
Workflow state definitions for LangGraph orchestration.

This module defines the canonical state structure used throughout
workflow execution, following LangGraph best practices.
"""

from typing import Annotated, Optional, Any, Literal, TypedDict
import operator
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, ConfigDict


class LLMResolution(BaseModel):
    """The service a RUN resolved at its start — carried so a failure can name it.

    The resolution is taken ONCE, at the run's start (phase 6, group 4, G4-F2), and travels as
    plain DATA because the failure frame (`run_workflow_async`) holds no database session — the
    step that must name the offender cannot ask the resolver for itself.

    `rung` is the RESOLVER's own vocabulary (`capability config`, `global default`, `disabled`,
    `none`, …), kept for the log line. It is deliberately NOT the failure statement's `reason`:
    that clause is the exception's, read at the failure site.
    """

    provider: Optional[str] = None
    model: Optional[str] = None
    rung: Optional[str] = None


class RunMetadata(BaseModel):
    """
    Metadata for a single workflow RUN (not the workflow definition).

    Attributes:
        workflow_id: The RUN's identifier (the execution id — also the thread id)
        template_id: ID of the workflow template being executed
        started_at: ISO format timestamp when workflow started
        completed_at: ISO format timestamp when workflow completed
        status: Current execution status (running, paused, completed, error, cancelled)
        error: Error message if status is 'error'
        retry_attempts: Number of retry attempts made
        config: Optional configuration from template
        tags: Optional list of tags from the template for categorization
        trace_level: Execution mode ('debug'/'release', Phase H)
        node_snapshots: Per-node state snapshots (debug runs only)
        llm_resolution: The service the run resolved at its start (G4-F2), carried so a failed
            run can name it — None for a run that resolved nothing, or one that predates this.
        failure_statement: The ONE wording for the failure, set on the error path so the
            run-level panel can render it — None when the run named nobody (G4-F5). `error`
            keeps the RAW exception (A1); this is the rendered sentence.
    """
    workflow_id: str
    template_id: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    status: Literal["running", "paused", "completed", "error", "cancelled"] = "running"
    error: Optional[str] = None
    retry_attempts: Optional[int] = None  # Number of retry attempts made
    config: Optional[dict] = None  # Template configuration
    tags: Optional[list[str]] = None  # Tags from template
    trace_level: Optional[str] = None  # Execution mode (debug/release, Phase H)
    node_snapshots: Optional[list[dict]] = None  # Per-node state snapshots (debug runs)
    # The service resolved at the run's START (G4-F2) — carried as data so the failure frame,
    # which holds no database session, can name the offender instead of reporting a raw error.
    llm_resolution: Optional[LLMResolution] = None
    # THE STATEMENT (phase 6 group 4, Stage 3): the one wording for the failure, rendered from the
    # carried resolution + the exception and set on the error path. It is served to the run-level
    # panel so the panel and the toast say the same sentence. None when the run named nobody (G4-F5).
    failure_statement: Optional[str] = None
    # THE SECOND AXIS (the 2026-10-07 ruling): True when a step failed and the run ABSORBED it.
    # The run's OUTCOME is still `completed` — this is the flag beside it, written by the record
    # layer from the final state (no node sets it), so `/status` and the history row tell the
    # same story in the same words.
    degraded: bool = False

    model_config = ConfigDict(json_schema_extra={ "example": { "workflow_id": "wf-123456", "template_id": "tpl-789", "started_at": "2026-03-23T12:00:00Z", "status": "running", "tags": ["test", "debug"] } })


# ── THE `metadata` CHANNEL'S MERGE POLICY ────────────────────────────────────────────────
# LangGraph REPLACES a state key whose TypedDict declares no reducer. `messages` and
# `tool_calls_history` have one; `metadata` did not — so a node that built a fresh
# `RunMetadata(...)` (32 sites across 9 node modules) silently dropped everything the run was
# carrying, `llm_resolution` included. Measured: after the first node the resolution was gone,
# so `run_failure_statement` returned None for a genuine provider failure and the gate built to
# name the offender could never fire on the node path.
#
# The policy is TWO LISTS, not a plain merge — a bare merge would make a stale verdict sticky
# (an earlier node's `error` would outlive a later node's success):
#
#   CARRY   identity — who the run is and what it resolved. A writer that does not name the
#           field keeps the run's value. `llm_resolution` is the whole reason this exists.
#   REPLACE verdict — the run's outcome. A writer that does not name the field gets the
#           field's own default, which is exactly the behaviour replacement semantics had
#           before this reducer: a later success node still clears an earlier failure.
#
# A writer that wants to CLEAR a carried field names it explicitly (`llm_resolution=None`),
# and the explicit value wins.
_CARRIED_FIELDS: frozenset[str] = frozenset({
    "workflow_id",
    "template_id",
    "started_at",
    "config",
    "tags",
    "trace_level",
    "llm_resolution",
})


def merge_run_metadata(current: Any, update: Any) -> Any:
    """The `metadata` channel's reducer: keep the run's identity, take the writer's verdict.

    Reads the update's NAMED fields only (`model_dump(exclude_unset=True)`), so a fresh
    `RunMetadata(workflow_id=..., status="running")` from a node is a statement about those two
    fields and nothing else. Both constructor-built and `model_copy(update=...)`-built values
    register their named fields, so either writer is read the same way.
    """
    if not isinstance(current, RunMetadata) or not isinstance(update, RunMetadata):
        # Nothing to carry from (or into) a value that is not run metadata: the update stands,
        # which is what the channel did before this reducer existed.
        return update
    named = update.model_dump(exclude_unset=True)
    carried = {field: getattr(current, field) for field in _CARRIED_FIELDS if field not in named}
    return update.model_copy(update=carried) if carried else update


class WorkflowState(TypedDict):
    """
    Canonical workflow state with accumulative message history.

    This is the primary state structure used throughout workflow execution,
    following LangGraph best practices.

    This is the primary state structure passed between nodes in LangGraph
    workflows. It follows LangGraph best practices:

    - Uses TypedDict for explicit type hints
    - Leverages add_messages reducer for accumulative message history
    - Minimal fields that can be expanded as needed
    - Clear separation of concerns (identity, execution, metadata)

    Attributes:
        messages: Accumulative message history with built-in reducer
        workflow_id: Unique identifier for this workflow execution
        template_id: ID of the workflow template being executed
        inputs: Input values for workflow nodes
        current_step: Name of the current step being executed
        execution_result: Results from step execution
        outputs: Output values from workflow execution (for UI display)
        approval_required: Whether this workflow requires human approval
        approval_status: Status of approval request (pending, approved, rejected)
        metadata: Workflow execution metadata

    Example:
        ```python
        state = {
            "messages": [HumanMessage(content="Start workflow")],
            "workflow_id": "wf-123",
            "template_id": "tpl-456",
            "inputs": {"user_input": "Hello"},
            "current_step": None,
            "execution_result": None,
            "outputs": {"greeting": "Hello, World!"},
            "approval_required": False,
            "approval_status": None,
            "metadata": RunMetadata(
                workflow_id="wf-123",
                template_id="tpl-456",
                status="running"
            )
        }
        ```
    """
    # Message history with built-in reducer for accumulation
    messages: Annotated[list[BaseMessage], add_messages]

    # Workflow identification
    workflow_id: str
    template_id: str

    # Input values for workflow nodes
    inputs: dict[str, Any]

    # Template configuration (the monitor-family config channel —
    # the 2026-08-18 wiring fix: the router seeds the template
    # config here; monitor nodes read feeds/params from it)
    config: Optional[dict[str, Any]]

    # Execution state
    current_step: Optional[str]
    execution_result: Optional[dict[str, Any]]
    outputs: Optional[dict[str, Any]]

    # Human-in-the-loop
    approval_required: bool
    approval_status: Optional[Literal["pending", "approved", "rejected"]]

    # Metadata — MERGED, not replaced: identity fields (the run's resolved service above all)
    # survive every node's rebuild, verdict fields keep their replace semantics. See
    # `merge_run_metadata` for the policy and the defect it closes.
    metadata: Annotated[RunMetadata, merge_run_metadata]

    # Phase 3 — Observability & Robustness
    tool_calls_history: Annotated[list[dict], operator.add]
    """Accumulated record of every tool call across all loop iterations."""

    tool_loop_count: int
    """Counter for ReAct loop iterations (guard against infinite loops)."""

    # Multi-agent ReAct loop support
    pending_tool_calls: Optional[list[dict]]
    """Tool calls pending execution (used for routing in ReAct loop)."""

    current_agent_step: Optional[int]
    """Current agent step number being executed (for multi-agent ReAct loop routing)."""
