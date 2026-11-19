---
title: Trace Store
type: atlas-devnote
category: tracing
order: 5
confidence: medium
updated: 2026-08-09
tags: [type/dev-notes, domain/tracing]
---

# Trace Store

## Cognitive pipeline store

- **File**: pipeline_traces.db (data/pipeline_traces.db) — separate
  SQLite from cogitate.db. **The single cognitive-trace store** —
  the old main-DB `cognitive_traces` table was dropped (migration
  0056); reads now point here.
- **Purpose**: persist per-request pipeline traces without
  contention on the main DB.
- **TTL**: 30-day pruning on each write (same transaction as insert).
- **Store**: backend/app/services/cognitive_pipeline/trace_store.py.

## Backup

- pipeline_traces.db is included in DB backups (backup_db.py +
  supplemental copies — see backups/<ts>/).

## Trace record schema (cognitive pipeline)

`pipeline_traces.db` → table `cognitive_traces` (verified from
trace_store.py):

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK AUTOINCREMENT | |
| `session_id` | INTEGER NOT NULL | chat session |
| `message_id` | INTEGER | nullable |
| `trace_json` | TEXT NOT NULL | the full trace tree (serialized) |
| `metrics_json` | TEXT | metrics payload (latency, tokens) |
| `memory_delta_json` | TEXT | memory changes applied |
| `error` | TEXT | error message when the pipeline failed |
| `created_at` | DATETIME default CURRENT_TIMESTAMP | |

**tool_calls wired + LIVE-PROVEN (2026-08-14)**: `metrics.tool_calls`
is now filled at the `chat/stream` save site from REAL sources —
the ToolCallTracker counts every executed tool call
(`get_summary()["total_calls"]`); `executor_trace.metadata
["tool_iterations"]` is the fallback when no tracker exists
(delegate/stub paths). Filled BEFORE the SSE trace event + save,
so the live Debugging view and the DB both show the truth. 5
regression tests (test_tool_calls_metric.py). LIVE: local qwen3 +
Calculator via the app stream executed a real tool call and
persisted `tool_calls: 1` (trace id 16) — which required fixing an
Ollama/LiteLLM streaming bug first (see the Known Issues entry:
`ollama` provider forces format=json; remapped to `ollama_chat`
via `litellm_route.litellm_model_string()`). The cognitive pipeline's own
executors still don't set it (they call acompletion without
tools=) — that path stays 0 by design.

**Metrics dead-instrumentation fix (2026-08-13)**: before this,
`metrics_json` was structurally all-zeros — `pipeline.py` populated
`total_duration_ms`/`total_tokens` only on the FULL SUCCESS path
(every early return left them 0), and `llm_calls`/`tool_calls`/
`cache_hits` were never assigned anywhere. Fixed: a
`_finalize_metrics()` helper now runs on ALL 8 exit paths (duration/
tokens summed from whatever components ran; `llm_calls=1` when the
executor made a call — including failed attempts, whose strategy +
error land on the component trace). `tool_calls`/`cache_hits` have
NO source in the cognitive pipeline (executors call `acompletion`
without `tools=`; nothing reads cache info) — they stay 0 by
design, reserved for when the pipeline gains tool execution.
Verified live: a real run now persists `{total_duration_ms: 33973,
total_tokens: 389, llm_calls: 1}` (trace id 12), and
`GET /api/v1/agent-chat/metrics` aggregates real values.

**Query APIs** (repointed 2026-08-09 — DB cleanup Phase 1):
the agent-chat endpoints read from this store (they previously
queried a main-DB `cognitive_traces` table that nothing ever
wrote — the Debugging UI's trace view was effectively empty):
- `GET /api/v1/agent-chat/session/traces?limit=N` — recent traces
- `GET /api/v1/agent-chat/metrics` — aggregated pipeline metrics
- `GET /api/v1/agent-chat/trace-stream` — SSE live trace stream
The CognitiveTraceViewer + TraceAnalysis components (Debugging
page) consume these. The main-DB table was dropped in migration
0056; this file is the single source of trace records.
