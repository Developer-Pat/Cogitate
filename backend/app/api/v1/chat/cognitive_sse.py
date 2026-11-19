"""
Cognitive SSE event emitter.

Provides helper functions to emit structured SSE events for the cognitive
pipeline stages. These events are consumed by the frontend to display
real-time cognitive indicators (badges, timing, trace data).

Event types defined in the architecture (v3):
    cognitive_context_built
    cognitive_executor_started
    cognitive_executor_progress
    cognitive_executor_completed
    cognitive_memory_updated
    cognitive_response_formatted
    cognitive_trace_complete  (aggregated trace at end)
"""

from __future__ import annotations

import json
from typing import Any, AsyncGenerator, Dict

from app.services.cognitive_pipeline.models import (
    CognitiveResult,
    ComponentTrace,
)


# ---------------------------------------------------------------------------
# SSE event formatting helpers
# ---------------------------------------------------------------------------

def _sse_event(event: str, data: Dict[str, Any]) -> str:
    """Format a single SSE event with event type and JSON data."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _component_to_event_data(
    component: ComponentTrace,
    component_name: str,
) -> Dict[str, Any]:
    """Convert a ComponentTrace to a JSON-serializable dict for SSE."""
    return {
        "component": component_name,
        "strategy": component.strategy,
        "duration_ms": component.duration_ms,
        "tokens_used": component.tokens_used,
        "metadata": component.metadata,
        "error": component.error,
    }


# ---------------------------------------------------------------------------
# Public emitter functions
# ---------------------------------------------------------------------------

def emit_cognitive_context_built(
    trace: ComponentTrace,
) -> str:
    """Emit event when Context Builder completes."""
    return _sse_event("cognitive_context_built", {
        "component": "context_builder",
        "strategy": trace.strategy,
        "duration_ms": trace.duration_ms,
        "tokens_used": trace.tokens_used,
        "sources": trace.metadata.get("sources", []),
        "error": trace.error,
    })


def emit_cognitive_executor_started(
    strategy: str,
) -> str:
    """Emit event when Executor begins."""
    return _sse_event("cognitive_executor_started", {
        "component": "executor",
        "strategy": strategy,
    })


def emit_cognitive_executor_progress(
    token_count: int = 0,
    tool_calls: int = 0,
    stage: str = "streaming",
) -> str:
    """Emit event during LLM streaming (progress updates)."""
    return _sse_event("cognitive_executor_progress", {
        "component": "executor",
        "token_count": token_count,
        "tool_calls": tool_calls,
        "stage": stage,
    })


def emit_cognitive_executor_completed(
    trace: ComponentTrace,
) -> str:
    """Emit event when Executor finishes."""
    return _sse_event("cognitive_executor_completed", {
        "component": "executor",
        "strategy": trace.strategy,
        "duration_ms": trace.duration_ms,
        "tokens_used": trace.tokens_used,
        "error": trace.error,
    })


def emit_cognitive_memory_updated(
    trace: ComponentTrace,
) -> str:
    """Emit event when Memory Manager completes."""
    return _sse_event("cognitive_memory_updated", {
        "component": "memory_manager",
        "strategy": trace.strategy,
        "duration_ms": trace.duration_ms,
        "compaction_triggered": trace.metadata.get("compaction_triggered", False),
        "stored_keys": trace.metadata.get("stored_keys", []),
        "error": trace.error,
    })


def emit_cognitive_response_formatted(
    trace: ComponentTrace,
) -> str:
    """Emit event when Response Formatter completes."""
    return _sse_event("cognitive_response_formatted", {
        "component": "response_formatter",
        "strategy": trace.strategy,
        "duration_ms": trace.duration_ms,
        "error": trace.error,
    })


def emit_cognitive_trace_complete(
    result: CognitiveResult,
) -> str:
    """Emit the full aggregated trace at the end of pipeline execution."""
    trace = result.trace
    return _sse_event("cognitive_trace_complete", {
        "trace": trace.to_dict(),
        "metrics": {
            "total_duration_ms": result.metrics.total_duration_ms,
            "total_tokens": result.metrics.total_tokens,
            "llm_calls": result.metrics.llm_calls,
            "tool_calls": result.metrics.tool_calls,
            "cache_hits": result.metrics.cache_hits,
        },
        "memory_delta": {
            "stored_keys": result.memory_delta.stored_keys if result.memory_delta else [],
            "evicted_keys": result.memory_delta.evicted_keys if result.memory_delta else [],
            "compaction_triggered": result.memory_delta.compaction_triggered if result.memory_delta else False,
        } if result.memory_delta else None,
        "error": result.error,
    })


# ---------------------------------------------------------------------------
# Async generator for streaming all cognitive events from a result
# ---------------------------------------------------------------------------

async def emit_all_cognitive_events(
    result: CognitiveResult,
) -> AsyncGenerator[str, None]:
    """Yield all cognitive SSE events from a completed pipeline result.

    This is useful for the JSON adapter or for replaying traces.
    For the live SSE stream, use the individual emit_* functions above
    at the appropriate points during pipeline execution.
    """
    yield emit_cognitive_context_built(result.trace.context_builder)
    yield emit_cognitive_executor_completed(result.trace.executor)
    yield emit_cognitive_memory_updated(result.trace.memory_manager)
    yield emit_cognitive_response_formatted(result.trace.response_formatter)
    yield emit_cognitive_trace_complete(result)
