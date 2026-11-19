---
title: Workflow Execution
type: atlas-page
path: frontend/src/pages/WorkflowExecution.tsx
confidence: high
updated: 2026-08-10
tags: [type/page, domain/atlas-ui]
---

# Workflow Execution

**Component**: `frontend/src/pages/WorkflowExecution.tsx`
**Route**: `/workflow-execution` (protected, `requiresAuth: true`, icon `play`, breadcrumb "Workflow Execution") — registered in `frontend/src/config/routes.ts` and linked from the sidebar navigation in `frontend/src/App.tsx` under the **Workflows** section (open by default, after Agents; nav label "Execution")
**Last Updated**: 2026-08-10

## Purpose

The **direct-execution model** ("do this thing now") — runs workflow templates (simple and multi-agent) and monitors their execution. The page lets the user pick a workflow template either directly or from a workflow list, supply input parameters, start/pause/stop/resume execution, and inspect live progress, step-level status, logs, and final results. Execution history is shown in a "Recent Executions" table (session-scoped: executions started on this page). It is the runtime counterpart of the [[WorkflowTemplates]] management page.

**Split (2026-08-10):** triggered execution ("keep doing this thing" — schedules, webhooks, per-trigger run history) moved to its own page: [[atlas/ui/pages/WorkflowAutomation|Workflow Automation]]. This page is the direct model only; the trigger control panel no longer lives here.

## Key Features

- Two selection modes via tabs: **All Templates** (direct template picker) and **From List** (pick a workflow list, then a workflow inside it)
- Template search filter (matches name, workflowType, category) with a category-grouped `<optgroup>` selector
- Selection persistence across reloads via `sessionStorage` (tab mode, list id, workflow id)
- Execution lifecycle controls — Start, Pause, Stop/Cancel, Resume — with status-driven enable/disable logic (Pause and Resume are stub handlers in `WorkflowRunner`; Stop calls the cancel API)
- Progress tracking: overall progress bar, per-step status rows, execution log stream, and step summary counters (Completed / Running / Failed / Total)
- Results viewer with **Outputs / Logs / Steps** tabs, per-output copy-to-clipboard, expandable log data, and JSON export (client-side Blob download)
- Recent Executions table (last 10 executions) with status badges, start time, duration, and result/error summary
- 2-second polling of execution status until a terminal state; an SSE progress stream client exists but is currently disabled (see Data Flow)

## Components Used

| Component | Path | Purpose |
|---|---|---|
| `ErrorBoundary` | `frontend/src/components/ErrorBoundary.tsx` | Wraps the whole page; catches render errors |
| `PageBanner` | `frontend/src/components/ui/PageBanner.tsx` | Page header banner — Help button in the `action` slot (no icon; consistent with Automation/Products) |
| `WorkflowRunner` | `frontend/src/components/features/workflowExecution/WorkflowRunner.tsx` | Main execution panel: configuration form, controls, progress, results, error alert |
| `ExecutionControls` | `frontend/src/components/features/workflowExecution/ExecutionControls.tsx` | Status display (icon + color) and Start/Pause/Resume/Stop buttons with enable/disable rules |
| `ProgressTracker` | `frontend/src/components/features/workflowExecution/ProgressTracker.tsx` | Overall progress bar, SSE connection badge, per-step progress, execution logs, step summary counters |
| `ResultViewer` | `frontend/src/components/features/workflowExecution/ResultViewer.tsx` | Tabbed results (Outputs/Logs/Steps), JSON export, copy-to-clipboard |

*(TriggerManagement was moved to the Automation page in the 2026-08-10 split.)*

## Hooks Used

| Hook | Path | Purpose |
|---|---|---|
| `usePageTitle` | `frontend/src/hooks/usePageTitle.ts` | Sets document title "Workflow Execution" and description |
| `useWorkflowTemplates` | `frontend/src/hooks/useWorkflowTemplates.ts` | Loads workflow templates (simple + multi-agent) and categories; exposes `templates`, `loading`, `error` |
| `useWorkflowLists` | `frontend/src/hooks/useWorkflowLists.ts` | Loads workflow lists for "From List" mode; exposes `workflowLists` |
| `useWorkflowExecution` | `frontend/src/hooks/useWorkflowExecution.ts` | Execution state and actions: `executeWorkflow`, `cancelExecution`, `retryExecution`, 2s polling loop, SSE disconnect registration; uses `useNotifications` for toasts |
| `useWorkflowProgress` | `frontend/src/hooks/useSSE.ts` | SSE hook (`type: 'workflow-progress'`) for real-time progress — currently hard-disabled; polling is the active mechanism |

## Data Flow

1. **Mount**: `useWorkflowTemplates` fetches templates via two parallel requests (`GET /api/v1/workflows/templates` and `GET /api/v1/multi-agent/templates`) and de-duplicates by id; `useWorkflowLists` fetches lists; `useWorkflowExecution` starts with an empty history. Selection state is rehydrated from `sessionStorage` keys `workflow_execution_selected_tab`, `workflow_execution_selected_list_id`, `workflow_execution_selected_workflow_id`.
2. **Selection (template mode)**: the page filters templates client-side by name/workflowType/category and groups them into `<optgroup>` by category; choosing one sets `selectedTemplate`.
3. **Selection (list mode)**: picking a list triggers `GET /api/v1/workflow-lists/{id}/workflows`; picking a workflow converts the `WorkflowInList` record into a synthetic `WorkflowTemplate` (empty steps/inputs, category `Custom`, default metadata) before it is passed to `WorkflowRunner`.
4. **Execute**: `WorkflowRunner` initializes input fields from `template.inputs[].defaultValue`, detects `workflowType` (`multi_agent` vs `simple`), and calls `executeWorkflow(templateId, inputs, workflowType)` → `POST /api/v1/workflows/execute` (or `/api/v1/multi-agent/execute`, 120s timeout). `workflowService` transforms the response (`workflow_id` → `id`, status `started` → `running`, synthetic `stepExecutions` + initial log entry). The result is prepended to `executions`, becomes `selectedExecution`, and a 2-second polling loop starts.
5. **Poll**: `GET /api/v1/workflows/{executionId}/status` replaces the execution in state on each tick (errors extracted from `execution_result.error_details`; `executionTime` computed from `started_at`/`completed_at`). Terminal statuses (`completed`, `failed`, `cancelled`, `error`) stop polling, fire success/error toasts via `useNotifications`, and `WorkflowRunner` invokes `onExecutionComplete` / `onExecutionError`.
6. **SSE (disabled)**: `useWorkflowProgress` targets `SSEClientFactory.createWorkflowProgressClient` (`/api/v1/workflows/{id}/progress`), but the hook hard-sets `enabled=false` because the backend SSE endpoint is not implemented — progress therefore renders from polled data. If SSE data arrived (`stepId`, `message`), `ProgressTracker` would update the current step and append log lines.
7. **Cancel**: Stop button → `cancelExecution` → `POST /api/v1/workflows/executions/{executionId}/cancel`; status is set to `cancelled` locally, polling and the SSE disconnect are torn down, and a warning toast is shown.
8. **History**: the Recent Executions table renders `executions.slice(0, 10)` with status badges, localized timestamps, and duration (`executionTime` or computed from `startedAt`/`completedAt`).

## State Management

No global store (no Redux/Zustand) — all state is local `useState` in the page plus hook-held state:

- **Page**: `selectionMode`, `templateFilter`, `selectedListId`, `listWorkflows`, `workflowsLoading`, `selectedTemplate`
- **useWorkflowTemplates**: `templates`, `filteredTemplates`, `filters`, `loading`, `error`, `categories`, `tags`, `selectedTemplate` (+ react-hook-form form for CRUD used on the Templates page)
- **useWorkflowLists**: `workflowLists`, `filteredLists`, `loading`, `error`, `selectedList`, `selectedListWorkflows`, `tags`, `filterTags` (+ react-hook-form form)
- **useWorkflowExecution**: `executions`, `selectedExecution`, `loading`, `error`, `polling`; refs `pollingIntervalRef` and `disconnectSSERef`; react-hook-form execution form
- **sessionStorage** (persistence only): `workflow_execution_selected_tab`, `workflow_execution_selected_list_id`, `workflow_execution_selected_workflow_id`

## API Endpoints Called

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/workflows/templates` | List simple workflow templates (via `useWorkflowTemplates` → `workflowService.getTemplates`) |
| GET | `/api/v1/multi-agent/templates` | List multi-agent workflow templates; merged and de-duplicated with simple templates |
| GET | `/api/v1/workflows/templates/categories` | Template categories and tags (used for selector grouping) |
| POST | `/api/v1/workflows/execute` | Start a simple workflow execution (120s timeout; response normalized to `WorkflowExecution`) |
| POST | `/api/v1/multi-agent/execute` | Start a multi-agent workflow execution (used when `template.workflowType === 'multi_agent'`) |
| GET | `/api/v1/workflows/{executionId}/status` | Poll execution status every 2s until a terminal status |
| POST | `/api/v1/workflows/executions/{executionId}/cancel` | Cancel/stop a running execution (Stop button) |
| POST | `/api/v1/workflows/executions/{executionId}/retry` | Retry a failed execution — exposed by `useWorkflowExecution`, not currently wired to page UI |
| GET | `/api/v1/workflow-lists` | List workflow lists ("From List" mode) |
| GET | `/api/v1/workflow-lists/{id}/workflows` | Workflows contained in a selected list |
| GET (SSE) | `/api/v1/workflows/{workflowId}/progress` | Real-time progress stream via `SSEClientFactory.createWorkflowProgressClient` — client exists and is wired through `useWorkflowProgress` but is disabled; polling is the active mechanism |

## Related Pages

- [[WorkflowTemplates]] — management counterpart (create/edit templates and lists); the "Manage Workflows" button navigates to `/workflow-templates`, and both pages share `workflowService`, `workflowListsService`, `useWorkflowTemplates`, and `useWorkflowLists`
