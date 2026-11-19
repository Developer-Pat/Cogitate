---
title: ProgressTracker
type: atlas-component
path: frontend/src/components/features/workflowExecution/ProgressTracker.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# ProgressTracker

**Path**: `frontend/src/components/features/workflowExecution/ProgressTracker.tsx`
**Last Updated**: 2026-08-01

## Purpose

Displays live progress of a workflow execution: an overall progress bar (percentage), per-step status list (only when the execution has more than one step), a real-time connection status badge, execution logs, and a step-status count grid (completed / running / failed / total). It merges two data sources:

1. **Real SSE stream** — via the optional `progressData` prop (an `SSEEvent`), whose JSON payload (`stepId`, `message`) updates the current step and appends messages to the log panel in real time.
2. **Execution snapshot** — from the required `execution` prop (`WorkflowExecution`), used to compute the percentage and render step/stat/log fallback data when no SSE payload has arrived (or the stream is unavailable).

Progress percentage is computed from completed step executions when steps exist (`completed / total * 100`); for single-step workflows it falls back to the execution status (`completed` → 100, `running` → 50, otherwise 0). Uses daisyUI classes (`progress`, `badge`, `card`, Tailwind theme vars).

## Props Interface

```typescript
interface ProgressTrackerProps {
  execution: WorkflowExecution;
  progressData?: SSEEvent | null;
  progressStatus: 'idle' | 'connecting' | 'connected' | 'error' | 'closed';
  className?: string;
}
```

Supporting types (from `frontend/src/services/sseClient.ts` and `frontend/src/types/workflows.ts`):

```typescript
// frontend/src/services/sseClient.ts
export interface SSEEvent {
  id?: string;
  event?: string;
  data: string;
  retry?: number;
}

// frontend/src/types/workflows.ts
export interface WorkflowExecution {
  id: string;
  templateId: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  inputs: Record<string, unknown>;
  outputs?: Record<string, unknown>;
  startedAt?: string;
  completedAt?: string;
  error?: string;
  executionTime?: number;
  stepExecutions: StepExecution[];
  logs: ExecutionLog[];
  /** Raw execution_result from the backend API (result, agent_name, completed_at, error_details, etc.) */
  executionResult?: Record<string, unknown>;
}

export interface StepExecution {
  stepId: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  startedAt?: string;
  completedAt?: string;
  output?: unknown;
  error?: string;
  executionTime?: number;
  retryCount?: number;
}
```

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `react` (`useState`, `useEffect`) | Hook | Local state for current step and rolling log buffer; effect parses incoming SSE payloads |
| `react` (`ReactNode`) | Type | Casting dynamic step `output` / `executionResult` fields for safe JSX rendering |
| `frontendLoggingService` (`frontend/src/services/frontendLoggingService.ts`) | Service | Logs SSE payload parse errors (`ProgressTracker` context) |
| `WorkflowExecution`, `StepExecution` (`frontend/src/types/workflows.ts`) | Type | Execution snapshot and step status data |
| `SSEEvent` (`frontend/src/services/sseClient.ts`) | Type | Shape of the real-time workflow-progress stream payload |
| daisyUI / Tailwind theme vars | Styling | `progress`, `badge`, `card` components and `--card-*`, `--card-shadow` CSS variables |

**Data source note**: the component itself does not open the SSE connection. The real stream is created by the parent (`SSEClientFactory.createWorkflowProgressClient(workflowId, onMessage)` → `GET /api/v1/workflows/{workflowId}/progress`, with 3s retry / max 5 retries) and its events are forwarded via the `progressData` prop. If the stream is absent/closed, the component degrades to the `execution` snapshot; when running without SSE it shows *"Workflow executing... (SSE real-time updates not available)"*.

## Usage Example

```tsx
// Parent: frontend/src/components/features/workflowExecution/WorkflowRunner.tsx
import ProgressTracker from './ProgressTracker';

{selectedExecution && (
  <ProgressTracker
    execution={selectedExecution}
    progressData={progressData}      // SSEEvent | null, from the workflow-progress stream
    progressStatus={progressStatus}  // 'idle' | 'connecting' | 'connected' | 'error' | 'closed'
    className="mb-6"
  />
)}
```

## State Used

Local state (in component):

| State | Type | Initial | Purpose |
|---|---|---|---|
| `currentStep` | `string \| null` | `null` | `stepId` of the currently executing step, from the latest SSE payload; drives the "Currently executing..." hint |
| `progressLogs` | `string[]` | `[]` | Rolling buffer (last 100 entries) of `message` strings from SSE payloads; rendered as the Execution Logs list with timestamps |

Derived (no state): `overallProgress` from `calculateProgress()`; step status icons/colors and execution status color via helper switches.

## Related Components

- `frontend/src/components/features/workflowExecution/WorkflowRunner.tsx` — parent; owns the SSE workflow-progress stream and passes `execution`, `progressData`, `progressStatus`.
- `frontend/src/components/features/workflowExecution/ExecutionControls.tsx` — sibling; start/pause/stop/resume controls for the same execution.
- `frontend/src/components/features/workflowExecution/ResultViewer.tsx` — sibling; renders execution results below ProgressTracker.
- `frontend/src/services/sseClient.ts` — `SSEClient` / `SSEClientFactory.createWorkflowProgressClient`; the real-time data source feeding `progressData`.
