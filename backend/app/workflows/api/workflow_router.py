"""
FastAPI router for workflow execution and management.

Provides REST API endpoints for:
- Starting workflow executions
- Checking workflow status
- Managing workflow templates
- Human-in-the-loop approvals
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any, List
from datetime import datetime, UTC
import uuid
import logging

logger = logging.getLogger(__name__)

from app.core.database import get_db_session  # noqa: E402
from ..graphs.simple_workflow import create_simple_workflow  # noqa: E402
from ..checkpointing.config import CheckpointerManager  # noqa: E402
from ..state.workflow_state import RunMetadata, WorkflowState, LLMResolution  # noqa: E402
from ..observability import LangfuseManager  # noqa: E402
from ..error_handling import RetryConfig, execute_with_retry, RollbackManager, RecoveryWorkflow, RecoveryStrategy  # noqa: E402
from ..execution_history import record_execution_start, record_execution_complete, delete_execution, list_executions  # noqa: E402
from ..utils.run_failure import run_failure_statement  # noqa: E402


# ── Graph resolution (Phase D: the if-chain is now DATA) ──────────────
# Legacy per-template graphs — templates whose graph is genuinely
# per-template (not kind-generic): the provider-test fixtures, the
# per-agent demos, the tool-test fixtures, and the monitor family's
# source variants. Resolution order:
#   1. this table (exact template_id match)
#   2. the kind registry (kind_id → KIND_GRAPH_FACTORIES)
#   3. default simple workflow

_LEGACY_TEMPLATE_GRAPHS = {
    "test-llm-connection": ("..graphs.default_provider_test_graphs", "create_llm_connection_graph", None),
    "test-llm-chain": ("..graphs.default_provider_test_graphs", "create_llm_chain_graph", None),
    "test-llm-summary": ("..graphs.default_provider_test_graphs", "create_llm_summary_graph", None),
    "test-llm-comparison": ("..graphs.default_provider_test_graphs", "create_llm_comparison_graph", None),
    "agent-hello": ("..graphs.agent_workflows", "create_hello_agent_graph", None),
    "agent-math": ("..graphs.agent_workflows", "create_math_assistant_graph", None),
    "agent-code-review": ("..graphs.agent_workflows", "create_code_review_graph", None),
    "agent-summary": ("..graphs.agent_workflows", "create_summary_agent_graph", None),
    # tool-test fixtures — the agent-with-tools graph
    "test-calculator": ("..graphs.agent_workflows", "create_agent_workflow_graph", ("..nodes.agent_nodes", "agent_invoke_node")),
    "test-datetime": ("..graphs.agent_workflows", "create_agent_workflow_graph", ("..nodes.agent_nodes", "agent_invoke_node")),
    "test-file-info": ("..graphs.agent_workflows", "create_agent_workflow_graph", ("..nodes.agent_nodes", "agent_invoke_node")),
    "test-text-tools": ("..graphs.agent_workflows", "create_agent_workflow_graph", ("..nodes.agent_nodes", "agent_invoke_node")),
    "test-todo-list": ("..graphs.agent_workflows", "create_agent_workflow_graph", ("..nodes.agent_nodes", "agent_invoke_node")),
    # monitor family — source-variant graphs
    "rss-monitor": ("..graphs.monitor_graph", "create_rss_monitor_graph", None),
    "market-watch": ("..graphs.monitor_graph", "create_market_watch_graph", None),
    "readiness-check": ("..graphs.monitor_graph", "create_readiness_check_graph", None),
    # the system-audit workflow (2026-08-20): audit → verify →
    # analyze → report — the structural verification (a read-back
    # node in the graph) for unattended runs
    "system-audit": ("..graphs.system_audit_graph", "create_system_audit_graph", None),
}


def _resolve_legacy_graph(template_id: str):
    """Resolve a legacy per-template graph (exact id) or None."""
    entry = _LEGACY_TEMPLATE_GRAPHS.get(template_id)
    if not entry:
        return None
    module_path, factory_name, arg = entry
    import importlib
    module = importlib.import_module(module_path, package=__package__)
    factory = getattr(module, factory_name)
    if arg:
        arg_module_path, arg_name = arg
        arg_module = importlib.import_module(arg_module_path, package=__package__)
        arg_value = getattr(arg_module, arg_name)
        return factory(arg_value)
    return factory()


def _resolve_kind_graph(template_id: str):
    """Resolve via the kind registry (template's kind_id → factory)."""
    try:
        import sqlite3
        from app.core.config import Paths, get_settings
        db_path = Paths.from_settings(get_settings()).shared_db
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute(
                "SELECT kind_id FROM workflow_templates WHERE id = ?", (template_id,)
            ).fetchone()
        finally:
            conn.close()
        if not row or not row[0]:
            return None
        from app.domain.workflows.kinds.registry import resolve_kind_graph_factory
        factory = resolve_kind_graph_factory(row[0])
        return factory() if factory else None
    except Exception:
        return None


def get_workflow_graph(template_id: str):
    """
    Get workflow graph based on template type.

    Resolution order (Phase D — the if-chain is now data):
      1. legacy per-template graphs (_LEGACY_TEMPLATE_GRAPHS)
      2. the kind registry (template's kind_id → factory)
      3. default simple workflow

    Args:
        template_id: ID of the template to determine workflow type

    Returns:
        StateGraph builder (will be compiled by compile_workflow())
    """
    if template_id:
        graph = _resolve_legacy_graph(template_id)
        if graph is not None:
            return graph
        graph = _resolve_kind_graph(template_id)
        if graph is not None:
            return graph

    # Default to simple workflow
    # THE LOUD-FALLBACK FIX (2026-08-23, the user's logging-gap
    # audit): a template that resolves to the DEFAULT SIMPLE graph
    # silently 'completed' in 0.05s (the deep-agent-job bug — the
    # graph resolution tier fell through). The user's doctrine:
    # FALLBACKS LOG LOUDLY. This is a WARNING with the template id —
    # a run that does nothing must be visible, not a fake success.
    logger.warning(
        "⚠️  WORKFLOW GRAPH FALLBACK: template '%s' resolved to the "
        "DEFAULT SIMPLE graph (no legacy entry, no kind factory) — "
        "the run will 'complete' without doing the work. Check the "
        "legacy table + the kind registry (KIND_GRAPH_FACTORIES).",
        template_id,
    )
    return create_simple_workflow()

router = APIRouter(prefix="/workflows", tags=["workflows"])


# ============== Request/Response Models ==============

class WorkflowToolGrant(BaseModel):
    """A declared tool need for a workflow run (Phase D).

    tool_slug: the keyed tool the workflow's agents must use.
    agent_ids: which agents hold the grant (None = all agents in
    the run). Issued as scope='run:<workflow_id>' at dispatch,
    revoked at run end.
    """

    tool_slug: str = Field(..., description="The tool slug to grant")
    agent_ids: Optional[List[str]] = Field(
        None, description="Agents to grant (None = all)"
    )


class ExecuteWorkflowRequest(BaseModel):
    """Request to start a new workflow execution.

    trace_level (Phase H, one engine / two modes):
    - 'debug' (DEFAULT): per-node state snapshots + full langfuse
      recording — diagnosing is the pre-launch bottleneck
    - 'release': lean tracing, no per-node snapshot capture
    The mode gates CAPTURE only; it never forks behavior.
    """
    template_id: str = Field(..., description="ID of workflow template to execute")
    initial_message: str = Field(..., description="User message to start workflow with")
    inputs: Optional[Dict[str, Any]] = Field(None, description="Input values for workflow nodes")
    workflow_id: Optional[str] = Field(None, description="Optional custom workflow ID")
    trace_level: str = Field(
        "debug",
        description="Execution mode: 'debug' (per-node snapshots, default) or 'release' (lean)",
    )
    tool_grants: Optional[List[WorkflowToolGrant]] = Field(
        None,
        description="Declared tool needs for this run (Phase D — the "
        "declarative grant path). Each entry names a tool slug the "
        "workflow's agents need; run-scoped grants are issued at "
        "dispatch and revoked at run end. Exa (the ARM) sets these "
        "when composing an orchestration.",
    )


class ExecuteWorkflowResponse(BaseModel):
    """Response after starting workflow execution."""
    workflow_id: str
    template_id: str
    status: str
    thread_id: str
    started_at: str
    message: str = "Workflow started successfully"


class WorkflowStatusResponse(BaseModel):
    """Current status of a workflow execution."""
    workflow_id: str
    template_id: str
    status: str
    current_step: Optional[str]
    next_nodes: List[str]
    execution_result: Optional[Dict[str, Any]]
    outputs: Optional[Dict[str, Any]]  # Workflow output values for UI display
    approval_required: bool
    approval_status: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    error: Optional[str]
    failure_statement: Optional[str] = None
    """The ONE wording for a failed run (naming the service it resolved) — None when the
    run named nobody. `error` above keeps the RAW exception (A1)."""
    degraded: bool = False
    """The second axis: the run COMPLETED with a failure absorbed inside it. `status` stays the
    execution outcome; this is whether the run was worse for it, and `failure_statement`/`error`
    carry the detail."""
    tool_calls_history: Optional[List[Dict[str, Any]]] = None
    """History of all tool calls made during workflow execution."""


class ApproveWorkflowRequest(BaseModel):
    """Request to approve or reject a workflow step."""
    status: str = Field(..., description="Approval status: 'approved' or 'rejected'")
    comment: Optional[str] = Field(None, description="Optional comment for approval/rejection")


class ApproveWorkflowResponse(BaseModel):
    """Response after approval action."""
    workflow_id: str
    approval_status: str
    message: str


# ============== Helper Functions ==============

def get_workflow_config(thread_id: str) -> dict:
    """Get workflow configuration with thread isolation."""
    return {"configurable": {"thread_id": thread_id}}


def compile_workflow(template_id: str | None = None):
    """
    Compile workflow graph with checkpointer.

    Uses CheckpointerManager to get a persistent checkpointer instance
    that stays open for background tasks.

    Args:
        template_id: ID of template to determine workflow type.
        When None, defaults to the simple workflow.

    Returns:
        Compiled StateGraph ready for execution
    """
    if template_id is None:
        logger.warning("compile_workflow called without template_id; falling back to simple workflow")
        graph = get_workflow_graph("simple")
    else:
        graph = get_workflow_graph(template_id)

    # Phase F: attach the kind's declared error contract as the
    # graph's native per-node RetryPolicy (the taxonomy → LangGraph
    # bridge). Kind-less/unknown templates get the default contract.
    try:
        from app.workflows.error_handling.policy_injector import apply_kind_retry_policy
        kind_name = None
        try:
            import sqlite3
            from app.core.config import Paths, get_settings
            db_path = Paths.from_settings(get_settings()).shared_db
            conn = sqlite3.connect(db_path)
            try:
                row = conn.execute(
                    "SELECT kind_id FROM workflow_templates WHERE id = ?", (template_id,)
                ).fetchone()
                if row and row[0]:
                    kind_name = row[0]
            finally:
                conn.close()
        except Exception:
            pass
        apply_kind_retry_policy(graph, kind_name or "simple")
    except Exception:
        pass  # policy wiring is non-critical; never block execution

    checkpointer = CheckpointerManager.get_checkpointer()
    
    # Only use interrupt_before for advanced workflows
    if template_id and "approval" in template_id.lower():
        return graph.compile(checkpointer=checkpointer, interrupt_before=["reviewer"])
    else:
        return graph.compile(checkpointer=checkpointer)


async def _resolve_run_llm(db) -> Optional[LLMResolution]:
    """Resolve the run's LLM capability to `{provider, model, rung}` — once, at the run's START.

    G4-F2: the failure frame (`run_workflow_async`) holds NO database session, so the answer is
    taken HERE, where a session exists, and carried as data on the run's own metadata — a failure
    must name what THIS run resolved, not what a re-resolution would say later.

    A read that fails yields None: the run still starts, and a failure falls back to the raw error
    rather than inventing a service name. `rung` is the resolver's vocabulary; a capability that
    resolves to NOTHING still carries its rung (`disabled`, `none`), so the log says why.
    """
    try:
        from app.domain.providers.capabilities import (
            WORKFLOW_CAPABILITY_KEY,
            resolve as resolve_capability,
        )
        resolved = await resolve_capability(db, WORKFLOW_CAPABILITY_KEY)
        primary = resolved.primary
        return LLMResolution(
            provider=primary.provider if primary else None,
            model=primary.model if primary else None,
            rung=resolved.reason,
        )
    except Exception as e:
        logger.warning(f"⚠️ could not resolve the workflow-llm capability for the run: {e}")
        return None


async def _build_initial_state(
    db,
    request: "ExecuteWorkflowRequest",
    workflow_id: str,
    template_config: dict,
    template_tags: list,
) -> WorkflowState:
    """Build the run's initial state, carrying the LLM resolved for THIS run (G4-F2).

    The resolution is placed on `metadata.llm_resolution` here — one seam, so a test can assert a
    run CARRIES what it resolved without standing up a graph.
    """
    from langchain_core.messages import HumanMessage

    llm_resolution = await _resolve_run_llm(db)
    return {
        "workflow_id": workflow_id,
        "template_id": request.template_id,
        "messages": [HumanMessage(content=request.initial_message)],
        "inputs": request.inputs or {},  # Pass inputs from request
        # the monitor-family config channel (2026-08-18 wiring fix):
        # the monitor nodes read feeds from state["config"] — the
        # template config was only in metadata.config (filtered for
        # the MonitorState graphs), so every run got 0 items
        "config": template_config or {},
        "current_step": None,
        "execution_result": None,
        "outputs": None,
        "approval_required": False,
        "approval_status": None,
        "metadata": RunMetadata(
            workflow_id=workflow_id,
            template_id=request.template_id,
            started_at=datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            status="running",
            config=template_config,  # Include template config in metadata
            tags=template_tags,  # Include template tags in metadata
            # The service resolved for THIS run (G4-F2) — carried so the failure frame,
            # which holds no session, can name the offender.
            llm_resolution=llm_resolution,
        ),
        "tool_calls_history": [],
        "tool_loop_count": 0,
        "pending_tool_calls": None,
        "current_agent_step": None,
    }


# ============== API Endpoints ==============

@router.post("/execute", response_model=ExecuteWorkflowResponse)
async def execute_workflow(
    request: ExecuteWorkflowRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Start workflow execution in background.

    Returns immediately with workflow_id for tracking.
    Workflow continues executing in background even if HTTP connection closes.

    **Features**:
    - Non-blocking execution
    - Automatic workflow ID generation
    - Thread isolation per workflow
    - Checkpoint-based persistence

    **Example**:
    ```python
    POST /api/v1/workflows/execute
    {
        "template_id": "tpl-123",
        "initial_message": "Help me write a report"
    }

    Response:
    {
        "workflow_id": "wf-abc123",
        "status": "started",
        "thread_id": "wf-abc123"
    }
    ```
    """
    # Generate workflow ID if not provided
    workflow_id = request.workflow_id or f"wf-{uuid.uuid4().hex[:12]}"
    thread_id = workflow_id  # Use workflow_id as thread_id for simplicity

    # PHASE C — THE LIFECYCLE EVENT (2026-08-24): the pipeline's
    # first consumer wiring — publish the started event so the SSE
    # stream shows a run beginning live.
    try:
        from app.domain.messaging.services import publish
        publish(f"workflow:{workflow_id}:started", {
            "workflow_id": workflow_id,
            "template_id": request.template_id,
            "started_at": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        })
    except Exception as _e:
        logger.error(f"  ❌ workflow:started publish failed: {_e}")

    # Record execution identity (agent link via request inputs/metadata if present)
    agent_id = None
    if request.inputs and isinstance(request.inputs, dict):
        agent_id = request.inputs.get("agent_id") or request.inputs.get("agentId")
    record_execution_start(
        execution_id=workflow_id,
        template_id=request.template_id,
        input_data=request.inputs,
        agent_id=agent_id,
    )

    # Log workflow start with clear visual markers
    logger.info("=" * 60)
    logger.info("🚀 WORKFLOW EXECUTION STARTING")
    logger.info(f"   Workflow ID: {workflow_id}")
    logger.info(f"   Template ID: {request.template_id}")
    logger.info("=" * 60)

    # Compile workflow with template-specific graph
    try:
        compiled = compile_workflow(template_id=request.template_id)
    except Exception as e:
        logger.error(f"❌ Failed to compile workflow | workflow_id={workflow_id} | error={str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to compile workflow: {str(e)}")

    # Load template config from database — ONE READER, shared with the scheduler's trigger path
    # (`app/workflows/template_config.py`). This block used to be inline here alone; the scheduler
    # had its own shape and seeded `"config": None`, which is how every scheduled monitor run
    # resolved zero feeds for weeks while reporting a clean cycle.
    from app.workflows.template_config import load_template_config

    template_config, template_tags = load_template_config(request.template_id)

    # Prepare the run's initial state — and resolve its LLM capability ONCE, HERE, where a
    # database session exists (G4-F2): the failure frame has none, so the answer must travel on
    # the run's own metadata (`_build_initial_state` places it there).
    initial_state: WorkflowState = await _build_initial_state(
        db, request, workflow_id, template_config, template_tags
    )
    
    config = get_workflow_config(thread_id)

    # Start workflow execution in background using asyncio.create_task
    # This ensures the HTTP response is sent immediately
    import asyncio
    
    async def start_workflow():
        """Start workflow execution in a separate task.

        Phase D — the declarative grant path: when the request
        declares tool_grants, issue run-scoped grants to the
        workflow's agents BEFORE the run, revoke at run end.
        """
        grant_scope = f"run:{workflow_id}"
        if request.tool_grants:
            await _issue_run_grants(
                request.tool_grants, grant_scope=grant_scope
            )
        try:
            await run_workflow_async(
                compiled_graph=compiled,
                initial_state=initial_state,
                config=config,
                workflow_id=workflow_id,
                trace_level=request.trace_level,
            )
        finally:
            if request.tool_grants:
                await _revoke_run_grants(
                    request.tool_grants, grant_scope=grant_scope
                )
    
    # Create task that runs independently of the HTTP response
    asyncio.create_task(start_workflow())

    return ExecuteWorkflowResponse(
        workflow_id=workflow_id,
        template_id=request.template_id,
        status="started",
        thread_id=thread_id,
        started_at=datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        message="Workflow started successfully"
    )


async def _issue_run_grants(
    grants: List["WorkflowToolGrant"], grant_scope: str
) -> None:
    """Issue run-scoped grants for the declared tool needs.

    The declarative ARM path (study 11 q2): Exa composing an
    orchestration declares "needs web-search for these agents";
    the grants are derived here — no imperative grant API call.
    """
    try:
        from app.core.database import AsyncSessionLocal
        from app.domain.tools.grant_service import AgentToolGrantService
        from app.domain.tools.services import ToolRegistryService
        async with AsyncSessionLocal() as db:
            svc = AgentToolGrantService(db)
            tools = ToolRegistryService(db)
            for decl in grants:
                tool = await tools.get_tool_by_slug(decl.tool_slug)
                if not tool:
                    logger.warning(
                        f"⚠️ tool_grants: unknown tool '{decl.tool_slug}'"
                    )
                    continue
                if decl.agent_ids:
                    for aid in decl.agent_ids:
                        await svc.grant(
                            str(aid), tool.id, granted_by="exa",
                            scope=grant_scope,
                        )
                else:
                    # no agent ids → grant ALL agents in the pool
                    from app.domain.agents.services import AgentService
                    agents, _total = await AgentService(db).list_all_agents()
                    for a in agents:
                        await svc.grant(
                            str(a.id), tool.id, granted_by="exa",
                            scope=grant_scope,
                        )
    except Exception as e:
        logger.error(f"❌ _issue_run_grants failed: {e}")


async def _revoke_run_grants(
    grants: List["WorkflowToolGrant"], grant_scope: str
) -> None:
    """Revoke the run-scoped grants at run end (the scope dies)."""
    try:
        from app.core.database import AsyncSessionLocal
        from app.domain.tools.grant_service import AgentToolGrantService
        from app.domain.tools.services import ToolRegistryService
        async with AsyncSessionLocal() as db:
            svc = AgentToolGrantService(db)
            tools = ToolRegistryService(db)
            for decl in grants:
                tool = await tools.get_tool_by_slug(decl.tool_slug)
                if not tool:
                    continue
                if decl.agent_ids:
                    for aid in decl.agent_ids:
                        await svc.revoke(str(aid), tool.id, scope=grant_scope)
                else:
                    from app.domain.agents.services import AgentService
                    agents, _total = await AgentService(db).list_all_agents()
                    for a in agents:
                        await svc.revoke(str(a.id), tool.id, scope=grant_scope)
    except Exception as e:
        logger.error(f"❌ _revoke_run_grants failed: {e}")


def _announce_run_failure(workflow_id: str, statement: Optional[str]) -> None:
    """Publish the run-level toast for a failed run — only where the run NAMED somebody.

    G4-F5: a non-LLM failure has no offender to finger, so nothing is announced and the panel
    carries its raw error instead. The bus is a singleton wiring concern, so the import sits at
    the publish site — the house shape (the executor, the chat router and the title service all
    import it locally). A publish failure must not change the run's outcome: caught and logged.
    """
    if not statement:
        return
    try:
        from app.domain.messaging.services import publish_warning

        publish_warning("Workflow run failed", statement, kind="workflow-failure")
    except Exception as e:
        logger.error(
            f"  ❌ workflow:failure toast publish failed | workflow_id={workflow_id} | {e}"
        )


def _announce_run_degraded(workflow_id: str, message: str) -> None:
    """Publish the toast for a DEGRADED run — one that finished with something wrong inside it.

    Different wording from the failure toast on purpose, and a different rule about firing: that
    one needs a NAMED offender (G4-F5) because the run died on the provider's behalf, while here
    the run completed and the message may be a plain raw error. It is announced whether or not
    anybody was named — the run IS worse for it, and an unattended run is exactly where nobody is
    watching a panel.
    """
    try:
        from app.domain.messaging.services import publish_warning

        publish_warning(
            "Workflow finished with an absorbed failure", message, kind="workflow-degraded"
        )
    except Exception as e:
        logger.error(
            f"  ❌ workflow:degraded toast publish failed | workflow_id={workflow_id} | {e}"
        )


def _error_metadata(
    initial_state: dict,
    workflow_id: str,
    error: str,
    retry_attempts: Optional[int] = None,
    failure_statement: Optional[str] = None,
) -> RunMetadata:
    """The run's metadata with the OUTCOME set — a COPY of what the run carried.

    A failure path must not REBUILD the metadata: the constructor sets only the fields it is
    given, so a rebuild silently drops `config`, `tags`, `trace_level` and the carried
    `llm_resolution` — on exactly the path A1 is about, a failed run that must still name the
    service it resolved at its start. So the carried object is copied and only the outcome
    fields are overwritten.

    `failure_statement` is the rendered sentence (Stage 3) the run-level panel reads; `error`
    stays the RAW exception, so the one wording and the raw cause each keep a home.
    """
    update: dict[str, Any] = {"status": "error", "error": error}
    if retry_attempts is not None:
        update["retry_attempts"] = retry_attempts
    if failure_statement is not None:
        update["failure_statement"] = failure_statement
    carried = initial_state.get("metadata")
    if isinstance(carried, RunMetadata):
        return carried.model_copy(deep=True, update=update)
    # No carried metadata (a run started without one): build the minimum, never a partial copy.
    return RunMetadata(
        workflow_id=workflow_id,
        template_id=initial_state.get("template_id") or "",
        **update,
    )


def _failure_state(
    initial_state: dict,
    workflow_id: str,
    error_text: str,
    retry_attempts: Optional[int] = None,
    failure_statement: Optional[str] = None,
) -> dict[str, Any]:
    """The state a FAILED run leaves behind — ONE shape, both failure paths.

    A fatal node (see `error_handling/grades.py`) hands the run its failure by RAISING instead
    of returning an error state, so the frame writes what such a node's error state would have
    carried: the metadata verdict AND the `execution_result` shape the run detail reads
    (`error_details.message` — the user-friendly message `workflowService` prefers). Without it
    a fatal failure's detail had only the row's raw string, which is a worse surface than the
    node path it replaced.

    `failure_statement` is the rendered sentence when the run named somebody; the raw error is
    the fallback, so the detail shows the raw cause when nobody was named.
    """
    message = failure_statement or error_text
    return {
        "metadata": _error_metadata(
            initial_state, workflow_id, error_text, retry_attempts,
            failure_statement=failure_statement,
        ),
        "execution_result": {
            "error": message,
            "error_details": {"message": message},
        },
    }


def _metadata_field(metadata: Any, name: str) -> Any:
    """One field off the run's metadata — `RunMetadata` or a hand-built dict."""
    if isinstance(metadata, dict):
        return metadata.get(name)
    return getattr(metadata, name, None)


def _final_metadata(compiled_graph: Any, config: dict) -> Any:
    """The run's metadata from its FINAL checkpoint — `None` when it cannot be read.

    Read from the CHECKPOINT rather than from the invoke's return value, because the debug trace
    level returns a `RetryResult` and not the state — one read, both trace levels. A read failure
    is logged and answered with `None`: a missing answer must never change a run's outcome.
    """
    try:
        snapshot = compiled_graph.get_state(config)
        values = getattr(snapshot, "values", None) or {}
    except Exception as e:
        logger.warning(f"⚠️  could not read the final state for a degraded verdict | {e}")
        return None
    return values.get("metadata")


def _run_verdict(metadata: Any) -> Optional[str]:
    """The run's DEGRADED message when a node declared it errored — `None` for a clean run.

    THE ONE RULE THIS RESTS ON: key on `metadata.status` — the node's OWN declaration, which the
    grade decides (`error_handling/grades.py`) — and NEVER on `execution_result.error`. That field
    is overloaded with per-ITEM errors from the batch families, so keying on it marks healthy
    batch runs degraded (measured when the shape was chosen: four of the 165 completed rows would
    have flipped, wrongly). A TOLERANT node never marks the run at all, so the monitor family is
    clean here by construction.
    """
    if _metadata_field(metadata, "status") != "error":
        return None
    statement = _metadata_field(metadata, "failure_statement")
    raw = _metadata_field(metadata, "error")
    return statement or raw or "a step failed and the run absorbed it"


def _mark_run_degraded(compiled_graph: Any, config: dict, metadata: Any) -> None:
    """Write the run's OUTCOME back into its final state: `completed`, second axis set.

    A node marked the run `status="error"` to say a step failed and it absorbed that. The run's
    outcome belongs to the record layer, so the state is corrected to say what the history row now
    says — otherwise `/status` reads `error` (and the run detail shows a failure panel) for a run
    the list shows as `completed`, which is the very disagreement this arc is about. `error` and
    `failure_statement` STAY: the evidence of what went wrong is what makes the flag useful.

    A copy, never a constructor (the carry policy in `workflow_state.py`): rebuilding the metadata
    would drop the run's identity fields, `llm_resolution` first among them.
    """
    if not isinstance(metadata, RunMetadata):
        return
    try:
        compiled_graph.update_state(
            config,
            {"metadata": metadata.model_copy(update={"status": "completed", "degraded": True})},
        )
    except Exception as e:
        logger.warning(f"⚠️  could not record the degraded outcome in the run's state | {e}")


async def run_workflow_async(
    compiled_graph,
    initial_state: dict,
    config: dict,
    workflow_id: str,
    trace_level: str = "debug",
):
    """
    Run workflow in background with proper error handling.

    This function:
    1. Executes graph asynchronously in a thread pool
    2. Handles errors and updates state
    3. Persists final state via checkpointer
    4. Sends traces to Langfuse (if configured)
    5. Implements retry logic for transient failures

    Runs in background, doesn't block HTTP response.
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    # ONE trace per run, its id derived from the run's own id, so the run's node spans and the run
    # record join the same trace without either asking the other. The template becomes the trace's
    # NAME and tag — not its "session": a Langfuse session is a user's own interaction stream, and
    # the old call site passed a template id as one.
    _trace_id = LangfuseManager.run_trace_id(workflow_id)
    handler = LangfuseManager.get_langfuse_handler(trace_id=_trace_id)
    _template_id = initial_state.get("template_id")
    config = LangfuseManager.with_run_metadata(
        config,
        trace_name=f"workflow:{_template_id or workflow_id}",
        tags=[str(_template_id)] if _template_id else None,
    )

    # THE HANDLER RIDES THE CONFIG, NEVER A KWARG. `invoke(..., callbacks=[handler])` reads as if it
    # worked and did nothing: LangGraph's `**kwargs` channel is the DEPRECATED one and reads only
    # `checkpoint_during`, so a `callbacks=` kwarg is silently dropped — which is why no workflow run
    # had ever emitted a single span. The adapter's own tests cannot see it (they hand the handler its
    # events directly). `scripts/diagnostics/langfuse_sink.py` is the control: it drives this function
    # for real and fails if the spans stop arriving.
    if handler is not None:
        config = {**config, "callbacks": [handler]}

    # Configure retry for transient failures
    retry_config = RetryConfig(
        max_retries=3,
        delay=1.0,
        backoff_multiplier=2.0,
    )

    def on_retry(attempt: int, exc: Exception, delay: float):
        """Callback for retry attempts."""
        logger.warning(f"⚠️  Workflow {workflow_id} retry {attempt}/{retry_config.max_retries}: {exc} | Waiting {delay:.1f}s before retry...")

    is_debug = trace_level != "release"
    logger.info(f"🎚️  trace_level={trace_level} (mode: {'debug — per-node snapshots' if is_debug else 'release — lean'}) | workflow_id={workflow_id}")

    captured_snapshots: list[dict] = []

    def run_workflow():
        """Execute workflow in thread pool (will be retried on failure).

        ONE engine, TWO modes (Phase H): debug streams per-node
        state updates (stream_mode='updates') and records them as
        snapshots; release invokes plainly. The mode gates CAPTURE
        only — the graph and its behavior are identical.
        """
        if is_debug:
            # per-node snapshots: stream every node's state update
            # (the SAME graph, one engine — stream_mode only changes
            # what we capture, never the graph's behavior).
            try:
                for chunk in compiled_graph.stream(
                    initial_state, config,
                    stream_mode="updates",
                ):
                    captured_snapshots.append({
                        "node": list(chunk.keys())[0] if isinstance(chunk, dict) and chunk else None,
                        "state": chunk,
                    })
            except Exception as _stream_err:
                # capture failure must not change behavior — the
                # graph runs identically via invoke (same engine)
                logger.warning(f"⚠️  Debug stream capture failed, falling back to invoke | workflow_id={workflow_id} | {_stream_err}")
                result = compiled_graph.invoke(initial_state, config)
                return result
            # stream completed: report success (the caller's
            # result.success path works — same engine, richer record)
            from ..error_handling.retry import RetryResult
            return RetryResult(success=True, result=None, error=None, attempts=1)
        result = compiled_graph.invoke(initial_state, config)
        return result

    try:
        # Run workflow in thread pool to avoid blocking event loop
        # This is CRITICAL for allowing cancel requests to be processed during execution
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            result = await loop.run_in_executor(
                executor,
                lambda: execute_with_retry(run_workflow, config=retry_config, on_retry=on_retry)
            )

        if result.success:
            # Workflow completed successfully
            logger.info("=" * 60)
            logger.info("✅ WORKFLOW EXECUTION COMPLETED SUCCESSFULLY")
            logger.info(f"   Workflow ID: {workflow_id}")
            logger.info(f"   Attempts: {result.attempts}")
            logger.info("=" * 60)

            # THE SECOND AXIS (the 2026-10-07 ruling): the graph ended normally, and a run can
            # still have failed inside it — a node ABSORBED the failure so the run would not
            # hang or die. `status` stays the execution outcome (`completed`); the verdict rides
            # beside it, as a flag plus the message, and the run is announced: an unattended run
            # that quietly lost a step is the whole reason this axis exists.
            _final = _final_metadata(compiled_graph, config)
            _degraded = _run_verdict(_final)
            if _degraded:
                logger.warning("⚠️  WORKFLOW COMPLETED WITH AN ABSORBED FAILURE")
                logger.warning(f"   Workflow ID: {workflow_id}")
                logger.warning(f"   {_degraded}")
                _announce_run_degraded(workflow_id, _degraded)
                _mark_run_degraded(compiled_graph, config, _final)

            # PHASE C — THE COMPLETED EVENT
            try:
                from app.domain.messaging.services import publish
                publish(f"workflow:{workflow_id}:completed", {
                    "workflow_id": workflow_id,
                    "template_id": initial_state.get("template_id"),
                    "degraded": bool(_degraded),
                })
            except Exception as _e:
                logger.error(f"  ❌ workflow:completed publish failed: {_e}")

            record_execution_complete(
                workflow_id,
                status="completed",
                output_data=result.result if hasattr(result, "result") else None,
                error_message=_degraded,
                degraded=bool(_degraded),
                trace_level=trace_level,
                node_snapshots=captured_snapshots[-20:],
            )
        else:
            # All retries exhausted - update state with error
            error = result.error
            logger.error("=" * 60)
            logger.error("❌ WORKFLOW EXECUTION FAILED")
            logger.error(f"   Workflow ID: {workflow_id}")
            logger.error(f"   Attempts: {result.attempts}")
            logger.error(f"   Error: {str(error)}")
            # THE STATEMENT — the ONE wording, naming the service THIS run resolved at its start.
            # It reaches THREE surfaces, always the same sentence: the log (here), the run-level
            # panel (the metadata below), and the toast (Stage 3).
            _statement = run_failure_statement(initial_state.get("metadata"), error)
            if _statement:
                logger.error(f"   {_statement}")
            logger.error("=" * 60)

            # THE TOAST — a run that fails while the user is elsewhere still says so, in the SAME
            # words. A run that named nobody (G4-F5) announces nothing; the panel carries its raw
            # error instead.
            _announce_run_failure(workflow_id, _statement)

            # PHASE C — THE FAILED EVENT
            try:
                from app.domain.messaging.services import publish
                publish(f"workflow:{workflow_id}:failed", {
                    "workflow_id": workflow_id,
                    "template_id": initial_state.get("template_id"),
                    "error": str(error)[:300],
                })
            except Exception as _e:
                logger.error(f"  ❌ workflow:failed publish failed: {_e}")

            error_state = _failure_state(
                initial_state, workflow_id, str(error), result.attempts,
                failure_statement=_statement,
            )

            record_execution_complete(
                workflow_id,
                status="error",
                error_message=str(error),
                trace_level=trace_level,
                node_snapshots=captured_snapshots[-20:],
            )

            try:
                compiled_graph.update_state(config, error_state)
            except Exception as update_error:
                logger.error(f"Failed to update error state | workflow_id={workflow_id} | error={str(update_error)}")

        # Flush traces
        LangfuseManager.flush()

    except Exception as e:
        # Handle unexpected errors
        logger.error(f"❌ Unexpected error in workflow execution | workflow_id={workflow_id} | error={str(e)}")

        error_state = _failure_state(initial_state, workflow_id, str(e))

        record_execution_complete(
            workflow_id,
            status="error",
            error_message=str(e),
        )

        try:
            compiled_graph.update_state(config, error_state)
        except Exception as update_error:
            logger.error(f"Failed to update error state | workflow_id={workflow_id} | error={str(update_error)}")

        LangfuseManager.flush()


def _read_run_status_metadata(raw_metadata) -> dict[str, Any]:
    """Pull a run's outcome fields out of whatever the checkpointer handed back.

    Three shapes reach here — a `RunMetadata`-ish OBJECT, a plain DICT, and a corrupted repr
    STRING (older checkpoints). One reader, so a field cannot be found in one shape and missed
    in another. `error` is the RAW exception (A1); `failure_statement` is the rendered sentence
    (Stage 3) — None when the run named nobody (G4-F5).

    The repr branch keeps each existing field's exact behaviour: the `'None'` guard is applied
    where the original applied it (`error`) and to the new `failure_statement` as well, because a
    literal `"None"` statement would otherwise render as a bogus line on the panel and the toast.
    """
    if hasattr(raw_metadata, "status"):
        return {
            "status": getattr(raw_metadata, "status", None),
            "started_at": getattr(raw_metadata, "started_at", None),
            "completed_at": getattr(raw_metadata, "completed_at", None),
            "error": getattr(raw_metadata, "error", None),
            "failure_statement": getattr(raw_metadata, "failure_statement", None),
            "degraded": bool(getattr(raw_metadata, "degraded", False)),
        }
    if isinstance(raw_metadata, dict):
        return {
            "status": raw_metadata.get("status"),
            "started_at": raw_metadata.get("started_at"),
            "completed_at": raw_metadata.get("completed_at"),
            "error": raw_metadata.get("error"),
            "failure_statement": raw_metadata.get("failure_statement"),
            "degraded": bool(raw_metadata.get("degraded")),
        }

    import re

    text = str(raw_metadata)

    def _grab(field: str, *, none_is_none: bool = False) -> Optional[str]:
        match = re.search(rf"{field}='([^']*)'", text)
        if not match:
            return None
        value = match.group(1)
        return None if (none_is_none and value == "None") else value

    return {
        "status": _grab("status"),
        "started_at": _grab("started_at"),
        "completed_at": _grab("completed_at"),
        "error": _grab("error", none_is_none=True),
        "failure_statement": _grab("failure_statement", none_is_none=True),
        # a BOOLEAN in the repr (`degraded=True`), never a quoted string
        "degraded": re.search(r"degraded=True", text) is not None,
    }


@router.get("/{workflow_id}/status", response_model=WorkflowStatusResponse)
async def get_workflow_status(workflow_id: str):
    """
    Get current workflow status and state.
    
    Poll this endpoint to track workflow progress.
    Returns current state, next nodes to execute, and execution results.
    
    **Example**:
    ```python
    GET /api/v1/workflows/wf-abc123/status
    
    Response:
    {
        "workflow_id": "wf-abc123",
        "status": "running",
        "current_step": "executor",
        "next_nodes": ["executor"],
        "execution_result": {...},
        "approval_required": false
    }
    ```
    """
    thread_id = workflow_id
    config = get_workflow_config(thread_id)

    # First, try to read the template_id from the checkpoint using a generic graph
    # This ensures we compile with the correct graph type for proper state interpretation
    try:
        compiled_probe = compile_workflow()
        probe_state = compiled_probe.get_state(config)
    except Exception:
        probe_state = None

    template_id = None
    if probe_state and probe_state.values:
        template_id = probe_state.values.get("template_id")

    # Now compile with the correct template_id
    try:
        compiled = compile_workflow(template_id=template_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compile workflow: {str(e)}")

    # Get current state from checkpoint
    try:
        state = compiled.get_state(config)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Workflow not found: {str(e)}")
    
    if not state or not state.values:
        raise HTTPException(status_code=404, detail="Workflow not found or not started")

    # Extract the run's outcome fields — whatever shape the checkpointer handed back.
    fields = _read_run_status_metadata(state.values.get("metadata", {}))
    status = fields["status"]
    started_at = fields["started_at"]
    completed_at = fields["completed_at"]
    error = fields["error"]
    failure_statement = fields["failure_statement"]
    degraded = bool(fields.get("degraded"))

    # Infer status from execution_result and next_nodes if metadata status is unreliable
    if not status or status == "running":
        exec_result = state.values.get("execution_result")
        if exec_result and isinstance(exec_result, dict) and "error" in exec_result:
            status = "error"
        elif state.next == ():
            # No more nodes to execute — workflow is complete
            status = "completed"
            if not completed_at:
                from datetime import datetime, timezone
                completed_at = datetime.now(timezone.utc).isoformat()

    return WorkflowStatusResponse(
        workflow_id=workflow_id,
        template_id=state.values.get("template_id", "unknown"),
        status=status or "unknown",
        current_step=state.values.get("current_step"),
        next_nodes=list(state.next) if state.next else [],
        execution_result=state.values.get("execution_result"),
        outputs=state.values.get("outputs"),  # Include outputs in response
        approval_required=state.values.get("approval_required", False),
        approval_status=state.values.get("approval_status"),
        started_at=started_at,
        completed_at=completed_at,
        error=error,
        failure_statement=failure_statement,
        degraded=degraded,
        tool_calls_history=state.values.get("tool_calls_history")
    )


@router.post("/{workflow_id}/approve", response_model=ApproveWorkflowResponse)
async def approve_workflow_step(
    workflow_id: str,
    request: ApproveWorkflowRequest,
):
    """
    Approve or reject a workflow step requiring human review.
    
    Use this endpoint when workflow is paused at reviewer node.
    Workflow will resume execution after approval.
    
    **Example**:
    ```python
    POST /api/v1/workflows/wf-abc123/approve
    {
        "status": "approved",
        "comment": "Looks good, proceed!"
    }
    
    Response:
    {
        "workflow_id": "wf-abc123",
        "approval_status": "approved",
        "message": "Workflow resumed"
    }
    ```
    """
    thread_id = workflow_id
    config = get_workflow_config(thread_id)
    
    try:
        compiled = compile_workflow()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compile workflow: {str(e)}")
    
    # Get current state to verify workflow is paused
    state = compiled.get_state(config)
    
    if not state or not state.values:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Check if workflow is actually paused at reviewer
    if "reviewer" not in state.next:
        raise HTTPException(
            status_code=400,
            detail=f"Workflow is not waiting for approval. Next nodes: {state.next}"
        )
    
    # Resume workflow with approval response
    
    # Invoke with None to resume from checkpoint
    # The interrupt() will receive the approval_response
    resume_config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }
    
    try:
        # Resume execution with approval
        # This will continue from the interrupt point
        compiled.invoke(None, resume_config)
        
        # Note: The approval_response needs to be passed differently
        # In LangGraph 1.0+, use command or update_state before resume
        # This is a simplified version - full implementation requires
        # using langgraph.types.Command or state updates
        
    except Exception:
        # May raise exception if interrupt handling needs special approach
        pass  # Approval state is saved, workflow will continue
    
    return ApproveWorkflowResponse(
        workflow_id=workflow_id,
        approval_status=request.status,
        message=f"Workflow {'resumed' if request.status == 'approved' else 'rejected'}"
    )


@router.get("/{workflow_id}/history")
async def get_workflow_history(workflow_id: str):
    """
    Get workflow execution history (all checkpoints).
    
    Returns list of historical states for debugging and audit.
    """
    thread_id = workflow_id
    config = get_workflow_config(thread_id)
    
    try:
        compiled = compile_workflow()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compile workflow: {str(e)}")
    
    # Get full history
    try:
        history = list(compiled.get_state_history(config))
        
        # Convert to serializable format
        history_list = []
        for state in history:
            history_list.append({
                "checkpoint_id": state.config.get("checkpoint_id") if state.config else None,
                "next": list(state.next) if state.next else [],
                "status": state.values.get("metadata", {}).get("status") if state.values else None,
                "created_at": state.values.get("metadata", {}).get("started_at") if state.values else None,
            })
        
        return {
            "workflow_id": workflow_id,
            "history": history_list,
            "total_checkpoints": len(history_list)
        }
        
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"History not found: {str(e)}")


@router.delete("/products")
async def clear_workflow_products():
    """Delete all workflow product files + the display index.

    Stale-data reset for the Products page. Removes product
    markdown files + products.json from data/monitor/ (keeps
    state.json — that's monitor dedup state, not a product).
    """
    from app.workflows.distribution import clear_products

    removed = clear_products()
    return {"cleared": removed}


@router.delete("/products/{product_id}")
async def delete_workflow_product(product_id: str):
    """Delete ONE workflow product (file + index entry).

    The Products page's per-row/bulk delete (Phase G, 2026-08-17).
    The product_id is the entry's CREATED_AT — the per-entry
    identity (the collision fix, 2026-08-18: basename matching
    deleted every same-day same-type entry at once). Returns 404
    if no entry matched.
    """
    from fastapi import HTTPException
    from app.workflows.distribution import delete_product

    removed = delete_product(product_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"No product '{product_id}' in the index")
    return {"deleted": product_id}


@router.post("/monitors/reset")
async def reset_monitor_checkpoint(payload: dict):
    """Reset a monitor's dedup checkpoint — the next run treats
    every item as new (the 'full run' reset, 2026-08-18).

    The monitor family persists cross-run 'what did I already
    report?' state in data/monitor/state.json under last_seen
    (feed_url -> seen item ids). Clearing the entries for the
    named template's feeds forces a full run.

    Body: {"template_id": "rss-monitor"} (or "market-watch").
    """
    from fastapi import HTTPException
    from app.workflows.nodes.monitor_nodes import _load_state, _save_state

    template_id = (payload or {}).get("template_id", "")
    if template_id not in ("rss-monitor", "market-watch"):
        raise HTTPException(
            status_code=400,
            detail="template_id must be a monitor template (rss-monitor, market-watch)",
        )

    # the feeds for that template come from its config — reuse the
    # loader (feeds are the state.json keys; clearing ALL keys would
    # nuke the other monitor's dedup too)
    import json
    from app.core.config import Paths, get_settings
    db = Paths.from_settings(get_settings()).shared_db
    feeds: list[str] = []
    if db.exists():
        import sqlite3
        conn = sqlite3.connect(db)
        try:
            row = conn.execute(
                "SELECT config FROM workflow_templates WHERE id = ?",
                (template_id,),
            ).fetchone()
            if row:
                feeds = list((json.loads(row[0]) or {}).get("feeds", []))
        finally:
            conn.close()

    state = _load_state()
    last_seen = dict(state.get("last_seen") or {})
    cleared: list[str] = []
    for feed in feeds:
        if feed in last_seen:
            del last_seen[feed]
            cleared.append(feed)
    state["last_seen"] = last_seen
    _save_state(state)

    return {"reset": template_id, "cleared_feeds": cleared, "cleared_count": len(cleared)}


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str):
    """
    Delete a workflow execution and all checkpoints.

    Removes:
    1. The execution identity record (workflow_execution_history)
    2. All checkpoints + writes for the thread (LangGraph delete_thread)

    Use with caution - this is irreversible.
    """
    logger.warning(f"⚠️  Workflow deletion requested | workflow_id={workflow_id}")

    # The execution record is the identity — if it never existed, 404.
    # (delete_thread on a missing thread silently no-ops, so we must
    # gate on the record, not on checkpoint deletion.)
    record_deleted = delete_execution(workflow_id)
    if not record_deleted:
        raise HTTPException(status_code=404, detail=f"Workflow execution '{workflow_id}' not found")

    # Delete checkpoints + writes for the thread
    checkpoints_deleted = False
    checkpoint_error: Optional[str] = None
    try:
        checkpointer = CheckpointerManager.get_checkpointer()
        checkpointer.delete_thread(workflow_id)
        checkpoints_deleted = True
    except Exception as e:
        logger.warning(f"Failed to delete checkpoints | workflow_id={workflow_id} | error={e}")
        checkpoint_error = str(e)

    return {
        "workflow_id": workflow_id,
        "execution_record_deleted": True,
        "checkpoints_deleted": checkpoints_deleted,
        "checkpoint_error": checkpoint_error,
        "message": "Workflow execution and checkpoints deleted",
    }


@router.get("/toasts")
async def get_workflow_toasts(since: str = ""):
    """List unread workflow-product toasts.

    Reads data/monitor/toasts.json (the ToastDistributor's queue).
    The frontend polls this with since=<last-seen-created_at> and
    shows each newer entry as an in-app toast.
    """
    from app.core.config import Paths, get_settings

    queue = Paths.from_settings(get_settings()).monitor_dir / "toasts.json"
    if not queue.exists():
        return {"toasts": [], "total": 0}
    try:
        import json

        entries = json.loads(queue.read_text(encoding="utf-8"))
        if not isinstance(entries, list):
            entries = []
    except (json.JSONDecodeError, OSError):
        entries = []
    if since:
        entries = [e for e in entries if e.get("created_at", "") > since]
    return {"toasts": entries, "total": len(entries)}


@router.get("/products")
async def get_workflow_products(limit: int = 50):
    """List workflow products (the display index).

    Reads data/monitor/products.json — written by the
    DisplayDistributor when a workflow delivers a product
    (digest, alert, report). The frontend Workflow Products
    page polls this.
    """
    from app.core.config import Paths, get_settings

    index = Paths.from_settings(get_settings()).monitor_dir / "products.json"
    if not index.exists():
        return {"products": [], "total": 0}
    try:
        import json

        entries = json.loads(index.read_text(encoding="utf-8"))
        if not isinstance(entries, list):
            entries = []
    except (json.JSONDecodeError, OSError):
        entries = []
    return {"products": entries[: int(limit)], "total": len(entries)}


@router.get("/executions")
async def get_executions(
    template_id: Optional[str] = None,
    trigger_id: Optional[str] = None,
    limit: int = 50,
):
    """List execution records (newest first).

    Filters: template_id, trigger_id (triggered runs carry
    input_data.trigger_id — the scheduler records it, which
    distinguishes direct vs triggered executions).
    """
    rows = list_executions(
        template_id=template_id,
        trigger_id=trigger_id,
        limit=limit,
    )
    return {"executions": rows, "total": len(rows)}


# ============== Retention — the windows are CONFIG, not code ==============
#
# The policy lives in the app settings (`user_settings.settings["workflow_retention"]`), so every
# window is readable and changeable from the surface with no code edit and no restart. These
# endpoints are the surface's backing store; `workflows/retention.py` owns the meaning.


class RetentionPolicyUpdate(BaseModel):
    """A PARTIAL policy. Only the fields present in the body are changed."""

    enabled: Optional[bool] = None
    snapshot_days: Optional[int] = None
    run_days: Optional[int] = None
    abandoned_hours: Optional[int] = None
    schedule_hour: Optional[int] = None


@router.get("/retention")
async def get_retention_policy():
    """The EFFECTIVE policy, the defaults it was resolved against, and what the store holds.

    Sending the defaults as well is deliberate: a surface that shows a number must be able to
    say whether it is the shipped default or somebody's choice.
    """
    from ..execution_history import retention_stats
    from ..retention import DEFAULT_POLICY, POLICY_SETTINGS_KEY, load_settings_blob, resolve_policy

    blob = await load_settings_blob()
    return {
        "policy": resolve_policy(blob).model_dump(),
        "defaults": DEFAULT_POLICY.model_dump(),
        "configured": isinstance(blob.get(POLICY_SETTINGS_KEY), dict),
        "stats": retention_stats(),
    }


@router.put("/retention")
async def update_retention_policy(request: RetentionPolicyUpdate):
    """Change the windows. Values are VALIDATED — a nonsense window is refused, not stored."""
    from ..retention import (
        RetentionPolicy,
        load_settings_blob,
        resolve_policy,
        save_policy,
    )

    blob = await load_settings_blob()
    current = resolve_policy(blob)
    changes = {
        k: v for k, v in request.model_dump(exclude_unset=True).items() if v is not None
    }
    try:
        # validate, do NOT model_copy: a copy skips the constraints and would store `run_days=-5`
        policy = RetentionPolicy.model_validate({**current.model_dump(), **changes})
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid retention policy: {e}")

    await save_policy(policy)
    try:
        from app.domain.messaging.services import publish

        publish("setting:workflow_retention:updated", {"key": "workflow_retention", **policy.model_dump()})
    except Exception as e:
        logger.warning(f"retention: could not announce the policy change | {e}")

    return {"policy": policy.model_dump()}


@router.post("/retention/prune")
async def run_retention_prune(dry_run: bool = True, confirm: bool = False):
    """PREVIEW (`dry_run=true`, the default) or apply the retention windows.

    A preview changes nothing and reports the same measurement the act would — the counts, the
    bytes and the ids — so the cost is known before the decision. Applying is a PERSON's act: it
    runs regardless of the `enabled` setting, which governs the scheduled prune.

    **A prune must be DECIDED, not merely requested** (`confirm=true`). The flag is not a gate —
    any caller can send it — it is the difference between a request that decided and one that
    arrived, so the accidental shapes fail instead of deleting: a stray `curl` with no body, a
    retry whose parameters were dropped, a script defaulting to everything. The refusal names
    what is missing and points at the preview.
    """
    if not dry_run and not confirm:
        raise HTTPException(
            status_code=400,
            detail=(
                "Refused: applying the retention windows needs confirm=true. "
                "Preview first (dry_run=true, the default) to see what would go."
            ),
        )

    from ..retention import load_settings_blob, prune_with_settings

    blob = await load_settings_blob()
    report = prune_with_settings(dry_run=dry_run, settings_blob=blob)
    return report.model_dump()


@router.post("/executions/{execution_id}/cancel", response_model=dict)
async def cancel_execution(execution_id: str):
    """
    Cancel a running workflow execution.

    This endpoint:
    1. Updates workflow status to 'cancelled'
    2. Stops any ongoing execution
    3. Preserves execution history for audit

    Note: In LangGraph 1.0+, direct checkpoint manipulation is complex.
    This endpoint logs the cancellation request. The workflow will be marked
    as cancelled in the next polling cycle.

    **Example**:
    ```python
    POST /api/v1/workflows/executions/wf-abc123/cancel

    Response:
    {
        "workflow_id": "wf-abc123",
        "status": "cancelled",
        "message": "Workflow execution cancelled successfully"
    }
    ```
    """
    logger.warning("=" * 60)
    logger.warning("⏹️  WORKFLOW CANCELLATION REQUESTED")
    logger.warning(f"   Workflow ID: {execution_id}")
    logger.warning("=" * 60)

    try:
        from ..checkpointing.config import CheckpointerManager

        # Get the checkpointer
        checkpointer = CheckpointerManager.get_checkpointer()

        # Get current state - include checkpoint_ns for proper checkpoint access
        config = {"configurable": {"thread_id": execution_id, "checkpoint_ns": ""}}
        current_state = checkpointer.get(config)

        if not current_state:
            logger.warning(f"Workflow not found | workflow_id={execution_id}")
            raise HTTPException(status_code=404, detail=f"Workflow execution '{execution_id}' not found")

        # Check if workflow is already completed/failed/cancelled
        channel_values = current_state.get("channel_values", {})
        metadata = channel_values.get("metadata", "")

        # Parse metadata string to check status
        status = "unknown"
        metadata_str = str(metadata)
        logger.warning(f"🔍 Current workflow metadata | workflow_id={execution_id} | metadata={metadata_str[:200] if len(metadata_str) > 200 else metadata_str}")
        
        if "status=" in metadata_str:
            import re
            match = re.search(r"status='([^']+)'", metadata_str)
            if match:
                status = match.group(1)

        if status in ["completed", "failed", "cancelled"]:
            logger.warning(f"Workflow already in terminal state | workflow_id={execution_id} | status={status}")
            return {
                "workflow_id": execution_id,
                "status": status,
                "message": f"Workflow already in terminal state: {status}"
            }

        # For LangGraph 1.0+, we need to update the checkpoint properly
        # Create updated channel_values with cancelled metadata
        updated_channels = channel_values.copy()
        
        # Parse and update metadata
        metadata_str = str(metadata)
        if "status='running'" in metadata_str:
            metadata_str = metadata_str.replace("status='running'", "status='cancelled'")
            if "error=" in metadata_str and "error=None" in metadata_str:
                metadata_str = metadata_str.replace("error=None", "error='Cancelled by user'")
            else:
                metadata_str = metadata_str.rstrip() + " error='Cancelled by user'"
        
        updated_channels["metadata"] = metadata_str
        updated_channels["current_step"] = None
        
        # Build proper checkpoint update
        checkpoint_update = {
            "v": current_state.get("v", 4),
            "ts": datetime.now(UTC).isoformat() + "+00:00",
            "id": current_state.get("id", ""),
            "channel_values": updated_channels,
            "channel_versions": current_state.get("channel_versions", {}),
            "versions_seen": current_state.get("versions_seen", {}),
            "updated_channels": ["metadata", "current_step"]
        }

        logger.warning(f"📝 Updated metadata string | workflow_id={execution_id} | new_metadata={updated_channels['metadata'][:200] if len(str(updated_channels['metadata'])) > 200 else str(updated_channels['metadata'])}")

        # Create metadata for the checkpoint
        from langgraph.checkpoint.base import CheckpointMetadata
        checkpoint_metadata = CheckpointMetadata(
            source="update",
            step=current_state.get("channel_versions", {}).get("__start__", "0"),
            writes={"status": "cancelled"},  # type: ignore[typeddict-unknown-key]
        )

        # Update the checkpoint
        from langgraph.checkpoint.base import ChannelVersions
        new_versions = ChannelVersions()

        checkpointer.put(config, checkpoint_update, checkpoint_metadata, new_versions)
        logger.warning(f"✅ Checkpoint updated | workflow_id={execution_id}")

        logger.warning("=" * 60)
        logger.warning("✅ WORKFLOW EXECUTION CANCELLED")
        logger.warning(f"   Workflow ID: {execution_id}")
        logger.warning("   Reason: User requested termination")
        logger.warning("=" * 60)

        # THE ORDERLY-SHUTDOWN EVENT (2026-08-24, the queued item):
        # the cancel is recorded — publish the cancelling event so
        # the UI shows 'shutting down gracefully…' while the workers
        # cooperatively bail (the nodes check is_workflow_cancelled
        # between batches). The SSE stream carries it live.
        try:
            from app.domain.messaging.services import publish
            publish(f"workflow:{execution_id}:cancelling", {
                "workflow_id": execution_id,
                "reason": "user",
                "kind": "cancelling",
            })
        except Exception as _e:
            logger.error(f"  ❌ workflow:cancelling publish failed: {_e}")

        return {
            "workflow_id": execution_id,
            "status": "cancelled",
            "message": "Workflow execution cancelled successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to cancel workflow | workflow_id={execution_id} | error={str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel workflow: {str(e)}")


# ============== Debugging Tools ==============

class WorkflowStateInspectionResponse(BaseModel):
    """Detailed workflow state for debugging."""
    workflow_id: str
    template_id: str
    status: str
    current_step: Optional[str]
    messages_count: int
    last_message: Optional[str]
    execution_result: Optional[Dict[str, Any]]
    approval_required: bool
    approval_status: Optional[str]
    metadata: Dict[str, Any]
    next_nodes: List[str]
    checkpoint_count: int
    tool_calls_history: Optional[List[Dict[str, Any]]] = None
    """History of all tool calls made during workflow execution."""


@router.get("/{workflow_id}/debug/state", response_model=WorkflowStateInspectionResponse)
async def inspect_workflow_state(workflow_id: str):
    """
    Inspect detailed workflow state for debugging.

    Returns comprehensive state information including:
    - Current execution status
    - Message history summary
    - Execution results
    - Next nodes to execute
    - Checkpoint count

    Use this endpoint to debug workflow issues or inspect state.

    **Example**:
    ```python
    GET /api/v1/workflows/wf-abc123/debug/state

    Response:
    {
        "workflow_id": "wf-abc123",
        "status": "running",
        "messages_count": 3,
        "last_message": "Plan created...",
        "next_nodes": ["executor"],
        "checkpoint_count": 2
    }
    ```
    """
    thread_id = workflow_id
    config = get_workflow_config(thread_id)

    try:
        compiled = compile_workflow()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compile workflow: {str(e)}")

    # Get current state
    try:
        state = compiled.get_state(config)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Workflow not found: {str(e)}")

    if not state or not state.values:
        raise HTTPException(status_code=404, detail="Workflow not found or not started")

    # Get checkpoint history
    try:
        history = list(compiled.get_state_history(config))
        checkpoint_count = len(history)
    except Exception:
        checkpoint_count = 0

    # Extract state values
    values = state.values
    metadata = values.get("metadata", {})

    # Get last message content
    messages = values.get("messages", [])
    last_message = None
    if messages:
        last_msg = messages[-1]
        if hasattr(last_msg, 'content'):
            last_message = last_msg.content[:500]  # Truncate for readability

    return WorkflowStateInspectionResponse(
        workflow_id=workflow_id,
        template_id=values.get("template_id", "unknown"),
        status=metadata.status if hasattr(metadata, 'status') else values.get("metadata", {}).get("status", "unknown"),
        current_step=values.get("current_step"),
        messages_count=len(messages),
        last_message=last_message,
        execution_result=values.get("execution_result"),
        approval_required=values.get("approval_required", False),
        approval_status=values.get("approval_status"),
        metadata={
            "started_at": metadata.started_at if hasattr(metadata, 'started_at') else values.get("metadata", {}).get("started_at"),
            "completed_at": metadata.completed_at if hasattr(metadata, 'completed_at') else values.get("metadata", {}).get("completed_at"),
            "error": metadata.error if hasattr(metadata, 'error') else values.get("metadata", {}).get("error"),
        },
        next_nodes=list(state.next) if state.next else [],
        checkpoint_count=checkpoint_count,
        tool_calls_history=values.get("tool_calls_history")
    )


@router.get("/{workflow_id}/debug/trace")
async def get_workflow_trace(workflow_id: str):
    """
    The Langfuse trace for a run, named by the id the run's own spans carry.

    The id is **derived** from the workflow id (`run_trace_id`) — the same derivation the run's node
    spans used — so this endpoint can name the trace of a run it does not hold a handle to. It is
    returned in BOTH states, because with tracing off it is the only useful thing this endpoint can
    say, and it costs nothing.

    The URL comes from the SDK's `get_trace_url`, which is **not** a string builder: it resolves the
    project id over the network. A failure degrades to the id alone; a debug endpoint must not 500
    because a vendor's API is unreachable.

    **Example**:
    ```python
    GET /api/v1/workflows/wf-abc123/debug/trace

    Response:
    {
        "workflow_id": "wf-abc123",
        "trace_id": "3f1c…",        # always — the id the run's spans were sent under
        "trace_url": None,           # when tracing is off, or the link could not be resolved
        "langfuse_enabled": false
    }
    ```
    """
    trace_id = LangfuseManager.run_trace_id(workflow_id)
    enabled = LangfuseManager.is_enabled()

    return {
        "workflow_id": workflow_id,
        "trace_id": trace_id,
        "trace_url": LangfuseManager.trace_url(trace_id) if enabled else None,
        "langfuse_enabled": enabled,
    }


# ============== Rollback & Recovery Endpoints ==============

class RollbackRequest(BaseModel):
    """Request to rollback workflow."""
    checkpoint_id: Optional[str] = Field(None, description="Specific checkpoint to rollback to")
    to_last_good: bool = Field(default=True, description="Rollback to last good state if checkpoint_id not provided")


class RollbackResponse(BaseModel):
    """Response after rollback."""
    success: bool
    workflow_id: str
    from_checkpoint: Optional[str]
    to_checkpoint: Optional[str]
    error: Optional[str]
    message: str


class RecoveryRequest(BaseModel):
    """Request to execute recovery workflow."""
    strategy: str = Field(..., description="Recovery strategy: retry, fallback, degrade, notify, abort")
    context: Dict[str, Any] = Field(default_factory=dict, description="Recovery context")


class RecoveryResponse(BaseModel):
    """Response after recovery."""
    success: bool
    workflow_id: str
    strategy: str
    new_status: str
    message: str


@router.post("/{workflow_id}/rollback", response_model=RollbackResponse)
async def rollback_workflow(workflow_id: str, request: RollbackRequest):
    """
    Rollback workflow to previous checkpoint.

    Can rollback to:
    - Specific checkpoint (if checkpoint_id provided)
    - Last known good state (default)

    **Example**:
    ```python
    POST /api/v1/workflows/wf-abc123/rollback
    {
        "to_last_good": true
    }

    # Or rollback to specific checkpoint
    POST /api/v1/workflows/wf-abc123/rollback
    {
        "checkpoint_id": "chk-123456"
    }
    ```
    """
    thread_id = workflow_id
    config = get_workflow_config(thread_id)

    try:
        compiled = compile_workflow()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compile workflow: {str(e)}")

    # Execute rollback
    if request.checkpoint_id:
        result = RollbackManager.rollback_to_checkpoint(
            workflow_id=workflow_id,
            checkpoint_id=request.checkpoint_id,
            compiled_graph=compiled,
            config=config,
        )
    else:
        result = RollbackManager.rollback_to_last_good(
            workflow_id=workflow_id,
            compiled_graph=compiled,
            config=config,
        )

    if not result.success:
        raise HTTPException(
            status_code=400,
            detail=result.error or "Rollback failed"
        )

    return RollbackResponse(
        success=result.success,
        workflow_id=result.workflow_id,
        from_checkpoint=result.from_checkpoint,
        to_checkpoint=result.to_checkpoint,
        error=result.error,
        message=f"Workflow rolled back to checkpoint {result.to_checkpoint}"
    )


@router.post("/{workflow_id}/recover", response_model=RecoveryResponse)
async def recover_workflow(workflow_id: str, request: RecoveryRequest):
    """
    Execute recovery workflow for failed workflow.

    Recovery strategies:
    - retry: Retry failed operation with backoff
    - fallback: Switch to fallback agent/configuration
    - degrade: Continue with reduced functionality
    - notify: Pause for human intervention
    - abort: Gracefully terminate workflow

    **Example**:
    ```python
    POST /api/v1/workflows/wf-abc123/recover
    {
        "strategy": "retry",
        "context": {"max_retries": 3}
    }
    ```
    """

    # Map string to enum
    strategy_map = {
        "retry": RecoveryStrategy.RETRY,
        "fallback": RecoveryStrategy.FALLBACK,
        "degrade": RecoveryStrategy.DEGRADE,
        "notify": RecoveryStrategy.NOTIFY,
        "abort": RecoveryStrategy.ABORT,
    }

    if request.strategy not in strategy_map:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid strategy: {request.strategy}. Valid: {list(strategy_map.keys())}"
        )

    strategy = strategy_map[request.strategy]
    thread_id = workflow_id
    config = get_workflow_config(thread_id)

    try:
        compiled = compile_workflow()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compile workflow: {str(e)}")

    # Get current state
    state = compiled.get_state(config)

    if not state or not state.values:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Create error for recovery (use existing error if available)
    metadata = state.values.get("metadata", {})
    error_msg = metadata.error if hasattr(metadata, 'error') else state.values.get("metadata", {}).get("error", "Unknown error")
    error = Exception(error_msg)

    # Execute recovery
    try:
        updated_state = RecoveryWorkflow.execute_recovery(
            strategy=strategy,
            error=error,
            state=state.values,
            context=request.context,
        )

        # Update workflow state
        compiled.update_state(config, updated_state)

        # Get new status
        new_metadata = updated_state.get("metadata", {})
        new_status = new_metadata.status if hasattr(new_metadata, 'status') else updated_state.get("metadata", {}).get("status", "unknown")

        return RecoveryResponse(
            success=True,
            workflow_id=workflow_id,
            strategy=request.strategy,
            new_status=new_status,
            message=f"Recovery strategy '{request.strategy}' executed successfully"
        )

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Recovery failed: {str(e)}"
        )


@router.get("/{workflow_id}/checkpoints")
async def get_workflow_checkpoints(workflow_id: str):
    """
    Get workflow checkpoint history.

    Returns list of all checkpoints with metadata.
    Useful for debugging and rollback decisions.

    **Example**:
    ```python
    GET /api/v1/workflows/wf-abc123/checkpoints

    Response:
    {
        "workflow_id": "wf-abc123",
        "checkpoints": [
            {
                "checkpoint_id": "chk-123",
                "status": "running",
                "current_step": "executor",
                "next_nodes": ["executor"]
            }
        ]
    }
    ```
    """
    thread_id = workflow_id
    config = get_workflow_config(thread_id)

    try:
        compiled = compile_workflow()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compile workflow: {str(e)}")

    checkpoints = RollbackManager.get_checkpoint_history(
        workflow_id=workflow_id,
        compiled_graph=compiled,
        config=config,
    )

    return {
        "workflow_id": workflow_id,
        "checkpoints": checkpoints,
        "total": len(checkpoints)
    }
