---
title: useWorkflowExecution
type: atlas-hook
path: frontend/src/hooks/useWorkflowExecution.ts
confidence: high
updated: 2026-08-01
tags: [type/hook, domain/atlas-ui]
---

# useWorkflowExecution

**Path**: `frontend/src/hooks/useWorkflowExecution.ts`
**Type**: hook

## Purpose

Manages the workflow execution lifecycle in the UI: starting a workflow execution (simple or multi-agent), fetching and selecting execution details, cancelling and retrying executions, and tracking live progress via a 2-second status polling loop. Also exposes SSE disconnect registration so consumers can hook real-time progress streams into the execution lifecycle (used by `WorkflowRunner`), and hosts the react-hook-form instance used to capture execution inputs. Note: pause/resume are NOT part of this hook's API — they are not yet implemented in the consuming `WorkflowRunner` component.

## Exported API

`useWorkflowExecution(): UseWorkflowExecutionReturn` — takes no arguments.

```ts
interface UseWorkflowExecutionReturn {
  // State
  executions: WorkflowExecution[];
  selectedExecution: WorkflowExecution | null;
  loading: boolean;
  error: string | null;
  polling: boolean;
  // Actions
  executeWorkflow: (templateId: string, inputs: Record<string, unknown>, workflowType?: 'simple' | 'multi_agent') => Promise<void>;
  getExecution: (executionId: string) => Promise<void>;
  cancelExecution: (executionId: string) => Promise<void>;
  retryExecution: (executionId: string) => Promise<void>;
  startPolling: (executionId: string) => void;
  stopPolling: () => void;
  setSSEDisconnect: (disconnectFn: () => void) => void;
  disconnectSSE: () => void;
  form: unknown; // UseFormReturn<WorkflowExecutionFormData> from react-hook-form
}
```

State and entity types (from `frontend/src/types/workflows.ts`):

```ts
interface WorkflowExecutionState {
  executions: WorkflowExecution[];
  selectedExecution: WorkflowExecution | null;
  loading: boolean;
  error: string | null;
  polling: boolean;
}

interface WorkflowExecution {
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
  executionResult?: Record<string, unknown>;
}
```

Form schema (Zod, `workflowExecutionFormSchema`):

```ts
{
  templateId: z.string().min(1, 'Template ID is required'),
  inputs: z.record(z.string(), z.any()),
}
// useForm defaultValues: { templateId: '', inputs: {} }
```

Behavior notes:

- `executeWorkflow` — calls `workflowService.executeTemplate`; validates the returned execution has an `id` (sets `error: 'Invalid workflow execution response'` and returns otherwise); prepends the new execution to `executions`, selects it, then calls `startPolling`. Failures set `error` and are logged via `frontendLoggingService`.
- `getExecution` — fetches one execution via `workflowService.getExecution` and sets it as `selectedExecution`.
- `cancelExecution` — calls `workflowService.cancelExecution`; on success it `stopPolling()`, `disconnectSSE()`, shows a `notifyWarning` toast ('Workflow Cancelled'), and marks the execution `status: 'cancelled'` in both `executions` and `selectedExecution`.
- `retryExecution` — calls `workflowService.retryExecution`; replaces the old execution with the returned one (prepended to `executions`), selects it, and starts polling for the new execution id.
- `startPolling` / `stopPolling` — manage the 2-second `window.setInterval` loop (see State / Data Flow).
- `setSSEDisconnect` / `disconnectSSE` — store a consumer-provided SSE disconnect callback in `disconnectSSERef`; `disconnectSSE` invokes it and nulls the ref.

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `workflowService` (`../services/domains/llm/workflowService`) | service singleton | All execution API calls: `executeTemplate`, `getExecution`, `cancelExecution`, `retryExecution` |
| `useNotifications` (`./useNotifications`) | hook | `notifyWarning` / `notifySuccess` toasts on cancel and on terminal poll status (completed) |
| `frontendLoggingService` (`../services/frontendLoggingService`) | service singleton | Structured logging of execution start / cancel / retry / poll events and errors |
| `useForm` (react-hook-form) + `zodResolver` (@hookform/resolvers) | library | Form state for execution inputs, validated against `workflowExecutionFormSchema` |
| `workflowExecutionFormSchema` (`../types/workflows`) | Zod schema | Validation of `{ templateId, inputs }` form data |
| `WorkflowExecutionState`, `UseWorkflowExecutionReturn`, `WorkflowExecutionFormData` (`../types/workflows`) | types | Hook state / return / form shapes |
| `useState`, `useEffect`, `useCallback`, `useRef` (react) | library | State, unmount cleanup, memoized callbacks, polling-interval + SSE-disconnect refs |

## Usage Example

```tsx
import { useWorkflowExecution } from '../hooks/useWorkflowExecution';

function ExecuteControls({ templateId }: { templateId: string }) {
  const {
    executions,
    selectedExecution,
    loading,
    error,
    polling,
    executeWorkflow,
    cancelExecution,
    retryExecution
  } = useWorkflowExecution();

  const handleStart = () =>
    executeWorkflow(templateId, { initial_message: 'Run from UI' });

  const handleStop = () => {
    if (selectedExecution) cancelExecution(selectedExecution.id);
  };

  return (
    <div>
      <button onClick={handleStart} disabled={loading || polling}>
        {loading ? 'Starting…' : 'Run workflow'}
      </button>
      {selectedExecution && selectedExecution.status === 'running' && (
        <button onClick={handleStop}>Stop</button>
      )}
      {selectedExecution?.status === 'failed' && (
        <button onClick={() => retryExecution(selectedExecution.id)}>Retry</button>
      )}
      {error && <p className="error">{error}</p>}
      <p>
        Status: {selectedExecution?.status ?? '—'} ({executions.length} executions)
      </p>
    </div>
  );
}
```

## State / Data Flow

- **Local state**: one `WorkflowExecutionState` object via `useState` (`executions`, `selectedExecution`, `loading`, `error`, `polling`). Every update uses the functional form `setState(prev => …)`.
- **Refs**: `pollingIntervalRef` holds the `window.setInterval` id; `disconnectSSERef` holds the consumer-registered SSE disconnect callback.
- **Polling loop**: `startPolling(executionId)` refuses invalid ids, clears any existing interval, sets `polling: true`, then runs `workflowService.getExecution(executionId)` every 2000 ms. Each tick replaces the matching entry in `executions` and updates `selectedExecution` when it matches. When a polled status is terminal (`completed`, `failed`, `cancelled`, `error`) the loop calls `stopPolling()`, computes elapsed time from `startedAt`/`completedAt`, logs a banner, and shows a `notifySuccess` toast ('Workflow Completed') for `completed`. Polling errors are logged but deliberately do not touch `error` state (to avoid disrupting UX). An unmount `useEffect` clears the interval.
- **API wiring** (via `workflowService`, base path `/api/v1/workflows`):
  - `POST /api/v1/workflows/execute` (simple) or `POST /api/v1/multi-agent/execute` (multi_agent) — `executeTemplate`, 120 s timeout, response normalized to the frontend `WorkflowExecution` shape (backend `started` → `running`, `workflow_id` → `id`).
  - `GET /api/v1/workflows/{executionId}/status` — `getExecution`, also used by the polling loop; response normalized the same way (error extraction from `error` / `execution_result.error_details.message`).
  - `POST /api/v1/workflows/executions/{executionId}/cancel` — `cancelExecution`.
  - `POST /api/v1/workflows/executions/{executionId}/retry` — `retryExecution`.
- **SSE workflow-progress integration**: the hook does not open SSE connections itself. `WorkflowRunner` calls `useWorkflowProgress` (from `hooks/useSSE.ts`, SSE event type `'workflow-progress'`) and registers its `disconnect` via `setSSEDisconnect`, so `cancelExecution` can tear the stream down with `disconnectSSE()`. Caveat: the workflow-progress SSE endpoint is not yet implemented on the backend — `useWorkflowProgress` hardcodes `sseEnabled = false`, so live progress currently comes from the 2 s polling loop and `disconnectSSE()` is effectively a no-op until the endpoint exists.

## Related

- `components/features/workflowExecution/WorkflowRunner.tsx` — primary consumer; wires `useWorkflowProgress` into `setSSEDisconnect`, drives `executeWorkflow` / `cancelExecution`, renders `ExecutionControls`, `ProgressTracker`, `ResultViewer`. Pause/resume handlers are not yet implemented here.
- `pages/WorkflowExecution.tsx` — consumes `executions` from the hook.
- `pages/WorkflowTemplates.tsx` — consumes the full hook return.
- `hooks/useSSE.ts` — `useWorkflowProgress` provides the (currently disabled) SSE progress stream that the hook's disconnect registration targets.
- `services/domains/llm/workflowService.ts` — all execution endpoints.
- `types/workflows.ts` — `WorkflowExecution`, `WorkflowExecutionState`, `UseWorkflowExecutionReturn`, `workflowExecutionFormSchema`.
