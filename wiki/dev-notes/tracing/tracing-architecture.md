---
title: Tracing Architecture
type: atlas-devnote
category: tracing
order: 1
confidence: medium
updated: 2026-08-05
tags: [type/dev-notes, domain/tracing]
---

# Tracing Architecture

## Overview

Two tracing layers coexist:

1. **Cognitive pipeline traces** — persisted per-request pipeline
   traces in a dedicated **pipeline_traces.db** (SQLite, separate
   from cogitate.db and per-agent cognitive_memory.db, to avoid
   contention). TTL cleanup: traces older than 30 days are pruned on
   each write (one DELETE in the same transaction as the insert).
   Store: backend/app/services/cognitive_pipeline/trace_store.py.
2. **Workflow observability (LangGraph)** — one destination: **Langfuse**
   (backend/app/workflows/observability/langfuse_config.py), which is keyed and
   optional. With tracing off there is no local trace store and none is needed —
   a run's own record (status, `degraded`, the failure statement) is the app's
   local truth about it. Config: LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY /
   LANGFUSE_HOST / LANGFUSE_TRACING_ENABLED; `get_langfuse_handler()` links a
   graph run to its trace, `with_run_metadata()` gives that trace its session,
   name and tags. See [[dev-notes/tracing/langfuse|Langfuse Observability]].

## UI

The Debugging page (frontend/src/pages/Debugging.tsx) surfaces
traces via components in frontend/src/components/features/debugging/
(CognitiveTraceViewer, BackendTraceViewer, TraceControls,
TraceAnalysis, LiveMonitoring, ErrorAnalysis, SystemDiagnostics,
DatabaseTools, LogViewer).

## Trace event schema (cognitive SSE)

The chat stream emits cognitive events via `cognitive_sse.py`
(`_sse_event` → `event: <type>\ndata: <json>\n\n`):

| Event | Payload |
|-------|---------|
| `cognitive_context_built` | component, strategy, duration_ms (ComponentTrace) |
| `cognitive_executor_started` / `_progress` / `_completed` | executor phase state |
| `cognitive_memory_updated` | memory delta applied |
| `cognitive_response_formatted` | formatted response trace |
| `cognitive_trace_complete` | full trace summary |

Every payload is a ComponentTrace-derived JSON: `component`,
`strategy`, `duration_ms`, plus phase-specific fields. The UI
subscribes to these event names in the chat stream.

## How the layers relate to the UI viewers

- **Cognitive traces** (pipeline_traces.db, `cognitive_traces`
  table) → CognitiveTraceViewer + TraceAnalysis (Debugging page)
- **Workflow / agent traces** → **Langfuse**, when it is keyed (above). There is no
  local workflow-trace store. The Debugging page's `BackendTraceViewer` panel
  requests `/api/v1/traces`, which **no router serves** (404) — the panel lists
  nothing, and its source is a `frontend/src/components/features/debugging/`
  question rather than a tracing one.
- The SSE events give the live stream view during chat, the pipeline store gives
  the persisted history.
