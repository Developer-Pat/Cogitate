---
title: useSSE
type: atlas-hook
path: frontend/src/hooks/useSSE.ts
confidence: high
updated: 2026-08-01
tags: [type/hook, domain/atlas-ui]
---

# useSSE

**Path**: `frontend/src/hooks/useSSE.ts`
**Type**: hook

## Purpose

Family of React hooks wrapping the `SSEClient` service for consuming Server-Sent Events (SSE) streams from the backend. The generic `useSSE` hook owns the full lifecycle of a single connection (create client → connect → message/error/open/close → disconnect) and exposes connection state to components. Four convenience wrappers pre-configure it for the supported stream types: `useLLMStream`, `useWorkflowProgress`, `useSystemMetrics`, `useLogStream`.

Stream types: `llm-stream`, `workflow-progress`, `system-metrics`, `log-stream`. When `url` is provided, `useSSE` connects directly to that endpoint; otherwise it delegates to `SSEClientFactory` to build a pre-configured client from `type` (+ required `sessionId` / `workflowId`).

> **Note**: `useWorkflowProgress` hardcodes `enabled: false` — the backend SSE endpoint for workflow progress is not implemented, so progress tracking falls back to polling via `useWorkflowExecution`.

## Exported API

### Shared types

```ts
// imported from ../services/sseClient
export interface SSEEvent {
  id?: string;
  event?: string;
  data: string;   // typed as string; JSON payloads are JSON.parse'd at runtime in SSEClient
  retry?: number;
}

export interface UseSSEOptions {
  url?: string       // custom endpoint; takes precedence over `type`
  type?: 'llm-stream' | 'workflow-progress' | 'system-metrics' | 'log-stream'
  sessionId?: string     // required for 'llm-stream'
  workflowId?: string    // required for 'workflow-progress'
  enabled?: boolean      // default true; when false no client is created
  onMessage?: (event: SSEEvent) => void
  onError?: (error: Event) => void
  onOpen?: () => void
  onClose?: () => void
}

export interface UseSSEReturn {
  data: SSEEvent | null                        // latest message payload
  error: Event | null                          // last connection error
  status: 'idle' | 'connecting' | 'connected' | 'error' | 'closed'
  connect: () => void                          // (re)create client and connect
  disconnect: () => void                       // disconnect and clear the client ref
  isConnected: boolean                         // derived: status === 'connected'
}
```

### useSSE

```ts
export function useSSE(options: UseSSEOptions = {}): UseSSEReturn
```

Generic hook. With `url`: `new SSEClient({ url, onMessage, onError, onOpen, onClose })`. With `type`: `SSEClientFactory.createLLMStreamClient(sessionId, handleMessage)`, `createWorkflowProgressClient(workflowId, handleMessage)`, `createSystemMetricsClient(handleMessage)`, or `createLogStreamClient(handleMessage)`. All client callbacks route into internal state handlers that update `data` / `error` / `status` and then forward to the user-supplied callbacks.

### useLLMStream

```ts
export function useLLMStream(sessionId: string, onMessage?: (event: SSEEvent) => void)
```

Wrapper for `useSSE({ type: 'llm-stream', sessionId, onMessage })`. Missing `sessionId` logs an error via `frontendLoggingService` and returns no client (status stays `idle`). Endpoint: `${baseUrl}/api/v1/chat/stream?session_id=${sessionId}`.

### useWorkflowProgress

```ts
export function useWorkflowProgress(
  workflowId: string,
  onMessage?: (event: SSEEvent) => void,
  _enabled: boolean = true
)
```

Wrapper for `type: 'workflow-progress'`. The third `_enabled` parameter is accepted but **ignored**: the hook hardcodes `const sseEnabled = false` and passes `enabled: false` to `useSSE` (backend SSE endpoint not yet implemented). Returns the standard `UseSSEReturn` shape, but status remains `idle` — progress is tracked by polling instead.

### useSystemMetrics

```ts
export function useSystemMetrics(onMessage?: (event: SSEEvent) => void)
```

Wrapper for `type: 'system-metrics'` (endpoint `${baseUrl}/api/v1/system/metrics`, retryInterval 5000ms, maxRetries 10).

> ⚠️ **Name collision**: `frontend/src/hooks/useSystemHealth.ts` also exports a polling-based `useSystemMetrics`, and `hooks/index.ts` re-exports **that** one. Consumers importing from `./hooks` / `hooks/index` get the polling version — the SSE variant must be imported from `../hooks/useSSE` directly.

### useLogStream

```ts
export function useLogStream(onMessage?: (event: SSEEvent) => void)
```

Wrapper for `type: 'log-stream'` (endpoint `${baseUrl}/api/v1/system/logs/stream`, retryInterval 3000ms, maxRetries 5).

### Default export

```ts
export default useSSE
```

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `react` (`useState`, `useEffect`, `useRef`, `useCallback`) | library | State (`data`/`error`/`status`), lifecycle effects, client ref (`sseClientRef`), stable callbacks |
| `../services/sseClient` → `SSEClient` | class | Wraps native `EventSource`; connect/disconnect, auto-reconnect (`retryInterval` default 3000ms, `maxRetries` default 5), JSON payload parsing, custom event listeners |
| `../services/sseClient` → `SSEClientFactory` | class | Builds pre-configured clients per stream type; `baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'` |
| `../services/sseClient` → `SSEEvent` | type | Incoming event shape `{ id?, event?, data, retry? }` |
| `../services/frontendLoggingService` | service | Error/debug/warning logging under the `useSSE` prefix |

### SSEClientFactory wiring (endpoints + retry config)

| Factory method | Endpoint | retryInterval | maxRetries |
|---|---|---|---|
| `createLLMStreamClient(sessionId, onMessage)` | `${baseUrl}/api/v1/chat/stream?session_id=${sessionId}` | 2000ms | 3 |
| `createWorkflowProgressClient(workflowId, onMessage)` | `${baseUrl}/api/v1/workflows/${workflowId}/progress` | 3000ms | 5 |
| `createSystemMetricsClient(onMessage)` | `${baseUrl}/api/v1/system/metrics` | 5000ms | 10 |
| `createLogStreamClient(onMessage)` | `${baseUrl}/api/v1/system/logs/stream` | 3000ms | 5 |

## Usage Example

```tsx
import { useSSE, useLLMStream, useSystemMetrics } from '../hooks/useSSE'

// 1. Generic hook with a custom URL
function Notifications() {
  const { data, error, status, connect, disconnect, isConnected } = useSSE({
    url: '/api/v1/notifications/stream',
    onOpen: () => console.log('stream opened'),
    onMessage: (evt) => console.log('event data:', evt.data),
  })

  return (
    <div>
      <span>Status: {status} {isConnected ? '(live)' : ''}</span>
      <button onClick={connect}>Connect</button>
      <button onClick={disconnect}>Disconnect</button>
      {error && <p>Error: {error.type}</p>}
      {data && <pre>{JSON.stringify(data.data)}</pre>}
    </div>
  )
}

// 2. Pre-configured LLM streaming for a chat session
function ChatStream({ sessionId }: { sessionId: string }) {
  const { data, status } = useLLMStream(sessionId, (evt) => {
    console.log('token chunk:', evt.data)
  })
  return status === 'connected' ? <div>Live: {String(data?.data)}</div> : <div>{status}</div>
}

// 3. SSE-based system metrics (import from useSSE directly — see name-collision note)
const metrics = useSystemMetrics()
```

## State / Data Flow

- **Status lifecycle**: starts `idle` → `connect()` sets `connecting` → client `onopen` → `connected` (clears `error`) → client `onerror` → `error` → `disconnect()` or client `onclose` → `closed`. `isConnected` is derived as `status === 'connected'`.
- **Client creation** (`createClient`): returns `null` when `enabled` is false, when neither `url` nor `type` is given, when required IDs are missing (`sessionId` for `llm-stream`, `workflowId` for `workflow-progress`), or on an unknown `type`. Thrown errors are logged and set `status: 'error'`. The live client is kept in `sseClientRef`.
- **Auto-connect effect**: on mount and whenever `enabled` flips, calls `connect()` (or `disconnect()`); the effect cleanup disconnects on unmount. `connect`/`disconnect` are stable via `useCallback`.
- **Reconnect-on-config-change effect**: when `url` / `type` / `sessionId` / `workflowId` change while `isConnected`, the hook disconnects and reconnects with the new config.
- **Callback wiring**: `handleMessage` stores the latest event in `data` then invokes `onMessage`; `handleError` stores it in `error` and sets `status: 'error'`; `handleOpen` sets `connected`; `handleClose` sets `closed`.
- **SSEClient reconnect behavior**: on error it retries up to `maxRetries` at `retryInterval`; if `EventSource.readyState === CLOSED` (e.g. 404 — workflow completed or endpoint missing) or retries are exhausted, it disconnects and fires `onClose`, which surfaces as `status: 'closed'`.

## Related

- `frontend/src/components/features/workflowExecution/WorkflowRunner.tsx` — consumes `useWorkflowProgress`; registers its `disconnect` with `useWorkflowExecution` via `setSSEDisconnect` so execution cleanup tears down the (currently dormant) SSE connection.
- `frontend/src/hooks/useWorkflowExecution.ts` — polling-based workflow progress (current fallback; exposes `setSSEDisconnect(disconnectFn)`).
- `frontend/src/components/features/monitoring/ConnectionStatus.tsx` — standalone badge component (`connected`/`connecting`/`error`/`closed` → badge colors) driven by the generic `useSSE`; not currently imported anywhere.
- `frontend/src/services/sseClient.ts` — `SSEClient`, `SSEClientFactory`, `SSEEvent`.
- `frontend/src/services/frontendLoggingService.ts` — logging used throughout the hook and client.
- ⚠️ `useSSE`'s `useSystemMetrics` is **not** re-exported from `frontend/src/hooks/index.ts`; the index's `useSystemMetrics` comes from `useSystemHealth.ts` (polling).
