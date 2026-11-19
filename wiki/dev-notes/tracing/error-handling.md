---
title: Error Handling & Recovery
type: atlas-devnote
category: tracing
order: 3
confidence: stub
updated: 2026-08-05
tags: [type/dev-notes, domain/tracing]
---

# Error Handling & Recovery

## Current shape

- Streaming errors surface as SSE error events (never silent
  truncation — the system surfaces failures visibly).
- Tool execution errors are wrapped into user-visible messages
  (ToolExecutionResult.to_user_message).
- ErrorAnalysis component (debugging UI) aggregates stream/trace
  errors for diagnosis.

## Error taxonomy

| Error class | Where it surfaces | UI presentation |
|-------------|-------------------|-----------------|
| **Provider failure** (timeout/5xx/bad key) | chat stream → SSE error event; usage_logs.success=false | error toaster + stream marked failed; health scan flags (3+ consecutive → warn) |
| **Tool execution failure** | `ToolExecutionResult` with error → wrapped by `to_user_message()` into a `tool_output` SSE event | visible tool message, never silent |
| **Stream abort** (client disconnect / cancel) | generator cancellation | stream ends; partial content retained |
| **Pipeline error** | `cognitive_traces.error` column populated | TraceAnalysis shows the failed trace |

## Retry semantics

- Provider calls: retried per the fallback chain when
  `fallback_enabled` (opt-in, default off) — each attempt logged.
- Tool execution: no automatic retry (fail-visible stance).
- Title generation: falls back to the fallback config on provider
  failure (degraded, observable).

## Key principle

Failures are **surfaced, never silent** — SSE error events, error
toasters, error badges, health warnings.
