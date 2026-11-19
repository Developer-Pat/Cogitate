---
title: WorkflowRunner
type: atlas-component
path: frontend/src/components/features/workflowExecution/WorkflowRunner.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---

# WorkflowRunner

**Path**: `frontend/src/components/features/workflowExecution/WorkflowRunner.tsx`
**Last Updated**: 2026-08-01

## Purpose

Top-level orchestrator component for executing a workflow template in the UI. It renders the workflow configuration form (template metadata + input parameters initialized from template defaults), wires the execution controls (start/stop/pause/resume) to the `useWorkflowExecution` hook, subscribes to real-time progress updates via SSE (`useWorkflowProgress`), and displays the live `ProgressTracker` and `ResultViewer` for the selected execution. It is the default export of the module and is the container that parents drop in to run a single `WorkflowTemplate`.

## Props Interface

```ts
interface WorkflowRunnerProps {
  template: WorkflowTemplate;
  onExecutionComplete?: (execution: WorkflowExecution) => void;
  onExecutionError?: (error: string) => void;
  className?: string;
}
```

- `template` (required): the workflow template to run; its `name`, `description`, and `inputs` drive the configuration card.
- `onExecutionComplete` (optional): invoked when the selected execution reaches `completed` status, with the final `WorkflowExecution`.
- `onExecutionError` (optional): invoked when the selected execution reaches `failed` status (or when starting an execution throws), with the error message string.
- `className` (optional, default `''`): appended to the root `workflow-runner` div.

## Dependencies

| Dependency | Type | Purpose |
| --- | --- | --- |
| `useWorkflowExecution` (`frontend/src/hooks/useWorkflowExecution.ts`) | custom hook | Supplies `executeWorkflow`, `cancelExecution`, `selectedExecution`, `loading`, `error`, `setSSEDisconnect`, `disconnectSSE`; owns the 2s polling loop and execution state |
| `useWorkflowProgress` (`frontend/src/hooks/useSSE.ts`) | custom hook | SSE stream for `workflow-progress` events keyed on `selectedExecution.id`; returns `data`, `status`, `disconnect`. Note: the backend SSE endpoint is not implemented yet, so the hook internally hard-disables SSE (`sseEnabled = false`) and progress is served by polling |
| `frontendLoggingService` (`frontend/src/services/frontendLoggingService.ts`) | service | Logs run lifecycle: start, completion, failure, cancellation, and progress events |
| `ExecutionControls` (`frontend/src/components/features/workflowExecution/ExecutionControls.tsx`) | component | Renders start/pause/stop/resume buttons wired to the local handlers |
| `ProgressTracker` (`frontend/src/components/features/workflowExecution/ProgressTracker.tsx`) | component | Renders live progress from `progressData` / `progressStatus` for the selected execution |
| `ResultViewer` (`frontend/src/components/features/workflowExecution/ResultViewer.tsx`) | component | Renders results of the selected execution |
| `WorkflowTemplate`, `WorkflowExecution` (`frontend/src/types/workflows.ts`) | types | Prop typing for template and execution payloads |

## Usage Example

```tsx
import { useState } from 'react';
import WorkflowRunner from '../components/features/workflowExecution/WorkflowRunner';
import type { WorkflowExecution, WorkflowTemplate } from '../types/workflows';

function WorkflowPage({ template }: { template: WorkflowTemplate }) {
  const [lastResult, setLastResult] = useState<WorkflowExecution | null>(null);
  const [lastError, setLastError] = useState<string | null>(null);

  return (
    <div>
      <WorkflowRunner
        template={template}
        onExecutionComplete={(execution) => setLastResult(execution)}
        onExecutionError={(error) => setLastError(error)}
        className="max-w-4xl mx-auto"
      />
      {lastResult && <p>Last run: {lastResult.id} ({lastResult.status})</p>}
      {lastError && <p className="text-error">{lastError}</p>}
    </div>
  );
}
```

## State Used

- **Local `useState`**: `executionInputs` (`Record<string, unknown>`) — initialized from `template.inputs[].defaultValue` in an effect keyed on `template`; updated per field via `handleInputChange`. `isExecuting` (boolean) — flips true around `executeWorkflow` and while a stop is in flight.
- **Hook state (`useWorkflowExecution`)**: `selectedExecution` — the active/current execution driving controls, progress, and results; `loading` — start/cancel in-flight flag combined into the controls' `isExecuting` prop; `error` — surfaced in the inline error alert.
- **SSE state (`useWorkflowProgress`)**: `progressData` (latest `SSEEvent`) and `progressStatus` (`'idle' | 'connecting' | 'connected' | 'error' | 'closed'`), passed to `ProgressTracker`. Enabled only when `selectedExecution?.id` is truthy.

## Run Orchestration

- **Start** (`handleStartExecution`): detects the workflow type by casting `template` to a record and checking `workflowType === 'multi_agent'` (defaults to `'simple'`), logs, then awaits `executeWorkflow(template.id, executionInputs, workflowType)`. On throw, logs and calls `onExecutionError` with the error message. Always resets `isExecuting` in `finally`.
- **Stop** (`handleStopExecution`): if `selectedExecution` exists, logs the termination request and awaits `cancelExecution(selectedExecution.id)`; otherwise logs that no active execution was found.
- **Pause / Resume** (`handlePauseExecution` / `handleResumeExecution`): not yet implemented — log a warning via `frontendLoggingService.warning` and no-op. (Wired to `ExecutionControls` for future use.)
- **Completion monitor** (effect on `selectedExecution` / callbacks): on `completed` → logs and calls `onExecutionComplete(selectedExecution)`; on `failed` → logs and calls `onExecutionError(selectedExecution.error || 'Execution failed')`; on `cancelled` → logs only.

## Progress Callback Wiring

`useWorkflowProgress(selectedExecution?.id || '', onMessage, !!selectedExecution?.id)` is called with an `onMessage` callback that debug-logs each progress event. The hook's `disconnect` function is registered into the execution hook via `setSSEDisconnect(disconnectProgress)` in an effect (deps: `disconnectProgress`, `setSSEDisconnect`) so that `useWorkflowExecution` can tear the stream down when an execution is cancelled (`disconnectSSE`). `progressData` and `progressStatus` flow into `ProgressTracker`; `disconnectSSE` from the hook is destructured but intentionally unused (aliased `_disconnectSSE`).

## API Calls

The component does not call the HTTP layer directly — all requests go through `useWorkflowExecution` → `workflowService` (`frontend/src/services/domains/llm/workflowService.ts`, base path `/api/v1/workflows`):

| Operation | Service method | Endpoint |
| --- | --- | --- |
| Start execution | `executeTemplate(templateId, inputs, workflowType)` | `POST /api/v1/workflows/.../execute` (execution creation) |
| Cancel execution | `cancelExecution(executionId)` | cancel endpoint under `/api/v1/workflows` |
| Status polling (every 2s, hook-owned) | `getExecution(executionId)` | execution detail endpoint under `/api/v1/workflows` |

Real-time progress via the `workflow-progress` SSE stream is wired but disabled on the backend side (see Dependencies), so the polling loop in `useWorkflowExecution` is the effective progress source.

## Related Components

- Parent/usage: pages embedding a workflow run flow (e.g. workflow detail/run views under `frontend/src/pages/`)
- `frontend/src/components/features/workflowExecution/ExecutionControls.tsx` — control buttons consumed here
- `frontend/src/components/features/workflowExecution/ProgressTracker.tsx` — live progress display
- `frontend/src/components/features/workflowExecution/ResultViewer.tsx` — result display
- `frontend/src/hooks/useWorkflowExecution.ts` — execution orchestration + polling hook
- `frontend/src/hooks/useSSE.ts` — `useWorkflowProgress` SSE hook
- `frontend/src/services/domains/llm/workflowService.ts` — API layer for execution endpoints
