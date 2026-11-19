---
title: Automated Trace Workflow
type: atlas-devnote
category: tracing
order: 2
confidence: stub
updated: 2026-08-05
tags: [type/dev-notes, domain/tracing]
---

# Automated Trace Workflow

How traces are captured automatically during chat/pipeline execution.

## Current shape

- Chat streaming captures tool calls via tool_call_tracker.py +
  cognitive_sse.py (SSE events carry trace data to the UI).
- Pipeline runs write to pipeline_traces.db via the cognitive
  pipeline trace store.

## Capture points (verified from router code)

1. **Chat stream** (`chat/router.py`, `_traced_stream`): a
   `TraceObservation` (kind="trace", id = session_id + timestamp)
   is recorded into the workflow ring-buffer store + Langfuse at
   stream start; tool calls are tracked by `tool_call_tracker.py`
   (start_chain/record_hop/complete_hop) and emitted via
   `cognitive_sse.py` events.
2. **Pipeline execution**: the cognitive pipeline writes completed
   traces to `pipeline_traces.db` via `trace_store.save_trace()`
   (with 30-day cleanup in the same transaction).
3. **SSE events the UI subscribes to**: `cognitive_context_built`,
   `cognitive_executor_started/progress/completed`,
   `cognitive_memory_updated`, `cognitive_response_formatted`,
   `cognitive_trace_complete` (see
   [[dev-notes/tracing/tracing-architecture|Tracing Architecture]]).
