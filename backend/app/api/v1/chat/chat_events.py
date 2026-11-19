"""The chat-stream event contract (Step 1, 2026-08-24).

THE CONTRACT EXTRACTION (the chat-stream migration, step 1): the
cognitive pipeline's events move from bespoke SSE strings to TYPED
event builders — (topic, payload) dicts. The SSE formatter renders
the SAME dicts (the output is IDENTICAL — a pure refactor). The
bus migration (step 2) publishes the same contract.

TOPIC NAMING (the messaging convention, all-colon):
    chat:<session>:session_id
    chat:<session>:context_built
    chat:<session>:executor_started
    chat:<session>:executor_progress
    chat:<session>:executor_completed
    chat:<session>:memory_updated
    chat:<session>:response_formatted
    chat:<session>:trace_complete

The chunk/progress topics are HIGH-FREQUENCY — the bus publishes
them with record=False (no ring churn) in step 2.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from app.services.cognitive_pipeline.models import (
    CognitiveResult,
    ComponentTrace,
)

# the event kinds (the contract's vocabulary)
KIND_SESSION_ID = "session_id"
KIND_CONTEXT_BUILT = "context_built"
KIND_EXECUTOR_STARTED = "executor_started"
KIND_EXECUTOR_PROGRESS = "executor_progress"
KIND_EXECUTOR_COMPLETED = "executor_completed"
KIND_MEMORY_UPDATED = "memory_updated"
KIND_RESPONSE_FORMATTED = "response_formatted"
KIND_TRACE_COMPLETE = "trace_complete"


def chat_topic(session_id: str, kind: str) -> str:
    """The topic for a chat event (all-colon convention)."""
    return f"chat:{session_id}:{kind}"


def _component_to_data(component: ComponentTrace, name: str) -> Dict[str, Any]:
    """The shared component-trace shape (identical to cognitive_sse)."""
    return {
        "component": name,
        "strategy": component.strategy,
        "duration_ms": component.duration_ms,
        "tokens_used": component.tokens_used,
        "metadata": component.metadata,
        "error": component.error,
    }


# ---------------------------------------------------------------------------
# THE EVENT BUILDERS — (topic, payload) pairs
# ---------------------------------------------------------------------------

def build_session_id(session_id: str) -> Tuple[str, Dict[str, Any]]:
    return chat_topic(session_id, KIND_SESSION_ID), {"session_id": session_id}


def build_context_built(session_id: str, trace: ComponentTrace) -> Tuple[str, Dict[str, Any]]:
    return chat_topic(session_id, KIND_CONTEXT_BUILT), {
        "component": "context_builder",
        "strategy": trace.strategy,
        "duration_ms": trace.duration_ms,
        "tokens_used": trace.tokens_used,
        "sources": trace.metadata.get("sources", []),
        "error": trace.error,
    }


def build_executor_started(session_id: str, strategy: str) -> Tuple[str, Dict[str, Any]]:
    return chat_topic(session_id, KIND_EXECUTOR_STARTED), {
        "component": "executor",
        "strategy": strategy,
    }


def build_executor_progress(
    session_id: str,
    token_count: int = 0,
    tool_calls: int = 0,
    stage: str = "streaming",
) -> Tuple[str, Dict[str, Any]]:
    return chat_topic(session_id, KIND_EXECUTOR_PROGRESS), {
        "component": "executor",
        "token_count": token_count,
        "tool_calls": tool_calls,
        "stage": stage,
    }


def build_executor_completed(session_id: str, trace: ComponentTrace) -> Tuple[str, Dict[str, Any]]:
    return chat_topic(session_id, KIND_EXECUTOR_COMPLETED), {
        "component": "executor",
        "strategy": trace.strategy,
        "duration_ms": trace.duration_ms,
        "tokens_used": trace.tokens_used,
        "error": trace.error,
    }


def build_memory_updated(session_id: str, trace: ComponentTrace) -> Tuple[str, Dict[str, Any]]:
    return chat_topic(session_id, KIND_MEMORY_UPDATED), {
        "component": "memory_manager",
        "strategy": trace.strategy,
        "duration_ms": trace.duration_ms,
        "compaction_triggered": trace.metadata.get("compaction_triggered", False),
        "stored_keys": trace.metadata.get("stored_keys", []),
        "error": trace.error,
    }


def build_response_formatted(session_id: str, trace: ComponentTrace) -> Tuple[str, Dict[str, Any]]:
    return chat_topic(session_id, KIND_RESPONSE_FORMATTED), {
        "component": "response_formatter",
        "strategy": trace.strategy,
        "duration_ms": trace.duration_ms,
        "error": trace.error,
    }


def build_trace_complete(session_id: str, result: CognitiveResult) -> Tuple[str, Dict[str, Any]]:
    trace = result.trace
    return chat_topic(session_id, KIND_TRACE_COMPLETE), {
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
    }


# ---------------------------------------------------------------------------
# THE SSE FORMER (step 1: renders the contract -> the SAME SSE strings)
# ---------------------------------------------------------------------------

def sse_from_event(event_name: str, data: Dict[str, Any]) -> str:
    """Format a contract event as the SSE string (the current output)."""
    import json
    return f"event: {event_name}\ndata: {json.dumps(data)}\n\n"


# the legacy bridge (step 1 keeps the current call sites working):
# the event KIND -> the legacy SSE event NAME (the frontend contract)
_LEGACY_NAMES = {
    KIND_SESSION_ID: "session_id",
    KIND_CONTEXT_BUILT: "cognitive_context_built",
    KIND_EXECUTOR_STARTED: "cognitive_executor_started",
    KIND_EXECUTOR_PROGRESS: "cognitive_executor_progress",
    KIND_EXECUTOR_COMPLETED: "cognitive_executor_completed",
    KIND_MEMORY_UPDATED: "cognitive_memory_updated",
    KIND_RESPONSE_FORMATTED: "cognitive_response_formatted",
    KIND_TRACE_COMPLETE: "cognitive_trace_complete",
}


def sse_from_builder(builder_result: Tuple[str, Dict[str, Any]]) -> str:
    """Render a contract (topic, payload) as the legacy SSE string.

    The topic chat:<session>:<kind> -> the legacy event name. The
    OUTPUT IS IDENTICAL to the current cognitive_sse emitters — a
    pure refactor (the frontend contract unchanged).
    """
    topic, payload = builder_result
    kind = topic.rsplit(":", 1)[-1]
    name = _LEGACY_NAMES.get(kind, kind)
    return sse_from_event(name, payload)
