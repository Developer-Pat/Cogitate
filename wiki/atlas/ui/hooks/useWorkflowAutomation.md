---
title: useWorkflowAutomation
type: atlas-hook
path: frontend/src/hooks/useWorkflowAutomation.ts
confidence: high
updated: 2026-08-10
tags: [type/hook, domain/atlas-ui]
---

# useWorkflowAutomation

**Hook**: `frontend/src/hooks/useWorkflowAutomation.ts`
**Used by**: [[atlas/ui/pages/WorkflowAutomation|Workflow Automation]] page

## Purpose

The triggered-execution model's data layer — manages the trigger
list, selection, and per-trigger run history. Wraps
`triggerService` + `workflowService`, following the established
page → hook → service convention (pages never call raw services;
the Workflow Execution page's hooks set the pattern).

## Returns

| Member | Type | Purpose |
|---|---|---|
| `triggers` | `TriggerInfoResponse[]` | All triggers (incl. inactive) |
| `selectedTrigger` | `string` | Currently selected trigger id |
| `runs` | `AutomationRun[]` | Run history for the selected trigger |
| `loadingRuns` | `boolean` | Run-history loading state |
| `selectTrigger` | `(id: string) => void` | Change the selected trigger |
| `refreshTriggers` | `() => Promise<void>` | Reload the trigger list (wired to the control panel's onRefresh) |

## Data Flow

- On mount: `refreshTriggers()` → `triggerService.getTriggers()`
  (`GET /api/v1/triggers?include_inactive=true`); first trigger
  auto-selected
- On `selectedTrigger` change: `workflowService.getExecutions(
  undefined, triggerId)` → `GET /api/v1/workflows/executions?
  trigger_id=...`; maps snake_case records to `AutomationRun`
  (id, templateId, status, startedAt, elapsed)
- Cancellation guard: a stale selection's in-flight fetch is
  discarded (the effect cleanup sets a `cancelled` flag)

## Related

- [[atlas/ui/pages/WorkflowAutomation|Workflow Automation]] — host page
- [[atlas/ui/hooks/useWorkflowExecution|useWorkflowExecution]] — the direct-model counterpart
- [[atlas/ui/services/domains/llm/workflowService|workflowService]]
