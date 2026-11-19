---
title: DatabaseTools
type: atlas-component
path: frontend/src/components/features/debugging/DatabaseTools.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# DatabaseTools

**Path**: `frontend/src/components/features/debugging/DatabaseTools.tsx`
**Last Updated**: 2026-08-01

## Purpose

Database debug tool for the Debugging page's Database tab. It lets a developer wipe all chat sessions and their messages from the backend database with one destructive action, and shows the equivalent command-line alternative (`python backend/scripts/clear_sessions.py`). The component is self-contained: it performs a raw `fetch` directly against the backend and does not go through any service or apiClient layer.

The file's docstring advertises three features ("Clear all sessions", "View database stats", "Reset database state"), but only the first is actually implemented. The component's sole network operation is `DELETE /api/v1/sessions/all`; there is no stats view and no separate reset action anywhere in the rendered UI — the other two docstring items are intent only.

## Props Interface

The component takes **no props** — `export function DatabaseTools()` accepts zero arguments. It is a **named export**, not a default export. The only type declaration in the file is the response shape for the delete operation, declared locally (not exported from `types/`):

```typescript
interface DeleteAllResponse {
  deleted: number[]
  failed: Array<{ id: number; reason: string }>
  total_requested: number
  total_deleted: number
  total_failed: number
}
```

## Dependencies

| Dependency | Type | Purpose |
| --- | --- | --- |
| `useState` (from `react`) | React hook | Only import in the file; drives the clear-session flow state (`isClearing`, `result`, `error`) |
| `fetch` (browser built-in) | Web API | Direct raw `DELETE` to `http://localhost:8000/api/v1/sessions/all` — the base URL is **hardcoded to localhost:8000**, no configured API base is used |
| `DeleteAllResponse` | Local interface | Typed shape of the DELETE response body, used for the `result` state |
| `traceService` | Referenced in comments only | `traceService.trace(...)` calls appear commented out (lines 35, 52-55, 59-61); the module is **not imported** — dead/commented code |
| DaisyUI + Tailwind classes | Styling | `card bg-base-100 shadow-xl`, `alert-warning` / `alert-error` / `alert-success`, `btn btn-error`, `loading loading-spinner` |

## Usage Example

Rendered by the Debugging page inside the Database tab (no props passed):

```tsx
// frontend/src/pages/Debugging.tsx (line ~182)
{activeTab === 'database' && (
  <div className="space-y-6">
    <DatabaseTools />
  </div>
)}
```

## State Used

All state is local `useState` — no stores, no context, no external selectors:

| State | Type | Purpose |
| --- | --- | --- |
| `isClearing` | `boolean` | True while the DELETE request is in flight; disables the button and swaps its label to a spinner + "Clearing..." |
| `result` | `DeleteAllResponse \| null` | Parsed DELETE response on success; drives the green success alert (shows `total_deleted`, plus `total_failed` when > 0) |
| `error` | `string \| null` | Error message on failure (`HTTP <status>: <statusText>` or the thrown message); drives the red error alert |

## Clear-Sessions Flow

1. User clicks the "🗑️ Clear All Sessions" button.
2. A `confirm()` dialog warns: "WARNING: This will delete ALL sessions and messages. This cannot be undone. Continue?" — the operation is aborted if the user dismisses it.
3. On confirm, the component fires a raw `fetch('http://localhost:8000/api/v1/sessions/all', { method: 'DELETE', headers: { 'Content-Type': 'application/json' } })`.
4. A non-OK response throws `HTTP <status>: <statusText>`, caught and stored in `error`.
5. On success the JSON body is parsed as `DeleteAllResponse` and stored in `result`; the success alert shows deleted/failed counts.
6. `finally` resets `isClearing` to `false`.
7. A second card offers the command-line alternative: `python backend/scripts/clear_sessions.py`.

## Related Components

- **Parent**: `frontend/src/pages/Debugging.tsx` — imports `DatabaseTools` (line 14) and renders it (line 184) when `activeTab === 'database'`.
- **Siblings** (other tab panels rendered by the same Debugging page, all in `frontend/src/components/features/debugging/`):
  - `BackendTraceViewer.tsx` — backend trace viewer (fetches `/api/v1/traces/traces`)
  - `CognitiveTraceViewer.tsx` — cognitive trace viewer (SSE at `/api/v1/agent-chat/trace-stream`)
  - `TraceAnalysis.tsx` — trace log analysis (polls `/api/v1/logs/recent?source=FlowTrace`)
  - `LogViewer.tsx`, `SystemDiagnostics.tsx`, `ErrorAnalysis.tsx`, `LiveMonitoring.tsx`, `TraceControls.tsx`, `DebugControls.tsx` — other debugging-panel components in the same folder
- **Backend counterpart**: `backend/scripts/clear_sessions.py` — the CLI script shown in the component's second card as an alternative to the UI action.
