---
title: Workflow Automation
type: atlas-page
path: frontend/src/pages/WorkflowAutomation.tsx
confidence: high
updated: 2026-08-10
tags: [type/page, domain/atlas-ui]
---

# Workflow Automation

**Component**: `frontend/src/pages/WorkflowAutomation.tsx`
**Route**: `/workflow-automation` (protected, `requiresAuth: true`, icon `refresh`, breadcrumb "Workflow Automation") — registered in `frontend/src/config/routes.ts` and linked from the sidebar navigation in `frontend/src/App.tsx` under the **Workflows** section (open by default, after Agents; nav label "Automation" — links omit the "Workflow" prefix since the section provides it)
**Last Updated**: 2026-08-10

## Purpose

The **triggered-execution model** ("keep doing this thing") — the
counterpart of the direct-model
[[atlas/ui/pages/WorkflowExecution|Workflow Execution]] page.
While the Execute page is a live session (interact DURING a run),
Automation is a control room (interact BETWEEN runs): set up
schedules/webhooks, activate or deactivate triggers, and monitor
each trigger's run history over time.

**Split rationale (2026-08-10):** tabs separate views of ONE
model; direct and triggered execution are TWO models with
different interaction rhythms. Splitting untangled a page that
mixed a live runner, a history log, and a control panel.

## Key Features

The page has **two tabs** (the two activities of the triggered
model — configure vs review):

- **🎛️ Triggers tab** (default): the TriggerManagement control
  table — ALL triggers (incl. inactive) with cron schedule, next
  run time, active state, and Activate/Deactivate toggles (see
  [[atlas/ui/components/features/workflows/TriggerManagement|TriggerManagement]]).
  Bounded list → plain page flow, no scroll machinery.
- **📊 History tab**: per-trigger run history — trigger selector
  (left) + run table (right). Uses the **collection pattern**
  (the WorkflowTable idiom): search box, status filter, and
  pagination (pageSize 20), because runs proliferate — a 5-min
  trigger alone produces 288 rows/day. Real execution records
  from `GET /workflows/executions?trigger_id=...` (run id,
  workflow, status badge, started time, duration).
- **History tab badge**: run count for the selected trigger.
- **Compact header**: no icon; Help button inline on the title
  row via `PageBanner`'s `action` slot (see
  [[atlas/ui/components/ui/PageBanner|PageBanner]]).

## Components Used

| Component | Path | Purpose |
|---|---|---|
| `ErrorBoundary` | `frontend/src/components/ErrorBoundary.tsx` | Wraps the whole page |
| `PageBanner` | `frontend/src/components/ui/PageBanner.tsx` | Page header banner — Help button in the `action` slot (no icon) |
| `TriggerManagement` | `frontend/src/components/features/workflows/TriggerManagement.tsx` | Full trigger control table (activate/deactivate, cron, next run) |
| `HelpButton` | `frontend/src/components/help` | Workflows help context |

## Hooks Used

| Hook | Path | Purpose |
|---|---|---|
| `usePageTitle` | `frontend/src/hooks/usePageTitle.ts` | Sets document title |
| `useWorkflowAutomation` | `frontend/src/hooks/useWorkflowAutomation.ts` | Trigger list + selection + per-trigger run loading; wraps `triggerService` + `workflowService` |

## Data Flow

1. **Mount**: `useWorkflowAutomation` calls `triggerService.getTriggers()`
   (`GET /api/v1/triggers?include_inactive=true` — shows ALL
   triggers, active and inactive). First trigger is auto-selected.
2. **Select trigger**: `selectTrigger(id)` sets the selection;
   the run-history effect calls `workflowService.getExecutions(
   undefined, triggerId)` → `GET /api/v1/workflows/executions?
   trigger_id=...` (reads `workflow_execution_history`; the
   scheduler records `input_data.trigger_id` on triggered runs).
3. **Control panel**: `TriggerManagement` lists the same triggers
   with schedule info from `GET /api/v1/triggers/schedules/list`,
   and toggles via `POST /api/v1/triggers/{id}/activate` /
   `deactivate`. Its `onRefresh` re-loads the selector.

## State Management

No global store — all state lives in `useWorkflowAutomation`:
`triggers`, `selectedTrigger`, `runs`, `loadingRuns`,
`selectTrigger`, `refreshTriggers`. The hook follows the
established page → hook → service convention (no raw service
calls in the component).

## API Endpoints Called

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/triggers?include_inactive=true` | List all triggers (selector + control panel) |
| GET | `/api/v1/triggers/schedules/list` | Schedule info incl. next run time |
| POST | `/api/v1/triggers/{id}/activate` | Activate a trigger |
| POST | `/api/v1/triggers/{id}/deactivate` | Deactivate a trigger |
| GET | `/api/v1/workflows/executions?trigger_id=...` | Per-trigger run history |

## Related

- [[atlas/ui/pages/WorkflowExecution|Workflow Execution]] — the direct model
- [[atlas/ui/components/features/workflows/TriggerManagement|TriggerManagement]]
- [[atlas/api/routers/workflows|Workflows API]] — execution + triggers endpoints
- [[dev-notes/workflows/monitor-family|Monitor Workflow Family]] — the first real triggers
