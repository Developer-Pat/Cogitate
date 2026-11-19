---
title: Capability Error Handling
type: atlas-devnote
category: tools
order: 2
confidence: stub
updated: 2026-09-10
tags: [type/dev-notes, domain/tools]
---

# Capability Error Handling

How tool/agent capability failures are represented and surfaced.

## Current shape

- ToolExecutionResult wraps outcomes; failures surface as tool
  messages (to_user_message / to_summary_message) rather than
  crashing the chat stream.
- Capability error handling pattern: per-tool error responses
  converted to user-visible messages in the stream.

## Error taxonomy (execution_service.py)

| Case | Detection | Result |
|------|-----------|--------|
| **Not enabled** | `agent_tool` missing or `is_enabled=false` | `ToolExecutionResult(error="Tool 'X' is not enabled for this agent")` — warning logged |
| **Not found** | no DB record | `ToolExecutionResult(error="Tool 'X' not found in database")` |
| **Execution failure** | handler raises / returns error | `ToolExecutionResult(error=...)` — the error text |

## Permission-denied flow

- Agent path: `agent_tool_service.get_agent_tool_by_slug()` →
  not enabled → early return with error (fail-visible, no tool
  call).
- System-manager path (agent_id=None): skips the junction check;
  access via `ToolPermissionService` (tool_collection_permissions).

## UI rendering

Errors convert via `to_user_message()` → `tool_output` SSE event →
visible tool message in the stream (never silent). The capability
name + error text reach the user; the ErrorAnalysis debugging
component collects them for diagnosis.

> The topic guide is the guide only — validate against
> `execution_service.py` + `tool_permission_service` before writing.
> (The three error strings are pinned in the taxonomy above:
> "not enabled for this agent" at L309, "not found in database" at
> L260/L322.)
