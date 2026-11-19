"""
Agent Chat API — JSON adapter for the cognitive pipeline.

Provides REST endpoints for agent-to-agent and script-to-agent communication
with structured JSON responses and full cognitive trace data.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.infrastructure.database.models import (
    ChatSession,
    ChatMessage,
    Agent,
    SystemFlag,
)
from app.services.cognitive_pipeline.trace_store import (
    get_session_trace as _trace_get_session,
    list_traces as _trace_list,
    get_traces_since as _trace_since,
    trace_metrics as _trace_metrics,
)
from app.services.cognitive_pipeline import (
    CognitivePipeline,
    AgentDescriptor,
    PipelineConfig,
    CognitiveResult,
)
from app.services.cognitive_pipeline.preset_service import (
    list_presets as _list_presets,
    get_preset as _get_preset,
    create_preset as _create_preset,
    update_preset as _update_preset,
    delete_preset as _delete_preset,
    export_presets as _export_presets,
    import_presets as _import_presets,
)
# THE ONE DECIDER (G-F): this path resolves its budget with the same function the main
# chat uses, so the number that runs here is the number the profile page declares.
from app.services.cognitive_pipeline.output_budget import (
    PATH_DEFAULT,
    declared_output_budget,
    log_effective_budget,
    resolve_output_budget,
)

from .schemas import (
    CreateSessionRequest,
    SendMessageRequest,
    UpdateStatusRequest,
    SessionResponse,
    MessageResponse,
    SendMessageResponse,
    TraceResponse,
    StatusResponse,
    CognitiveTraceSchema,
    CognitiveMetricsSchema,
    MemoryDeltaSchema,
    ComponentTraceSchema,
    PresetCreateRequest,
    PresetUpdateRequest,
    PresetResponse,
    PresetExportData,
    UIStateResponse,
    UIStateUpdateRequest,
    UINavigateRequest,
    UINavigateResponse,
    WSMessage,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent-chat", tags=["agent-chat"])


# ---------------------------------------------------------------------------
# Helpers for system_flags
# ---------------------------------------------------------------------------


EXTERNAL_ACCESS_KEY = "external_access_enabled"


# THE PER-SESSION SERIALIZATION (2026-08-30, the user's agent-chat
# audit): send_message's pipeline is unguarded — two quick messages
# to the same session ran CONCURRENTLY (the second's context read
# the history BEFORE the first's message was saved — the stale
# context, the agent-chat cousin of the Exa every-other bug). The
# lock serializes the same-session sends; each turn sees the
# previous one's message.
_session_locks: dict[int, asyncio.Lock] = {}


def _session_lock(session_id: int) -> asyncio.Lock:
    lock = _session_locks.get(session_id)
    if lock is None:
        lock = asyncio.Lock()
        _session_locks[session_id] = lock
    return lock


async def _get_system_flag(db: AsyncSession, key: str) -> Optional[str]:
    """Get a system flag value from the database."""
    result = await db.execute(
        select(SystemFlag).where(SystemFlag.key == key)
    )
    flag = result.scalar_one_or_none()
    return flag.value if flag else None


async def _set_system_flag(db: AsyncSession, key: str, value: str) -> None:
    """Set a system flag value in the database (upsert)."""
    result = await db.execute(
        select(SystemFlag).where(SystemFlag.key == key)
    )
    flag = result.scalar_one_or_none()
    if flag:
        flag.value = value
        flag.updated_at = datetime.utcnow()
    else:
        db.add(SystemFlag(key=key, value=value))
    await db.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _build_agent_descriptor(
    agent: Agent,
    cognitive_config: Optional[Dict[str, str]],
    db: Optional[AsyncSession] = None,
) -> AgentDescriptor:
    """Build an ``AgentDescriptor`` from a DB agent row and optional config.

    THE DESCRIPTOR CARRIES THE RESOLVER'S NUMBER (G-F). This path built its own
    descriptor and handed it straight to an executor, so the executors' own
    constructor defaults decided how much the answer could be — a number the profile
    page never showed and the log never recorded, on a path whose page claims the
    same declaration as the main chat. Resolving here means one function, one order,
    one number for both paths; the resolution is logged with the same line the main
    chat writes, so a turn on this path is now visible in the same place.

    A resolution that cannot read (no session, an unreadable driver) leaves
    ``output_budget`` None — the executor's default speaks, as before — and the
    reason is logged rather than swallowed.
    """
    budget: Optional[int] = None
    if db is not None:
        provider = getattr(agent, "provider", "") or ""
        model = getattr(agent, "model", "") or ""
        driver = f"{provider}/{model}" if provider else model
        try:
            from app.domain.providers.model_window import (
                resolve_model_thinking,
                resolve_model_window,
            )

            window = await resolve_model_window(db, provider, model)
            thinking = await resolve_model_thinking(db, provider, model)
            budget, reason = resolve_output_budget(
                agent,
                driver,
                thinking,
                PATH_DEFAULT,
                window.value if window is not None else None,
            )
            log_effective_budget(
                budget,
                budget,
                declared_output_budget(agent),
                reason,
                path=PATH_DEFAULT,
                model=driver,
            )
        except Exception as exc:  # noqa: BLE001 — a missing reading must not fail the turn
            logger.warning(
                "agent_chat: no resolver reading for agent %s (%s) — "
                "the executor's own default decides this turn",
                getattr(agent, "id", "?"),
                exc,
            )

    return AgentDescriptor(
        id=agent.id,
        name=agent.name,
        description=getattr(agent, "description", "") or "",
        provider=getattr(agent, "provider", "") or "",
        model=getattr(agent, "model", "") or "",
        system_prompt=getattr(agent, "system_prompt", "") or "",
        cognitive_config=cognitive_config or {},
        cognitive_profile_id=getattr(agent, "cognitive_profile_id", None),
        fallback_enabled=bool(getattr(agent, "fallback_enabled", False)),
        preferred_providers=list(getattr(agent, "preferred_providers", None) or []),
        output_budget=budget,
    )


def _build_pipeline_config(cognitive_config: Optional[Dict[str, str]]) -> PipelineConfig:
    """Build a ``PipelineConfig`` from an optional config dict."""
    if cognitive_config:
        return PipelineConfig.from_dict(cognitive_config)
    return PipelineConfig()


async def _resolve_agent_cognitive_config(
    db: AsyncSession,
    agent: Agent,
    session_override: Optional[Dict[str, str]],
) -> PipelineConfig:
    """Resolve the effective pipeline config for an agent.

    Resolution order (later overrides earlier):
    1. PipelineConfig code defaults
    2. Agent-level Cognitive Profile (from DB)
    3. Session-level overrides (request payload, if provided)
    """
    config = PipelineConfig()

    # Step 2: Resolve agent's cognitive profile
    if agent.cognitive_profile_id is not None:
        from app.infrastructure.database.models import CognitiveProfile
        from sqlalchemy.orm import selectinload

        stmt = (
            select(CognitiveProfile)
            .options(selectinload(CognitiveProfile.memory_profile))
            .where(CognitiveProfile.id == agent.cognitive_profile_id)
        )
        result = await db.execute(stmt)
        profile = result.scalar_one_or_none()
        if profile:
            config.context_builder = profile.context_builder
            config.executor = profile.executor
            config.memory_manager = profile.memory_profile.strategy if profile.memory_profile else "default"
            config.response_formatter = profile.response_formatter

    # Step 3: Session-level overrides take precedence
    if session_override:
        config = PipelineConfig.from_dict(session_override)

    return config


def _serialize_trace(result: CognitiveResult) -> CognitiveTraceSchema:
    """Serialize a ``CognitiveTrace`` to its Pydantic schema."""
    t = result.trace
    return CognitiveTraceSchema(
        context_builder=ComponentTraceSchema(
            strategy=t.context_builder.strategy,
            duration_ms=t.context_builder.duration_ms,
            tokens_used=t.context_builder.tokens_used,
            input_tokens=t.context_builder.input_tokens,
            output_tokens=t.context_builder.output_tokens,
            metadata=t.context_builder.metadata,
            error=t.context_builder.error,
        ),
        executor=ComponentTraceSchema(
            strategy=t.executor.strategy,
            duration_ms=t.executor.duration_ms,
            tokens_used=t.executor.tokens_used,
            input_tokens=t.executor.input_tokens,
            output_tokens=t.executor.output_tokens,
            metadata=t.executor.metadata,
            error=t.executor.error,
        ),
        memory_manager=ComponentTraceSchema(
            strategy=t.memory_manager.strategy,
            duration_ms=t.memory_manager.duration_ms,
            tokens_used=t.memory_manager.tokens_used,
            input_tokens=t.memory_manager.input_tokens,
            output_tokens=t.memory_manager.output_tokens,
            metadata=t.memory_manager.metadata,
            error=t.memory_manager.error,
        ),
        response_formatter=ComponentTraceSchema(
            strategy=t.response_formatter.strategy,
            duration_ms=t.response_formatter.duration_ms,
            tokens_used=t.response_formatter.tokens_used,
            input_tokens=t.response_formatter.input_tokens,
            output_tokens=t.response_formatter.output_tokens,
            metadata=t.response_formatter.metadata,
            error=t.response_formatter.error,
        ),
        total_duration_ms=t.total_duration_ms,
        total_tokens=t.total_tokens,
    )


def _serialize_metrics(result: CognitiveResult) -> CognitiveMetricsSchema:
    """Serialize ``CognitiveMetrics`` to its Pydantic schema."""
    m = result.metrics
    return CognitiveMetricsSchema(
        total_duration_ms=m.total_duration_ms,
        total_tokens=m.total_tokens,
        llm_calls=m.llm_calls,
        tool_calls=m.tool_calls,
        cache_hits=m.cache_hits,
    )


def _serialize_memory_delta(result: CognitiveResult) -> Optional[MemoryDeltaSchema]:
    """Serialize ``MemoryDelta`` to its Pydantic schema (or None)."""
    md = result.memory_delta
    if md is None:
        return None
    return MemoryDeltaSchema(
        stored_keys=md.stored_keys,
        evicted_keys=md.evicted_keys,
        compaction_triggered=md.compaction_triggered,
        summary=md.summary,
    )


def _message_to_schema(msg: ChatMessage) -> MessageResponse:
    """Convert a DB ``ChatMessage`` to a Pydantic ``MessageResponse``."""
    return MessageResponse(
        id=msg.id,
        role=msg.role,
        content=msg.content,
        token_count=msg.token_count,
        model=msg.model,
        provider=msg.provider,
        total_time_ms=msg.total_time_ms,
        metadata=msg.meta,
        created_at=msg.created_at,
    )


async def _get_session_or_404(
    db: AsyncSession, session_id: int
) -> ChatSession:
    """Fetch a session by ID or raise 404."""
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    return session


async def _get_agent_or_404(
    db: AsyncSession, agent_id: int
) -> Agent:
    """Fetch an agent by ID or raise 404."""
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found",
        )
    return agent


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/session",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new agent chat session",
)
async def create_session(
    request: CreateSessionRequest,
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    """Create a new chat session with an agent, optionally with cognitive config.

    The session is created in the ``chat_sessions`` table with ``source='agent'``
    to distinguish it from human UI sessions.
    """
    # Verify agent exists
    await _get_agent_or_404(db, request.agent_id)

    # Serialize cognitive config to JSON for storage
    cognitive_config_json: Optional[str] = None
    if request.cognitive_config:
        cognitive_config_json = json.dumps(request.cognitive_config)

    session = ChatSession(
        agent_id=request.agent_id,
        title=request.title or f"Agent Chat #{int(datetime.utcnow().timestamp())}",
        is_active=True,
        source="agent",
    )
    db.add(session)
    await db.flush()  # Get session.id without committing yet

    # Store cognitive config in session metadata if provided
    # We use a simple approach: store as JSON in a metadata column.
    # Since ChatSession doesn't have a dedicated cognitive_config column,
    # we'll store it via the RuntimeConfig or a simple approach.
    # For now, we store it in the session title as JSON prefix (temporary).
    # A proper migration will add a cognitive_config column later.
    if cognitive_config_json:
        session.title = f"{session.title}|cfg:{cognitive_config_json}"

    await db.commit()
    await db.refresh(session)

    return SessionResponse(
        id=session.id,
        agent_id=session.agent_id,
        title=session.title,
        is_active=session.is_active,
        cognitive_config=request.cognitive_config,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.post(
    "/message",
    response_model=SendMessageResponse,
    summary="Send a message and get a JSON response with cognitive trace",
)
async def send_message(
    request: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
) -> SendMessageResponse:
    """Send a message to an agent and receive a structured JSON response.

    The response includes:
    - The agent's response text
    - Full cognitive trace (per-component timing, tokens, metadata)
    - Performance metrics (LLM calls, tool calls, cache hits)
    - Memory delta (what changed in memory)

    The cognitive pipeline runs synchronously and returns all data in a
    single JSON response — no streaming.
    """
    # Fetch session
    session = await _get_session_or_404(db, request.session_id)

    # Fetch agent
    agent = await _get_agent_or_404(db, session.agent_id) if session.agent_id is not None else None
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Resolve effective pipeline config:
    # 1. Code defaults -> 2. Agent cognitive profile -> 3. Session overrides
    pipeline_config = await _resolve_agent_cognitive_config(
        db, agent, request.cognitive_config
    )

    # Build agent descriptor — with the RESOLVER's chain on it (R3)
    from app.services.cognitive_pipeline.chat_chain import attach as attach_chat_chain

    agent_desc = await attach_chat_chain(
        await _build_agent_descriptor(agent, request.cognitive_config, db), db, path="agent_chat"
    )

    # THE SERIALIZED TURN (2026-08-30): the same-session sends run
    # one at a time — the history read + the pipeline + the saves
    # inside the lock, so the second turn always sees the first's
    # message.
    async with _session_lock(session.id):
        # Fetch session history
        history_result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.created_at.asc())
        )
        session_messages = history_result.scalars().all()

        session_history: List[Dict[str, Any]] = [
            {"role": m.role, "content": m.content} for m in session_messages
        ]

        # The `memory` capability's chain — resolved HERE, where the session is (the pipeline holds
        # none, so it cannot resolve one and carries this answer instead). The memory manager is a
        # registered singleton; the chain travels on the turn's Context.
        from app.domain.providers.capabilities import resolve
        from app.domain.providers.embeddings import resolve_embedding_service
        from app.services.cognitive_pipeline.memory_manager import MEMORY_CAPABILITY_KEY

        memory_chain = await resolve(db, MEMORY_CAPABILITY_KEY)

        # The `embeddings` service — resolved HERE for the same reason: the pipeline's constructions
        # are sync and hold no session, and its `turn` vector store may not carry an embedding answer
        # of its own. An install that has configured no embedding model gets NO turn store, so the
        # pipeline's recall step skips (and says so) instead of embedding with a default.
        embedding = await resolve_embedding_service(db)

        # Run the cognitive pipeline
        pipeline = CognitivePipeline(embedding=embedding)
        result: CognitiveResult = await pipeline.run(
            user_message=request.message,
            agent=agent_desc,
            session_history=session_history,
            config=pipeline_config,
            capability_chains={MEMORY_CAPABILITY_KEY: memory_chain.candidates},
        )

        # Save the user message
        user_msg = ChatMessage(
            session_id=session.id,
            role="user",
            content=request.message,
        )
        db.add(user_msg)
        await db.flush()

        # Save the assistant response
        assistant_msg = ChatMessage(
            session_id=session.id,
            role="assistant",
            content=result.response,
            token_count=result.metrics.total_tokens if result.metrics else None,
            model=agent.model,
            provider=agent.provider,
            total_time_ms=float(result.metrics.total_duration_ms) if result.metrics else None,
        )
        db.add(assistant_msg)
        await db.flush()

        # Persist cognitive trace to dedicated pipeline_traces.db
        from app.services.cognitive_pipeline.trace_store import save_trace
        save_trace(
            result,
            session_id=session.id,
            message_id=assistant_msg.id,
        )

        # Update session timestamp
        session.updated_at = datetime.utcnow()

        await db.commit()

    return SendMessageResponse(
        session_id=session.id,
        message_id=assistant_msg.id,
        response=result.response,
        trace=_serialize_trace(result),
        metrics=_serialize_metrics(result),
        memory_delta=_serialize_memory_delta(result),
        error=result.error,
    )


@router.get(
    "/session/{session_id}/trace",
    response_model=TraceResponse,
    summary="Get the cognitive trace for a session",
)
async def get_session_trace(
    session_id: int,
    db: AsyncSession = Depends(get_db),
) -> TraceResponse:
    """Retrieve the cognitive trace data for a completed session.

    Returns the most recent trace stored in the ``cognitive_traces`` table.
    If no trace exists yet (session created but no messages sent), returns
    an empty trace structure.
    """
    session = await _get_session_or_404(db, session_id)

    # Fetch the most recent cognitive trace for this session from the
    # live trace store (pipeline_traces.db) — the main-DB table was
    # never written (DB cleanup Phase 1)
    trace_record = _trace_get_session(session.id)

    if trace_record is None:
        return TraceResponse(
            session_id=session.id,
            trace=CognitiveTraceSchema(),
            metrics=CognitiveMetricsSchema(),
            memory_delta=None,
        )

    # Deserialize stored JSON back into schema objects
    trace_data = json.loads(trace_record["trace_json"])
    trace_schema = CognitiveTraceSchema(**trace_data)

    metrics_schema = CognitiveMetricsSchema()
    if trace_record.get("metrics_json"):
        metrics_data = json.loads(trace_record["metrics_json"])
        metrics_schema = CognitiveMetricsSchema(**metrics_data)

    memory_delta_schema = None
    if trace_record.get("memory_delta_json"):
        memory_data = json.loads(trace_record["memory_delta_json"])
        memory_delta_schema = MemoryDeltaSchema(**memory_data)

    return TraceResponse(
        session_id=session.id,
        trace=trace_schema,
        metrics=metrics_schema,
        memory_delta=memory_delta_schema,
    )


@router.delete(
    "/session/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a session",
    response_model=None,
)
async def delete_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a session and all its messages."""
    session = await _get_session_or_404(db, session_id)

    await db.delete(session)
    await db.commit()


@router.get(
    "/status",
    response_model=StatusResponse,
    summary="Get external access status",
)
async def get_status(
    db: AsyncSession = Depends(get_db),
) -> StatusResponse:
    """Check whether external (agent-to-agent) access is currently enabled.

    Reads from the ``system_flags`` table so the value survives restarts.
    """
    value = await _get_system_flag(db, EXTERNAL_ACCESS_KEY)
    enabled = value is not None and value.lower() not in ("false", "0", "")
    return StatusResponse(enabled=enabled)


@router.put(
    "/status",
    response_model=StatusResponse,
    summary="Toggle external access",
)
async def update_status(
    request: UpdateStatusRequest,
    db: AsyncSession = Depends(get_db),
) -> StatusResponse:
    """Enable or disable external (agent-to-agent) access.

    Persists the value in the ``system_flags`` table so it survives restarts.
    """
    value = "true" if request.enabled else "false"
    await _set_system_flag(db, EXTERNAL_ACCESS_KEY, value)
    logger.info("External access %s", "enabled" if request.enabled else "disabled")
    return StatusResponse(enabled=request.enabled)


# ---------------------------------------------------------------------------
# REST endpoint: list historical traces
# ---------------------------------------------------------------------------


class TracesListResponse(BaseModel):
    """Response schema for listing historical cognitive traces."""

    traces: List[Dict[str, Any]]


@router.get(
    "/session/traces",
    summary="List historical cognitive traces",
)
async def list_traces(
    limit: int = Query(50, ge=1, le=200, description="Max traces to return"),
    db: AsyncSession = Depends(get_db),
) -> TracesListResponse:
    """Return the most recent cognitive traces across all sessions.

    Each entry includes the stored trace JSON, metrics JSON, memory delta,
    error, and timestamps — ready for the frontend history tab.
    """
    records = _trace_list(limit)

    traces: List[Dict[str, Any]] = []
    for r in records:
        trace_data = json.loads(r["trace_json"]) if r.get("trace_json") else {}
        metrics_data = json.loads(r["metrics_json"]) if r.get("metrics_json") else {}
        memory_data = json.loads(r["memory_delta_json"]) if r.get("memory_delta_json") else None

        traces.append({
            "id": r["id"],
            "session_id": r["session_id"],
            "message_id": r["message_id"],
            "trace": trace_data,
            "metrics": metrics_data,
            "memory_delta": memory_data,
            "error": r.get("error"),
            "created_at": r.get("created_at"),
        })

    return TracesListResponse(traces=traces)


# ---------------------------------------------------------------------------
# REST endpoint: aggregated performance metrics
# ---------------------------------------------------------------------------


class MetricsResponse(BaseModel):
    """Aggregated performance metrics across all cognitive pipeline runs."""

    total_runs: int
    avg_duration_ms: float
    max_duration_ms: float
    total_tokens: int
    avg_tokens_per_run: float
    total_llm_calls: int
    total_tool_calls: int
    total_cache_hits: int
    error_count: int
    avg_input_tokens: float
    avg_output_tokens: float


@router.get(
    "/metrics",
    response_model=MetricsResponse,
    summary="Get aggregated performance metrics",
)
async def get_metrics(
    db: AsyncSession = Depends(get_db),
) -> MetricsResponse:
    """Return aggregated performance metrics across all cognitive pipeline runs.

    Computes averages, totals, and error counts from the ``cognitive_traces``
    table.  Metrics are computed from the stored JSON fields so they reflect
    the actual pipeline performance.
    """
    m = _trace_metrics()
    return MetricsResponse(**m)


# ---------------------------------------------------------------------------
# SSE endpoint: real-time cognitive trace stream
# ---------------------------------------------------------------------------


@router.get(
    "/trace-stream",
    summary="SSE stream of cognitive trace events",
    response_class=StreamingResponse,
)
async def stream_cognitive_traces(
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """SSE endpoint that streams cognitive trace events in real-time.

    Polls the ``cognitive_traces`` table for new entries and emits them as
    SSE ``cognitive_trace_complete`` events.  The client receives a continuous
    stream of trace data as pipeline runs complete.
    """
    from app.api.v1.chat.cognitive_sse import emit_cognitive_trace_complete
    from app.services.cognitive_pipeline import (
        CognitiveResult,
        CognitiveTrace as PipelineTrace,
        CognitiveMetrics,
    )

    async def event_generator() -> AsyncGenerator[str, None]:
        last_id = 0
        poll_interval = 1.0  # seconds

        try:
            while True:
                # Poll for new traces from the live store (pipeline_traces.db)
                new_traces = _trace_since(last_id, limit=10)

                for trace_record in new_traces:
                    if trace_record["id"] > last_id:
                        last_id = trace_record["id"]

                    # Reconstruct a CognitiveResult from stored JSON
                    trace_data = json.loads(trace_record["trace_json"]) if trace_record.get("trace_json") else {}
                    metrics_data = json.loads(trace_record["metrics_json"]) if trace_record.get("metrics_json") else {}

                    pipeline_trace = PipelineTrace()
                    for comp in ("context_builder", "executor", "memory_manager", "response_formatter"):
                        if comp in trace_data:
                            getattr(pipeline_trace, comp).strategy = trace_data[comp].get("strategy", "unknown")
                            getattr(pipeline_trace, comp).duration_ms = trace_data[comp].get("duration_ms", 0)
                            getattr(pipeline_trace, comp).tokens_used = trace_data[comp].get("tokens_used", 0)
                            getattr(pipeline_trace, comp).input_tokens = trace_data[comp].get("input_tokens", 0)
                            getattr(pipeline_trace, comp).output_tokens = trace_data[comp].get("output_tokens", 0)
                            getattr(pipeline_trace, comp).metadata = trace_data[comp].get("metadata", {})
                            getattr(pipeline_trace, comp).error = trace_data[comp].get("error")

                    metrics = CognitiveMetrics(
                        total_duration_ms=metrics_data.get("total_duration_ms", 0),
                        total_tokens=metrics_data.get("total_tokens", 0),
                        llm_calls=metrics_data.get("llm_calls", 0),
                        tool_calls=metrics_data.get("tool_calls", 0),
                        cache_hits=metrics_data.get("cache_hits", 0),
                    )

                    trace_result = CognitiveResult(
                        response="",
                        trace=pipeline_trace,
                        metrics=metrics,
                        error=trace_record.get("error"),
                    )

                    yield emit_cognitive_trace_complete(trace_result)

                await asyncio.sleep(poll_interval)

        except asyncio.CancelledError:
            logger.info("Cognitive trace stream cancelled by client")
            return

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# WebSocket Bridge — UI State & Navigation
# ---------------------------------------------------------------------------

# In-memory store for the latest UI state snapshot.
# The frontend pushes its state here periodically; the WebSocket endpoint
# reads from it to broadcast to connected clients.
_latest_ui_state: Dict[str, Any] = {
    "current_route": "/",
    "sidebar_collapsed": False,
    "theater_mode_active": False,
    "active_agent_id": None,
    "active_agent_name": None,
    "active_session_id": None,
    "active_session_title": None,
    "theme": "light",
}

# Connected WebSocket clients
_ws_clients: List[WebSocket] = []


def _build_ui_state_response() -> UIStateResponse:
    """Build a ``UIStateResponse`` from the in-memory state store."""
    return UIStateResponse(
        current_route=_latest_ui_state.get("current_route", "/"),
        sidebar_collapsed=_latest_ui_state.get("sidebar_collapsed", False),
        theater_mode_active=_latest_ui_state.get("theater_mode_active", False),
        active_agent_id=_latest_ui_state.get("active_agent_id"),
        active_agent_name=_latest_ui_state.get("active_agent_name"),
        active_session_id=_latest_ui_state.get("active_session_id"),
        active_session_title=_latest_ui_state.get("active_session_title"),
        theme=_latest_ui_state.get("theme", "light"),
        timestamp=datetime.utcnow().isoformat(),
    )


async def _broadcast_ui_state() -> None:
    """Broadcast the current UI state to all connected WebSocket clients."""
    state = _build_ui_state_response()
    message = WSMessage(
        type="ui_state_update",
        payload=state.model_dump(),
        timestamp=datetime.utcnow().isoformat(),
    )
    payload = message.model_dump_json()

    disconnected: List[WebSocket] = []
    for client in _ws_clients:
        try:
            await client.send_text(payload)
        except Exception:
            disconnected.append(client)

    for client in disconnected:
        try:
            _ws_clients.remove(client)
        except ValueError:
            pass


@router.get(
    "/ui-state",
    response_model=UIStateResponse,
    summary="Get the current frontend UI state snapshot",
)
async def get_ui_state() -> UIStateResponse:
    """Return the current UI state snapshot.

    The state is maintained in-memory and updated by the frontend via
    periodic pushes or WebSocket messages.  This endpoint allows external
    agents / scripts to read the current UI state without a WebSocket
    connection.
    """
    return _build_ui_state_response()


@router.post(
    "/ui-state",
    response_model=UIStateResponse,
    summary="Update the UI state snapshot (called by frontend)",
)
async def update_ui_state(
    state: UIStateUpdateRequest,
) -> UIStateResponse:
    """Update the in-memory UI state snapshot.

    Called by the frontend (or any client) to push the current UI state
    to the backend.  Only the fields that are provided (not ``None``) will
    be updated.  The updated state is then broadcast to all connected
    WebSocket clients.
    """
    update_dict: Dict[str, Any] = {}
    if state.current_route is not None:
        update_dict["current_route"] = state.current_route
    if state.sidebar_collapsed is not None:
        update_dict["sidebar_collapsed"] = state.sidebar_collapsed
    if state.theater_mode_active is not None:
        update_dict["theater_mode_active"] = state.theater_mode_active
    if state.active_agent_id is not None:
        update_dict["active_agent_id"] = state.active_agent_id
    if state.active_agent_name is not None:
        update_dict["active_agent_name"] = state.active_agent_name
    if state.active_session_id is not None:
        update_dict["active_session_id"] = state.active_session_id
    if state.active_session_title is not None:
        update_dict["active_session_title"] = state.active_session_title
    if state.theme is not None:
        update_dict["theme"] = state.theme

    if update_dict:
        _latest_ui_state.update(**update_dict)

        # Broadcast updated state to all WebSocket clients
        await _broadcast_ui_state()

        logger.info(
            "UI state updated: route=%s sidebar=%s agent=%s session=%s",
            update_dict.get("current_route", _latest_ui_state.get("current_route")),
            update_dict.get("sidebar_collapsed", _latest_ui_state.get("sidebar_collapsed")),
            update_dict.get("active_agent_id", _latest_ui_state.get("active_agent_id")),
            update_dict.get("active_session_id", _latest_ui_state.get("active_session_id")),
        )

    return _build_ui_state_response()


@router.post(
    "/ui-navigate",
    response_model=UINavigateResponse,
    summary="Programmatically navigate the frontend to a route",
)
async def ui_navigate(
    request: UINavigateRequest,
) -> UINavigateResponse:
    """Request the frontend to navigate to a specific route.

    The navigation request is broadcast to all connected WebSocket clients.
    The frontend WebSocket handler will call ``window.history.pushState``
    (or ``replaceState`` if ``replace=True``) to perform the navigation.

    Returns immediately with a confirmation; the actual navigation happens
    asynchronously on the frontend.
    """
    # Broadcast navigation request to all WebSocket clients
    message = WSMessage(
        type="navigation_request",
        payload={"route": request.route, "replace": request.replace},
        timestamp=datetime.utcnow().isoformat(),
    )
    payload = message.model_dump_json()

    disconnected: List[WebSocket] = []
    for client in _ws_clients:
        try:
            await client.send_text(payload)
        except Exception:
            disconnected.append(client)

    for client in disconnected:
        try:
            _ws_clients.remove(client)
        except ValueError:
            pass

    logger.info(
        "Navigation request: route=%s replace=%s clients=%d",
        request.route,
        request.replace,
        len(_ws_clients),
    )

    return UINavigateResponse(
        success=True,
        route=request.route,
        message=f"Navigation to '{request.route}' broadcast to {len(_ws_clients)} client(s)",
    )


@router.websocket(
    "/ws",
)
async def ui_state_websocket(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time UI state push.

    Connected clients receive ``ui_state_update`` messages whenever the
    UI state changes.  Clients can also send ``navigation_request`` messages
    to request programmatic navigation.

    **Message types (server → client):**
    - ``ui_state_update`` — Full UI state snapshot
    - ``navigation_request`` — Request to navigate to a route

    **Message types (client → server):**
    - ``ui_state_update`` — Push current UI state to backend
    - ``ping`` — Keep-alive; server responds with ``pong``
    """
    await websocket.accept()
    _ws_clients.append(websocket)
    logger.info(
        "WebSocket client connected (%d total)", len(_ws_clients)
    )

    try:
        # Send the current state immediately on connect
        initial_state = _build_ui_state_response()
        welcome = WSMessage(
            type="ui_state_update",
            payload=initial_state.model_dump(),
            timestamp=datetime.utcnow().isoformat(),
        )
        await websocket.send_text(welcome.model_dump_json())

        while True:
            data = await websocket.receive_text()

            try:
                msg = json.loads(data)
                msg_type = msg.get("type", "")
                payload = msg.get("payload", {})

                if msg_type == "ping":
                    pong = WSMessage(
                        type="pong",
                        timestamp=datetime.utcnow().isoformat(),
                    )
                    await websocket.send_text(pong.model_dump_json())

                elif msg_type == "ui_state_update":
                    # Update in-memory state from client
                    if payload:
                        _latest_ui_state.update(
                            current_route=payload.get("current_route", _latest_ui_state["current_route"]),
                            sidebar_collapsed=payload.get("sidebar_collapsed", _latest_ui_state["sidebar_collapsed"]),
                            theater_mode_active=payload.get("theater_mode_active", _latest_ui_state["theater_mode_active"]),
                            active_agent_id=payload.get("active_agent_id", _latest_ui_state["active_agent_id"]),
                            active_agent_name=payload.get("active_agent_name", _latest_ui_state["active_agent_name"]),
                            active_session_id=payload.get("active_session_id", _latest_ui_state["active_session_id"]),
                            active_session_title=payload.get("active_session_title", _latest_ui_state["active_session_title"]),
                            theme=payload.get("theme", _latest_ui_state["theme"]),
                        )
                        # Broadcast to all other clients
                        await _broadcast_ui_state()

                elif msg_type == "navigation_request":
                    route = payload.get("route", "/")
                    replace = payload.get("replace", False)
                    logger.info(
                        "WebSocket navigation request: route=%s replace=%s",
                        route,
                        replace,
                    )
                    # Broadcast navigation to all clients
                    nav_msg = WSMessage(
                        type="navigation_request",
                        payload={"route": route, "replace": replace},
                        timestamp=datetime.utcnow().isoformat(),
                    )
                    nav_payload = nav_msg.model_dump_json()
                    for client in _ws_clients:
                        try:
                            await client.send_text(nav_payload)
                        except Exception:
                            pass

            except json.JSONDecodeError:
                logger.warning("Invalid JSON received on WebSocket: %s", data[:200])
                error_msg = WSMessage(
                    type="error",
                    payload={"detail": "Invalid JSON"},
                    timestamp=datetime.utcnow().isoformat(),
                )
                await websocket.send_text(error_msg.model_dump_json())

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.exception("WebSocket error: %s", str(e))
    finally:
        try:
            _ws_clients.remove(websocket)
        except ValueError:
            pass
        logger.info(
            "WebSocket client removed (%d remaining)", len(_ws_clients)
        )


# ---------------------------------------------------------------------------
# Preset CRUD endpoints
# ---------------------------------------------------------------------------


@router.get("/presets", response_model=List[PresetResponse])
async def get_presets(
    include_builtin: bool = Query(
        True, description="Include built-in presets in the list"
    ),
    db: AsyncSession = Depends(get_db),
):
    """List all cognitive configuration presets.

    Returns both built-in and user-created presets by default.
    Set ``include_builtin=false`` to see only user-created presets.
    """
    presets = await _list_presets(db, include_builtin=include_builtin)
    return presets


@router.get("/presets/{preset_id}", response_model=PresetResponse)
async def get_preset_by_id(
    preset_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a single cognitive configuration preset by ID."""
    preset = await _get_preset(db, preset_id)
    if preset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preset with id={preset_id} not found",
        )
    return preset


@router.post("/presets", response_model=PresetResponse, status_code=status.HTTP_201_CREATED)
async def create_preset(
    request: PresetCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new cognitive configuration preset."""
    try:
        preset = await _create_preset(
            db,
            name=request.name,
            description=request.description,
            context_builder=request.context_builder,
            executor=request.executor,
            memory_manager=request.memory_manager,
            response_formatter=request.response_formatter,
            config=request.config,
        )
        return preset
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.put("/presets/{preset_id}", response_model=PresetResponse)
async def update_preset(
    preset_id: int,
    request: PresetUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update an existing user-created cognitive configuration preset.

    Built-in presets cannot be modified.
    """
    try:
        preset = await _update_preset(
            db,
            preset_id,
            name=request.name,
            description=request.description,
            context_builder=request.context_builder,
            executor=request.executor,
            memory_manager=request.memory_manager,
            response_formatter=request.response_formatter,
            config=request.config,
        )
        if preset is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Preset with id={preset_id} not found",
            )
        return preset
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.delete("/presets/{preset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_preset(
    preset_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a user-created cognitive configuration preset.

    Built-in presets cannot be deleted.
    """
    try:
        deleted = await _delete_preset(db, preset_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Preset with id={preset_id} not found",
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.get("/presets/export/all", response_model=PresetExportData)
async def export_all_presets(
    preset_ids: Optional[str] = Query(
        None,
        description="Comma-separated list of preset IDs to export. Omit to export all.",
    ),
    db: AsyncSession = Depends(get_db),
):
    """Export presets as a JSON-serializable document.

    Optionally filter by comma-separated preset IDs.
    Useful for backup or transferring presets between instances.
    """
    ids: Optional[List[int]] = None
    if preset_ids:
        try:
            ids = [int(x.strip()) for x in preset_ids.split(",") if x.strip()]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid preset_ids format. Use comma-separated integers.",
            )

    export_data = await _export_presets(db, preset_ids=ids)
    return export_data


@router.post("/presets/import", response_model=List[PresetResponse])
async def import_presets(
    import_data: PresetExportData,
    overwrite: bool = Query(
        False,
        description="If true, overwrite existing presets with matching names",
    ),
    db: AsyncSession = Depends(get_db),
):
    """Import presets from a JSON export document.

    By default, skips presets whose names already exist.
    Set ``overwrite=true`` to replace existing presets.
    """
    try:
        imported = await _import_presets(
            db,
            import_data.model_dump(),
            overwrite=overwrite,
        )
        return imported
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
