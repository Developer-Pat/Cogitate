---
title: Debug Actions Service
type: atlas-service
path: frontend/src/services/domain/DebugActionsService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# Debug Actions Service

**Path**: `frontend/src/services/domain/DebugActionsService.ts`
**Type**: service (class + singleton)

## Purpose
Centralized management of "debug actions" (maintenance/diagnostic operations exposed to the UI):
list available actions, execute them, track per-action status and a bounded action history, and push
reactive updates to subscribers. Decoupled from React/Zustand — UI components subscribe directly.

**⚠️ Functional status: backend is a stub.** The backend `/api/v1/debug/actions` endpoint exists but
returns an empty list (`{"actions": [], "total": 0}`); the endpoints this service polls for status
(`GET /actions/{id}/status`) and history (`GET /actions/history`) are **not implemented** in the
backend router and 404 (errors are swallowed by the service's try/catch). The DebugControls UI labels
itself "Mock Actions - Coming Soon". See [Deprecation / Obsolete Notes](#deprecation--obsolete-notes).

## Exported API

### Types (all exported)
```typescript
type DebugActionCategory = 'system' | 'performance' | 'diagnostic' | 'maintenance'
type DebugActionStatus = 'idle' | 'running' | 'completed' | 'failed' | 'cancelled'

interface DebugAction {
  id: string
  name: string
  description: string
  category: DebugActionCategory
  requiresConfirmation: boolean
  dangerous: boolean
  endpoint?: string
  method?: 'POST' | 'DELETE' | 'PUT' | 'GET'
  enabled: boolean
}

interface ActionResult {
  actionId: string
  actionName: string
  status: DebugActionStatus
  message: string
  output?: string
  error?: string
  startedAt: string
  completedAt?: string
  duration?: number
}

interface ActionHistory {
  id: string
  actionId: string
  actionName: string
  status: DebugActionStatus
  executedAt: string
  executedBy?: string
  duration?: number
  result?: string
}
```

### Class `DebugActionsService` (exported; internal types `ActionSubscriber`, `StatusSubscriber`)
```typescript
constructor()                                  // calls loadActions() + startStatusPolling()

getActions(): DebugAction[]                    // copy of internal list
getAction(actionId: string): DebugAction | null
getActionStatus(actionId: string): DebugActionStatus            // local map, default 'idle'
getAllStatuses(): Record<string, DebugActionStatus>
getHistory(): ActionHistory[]                  // copy of internal history
subscribe(callback: (actions: DebugAction[]) => void): () => void   // fires immediately; returns unsubscribe
subscribeToStatus(callback: (status: Record<string, DebugActionStatus>) => void): () => void

async loadActions(): Promise<void>             // GET /api/v1/debug/actions; on failure → setDefaultActions()
async executeAction(actionId: string): Promise<ActionResult>  // runs action.endpoint (POST default); 'NOT_IMPLEMENTED' if no endpoint
async getActionStatusFromBackend(actionId: string): Promise<DebugActionStatus>  // GET /actions/{id}/status (404 → local status)
async cancelAction(actionId: string): Promise<void>           // POST /actions/{id}/cancel; always sets local 'cancelled'
async loadHistory(): Promise<void>             // GET /actions/history (404 → keeps local history)
async clearHistory(): Promise<void>            // DELETE /actions/history; always clears local history

stopStatusPolling(): void                      // clearInterval on 2s poller
destroy(): void                                // stop polling + clear subscribers
getStatus(): { actionCount: number; historyCount: number; subscriberCount: number;
               statusSubscriberCount: number; isLoading: boolean; runningActions: number }
```

### Private members
`setDefaultActions()` — 8 hardcoded actions (clear_cache, force_gc, reset_db_connections,
generate_performance_report, run_health_check, flush_logs, restart_services, memory_dump),
**all `enabled: false`**, used only as fallback when the backend request throws.
`addToHistory(result)` — prepends entry, keeps last 50. `notifySubscribers()` / `notifyStatusSubscribers()`.
`startStatusPolling()` — polls `getActionStatusFromBackend` for all `running` actions every 2000 ms.

### Singleton
```typescript
export const debugActionsService = new DebugActionsService()   // module-level singleton (line 546)
```

## Endpoints
All requests via `apiClient` (base `VITE_API_URL || http://localhost:8000`), full paths under `/api/v1`:

| Method | Path | Purpose | Backend status |
|--------|------|---------|----------------|
| GET | `/api/v1/debug/actions` | List actions | ✅ exists — **stub, returns `{"actions": [], "total": 0}`** |
| GET | `/api/v1/debug/actions/{actionId}/status` | Poll action status | ❌ **not in router** (404, caught) |
| POST | `/api/v1/debug/actions/{actionId}/cancel` | Cancel action | ✅ exists — stub success |
| GET | `/api/v1/debug/actions/history` | Load history | ❌ **not in router** (404, caught) |
| DELETE | `/api/v1/debug/actions/history` | Clear history | ✅ exists — stub success |
| — | `action.endpoint` (per-action, if set) | Execute action via its own endpoint | method defaults to POST; GET/DELETE supported |

Backend router: `backend/app/api/v1/debug/router.py` (prefix `/debug`, mounted at `/api/v1` in
`backend/app/api/v1/router.py` line 86). Note it also exposes `GET /actions/running` which the
frontend does **not** call, and it has **no** execute endpoint (`POST /actions/{id}`) — the frontend
either calls `action.endpoint` or returns `{ status: 'failed', error: 'NOT_IMPLEMENTED' }`.

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| `apiClient` (`services/apiClient.ts`) | service | All HTTP calls (get/post/delete), auth + retry handling |
| `frontendLoggingService` (`services/frontendLoggingService.ts`) | service | info/error/warning logs for load, execute, cancel, history ops |
| `ApiResponse` (`types`) | type | Response envelope used in executeAction |
| `setInterval`/`clearInterval` | global | 2s status polling for running actions |

## Usage Example
```tsx
// DebugControls.tsx — the primary consumer
useEffect(() => {
  debugActionsService.loadActions()
    .catch(err => { /* logs 'BACKEND API NOT AVAILABLE' + rethrows */ })

  const unsub = debugActionsService.subscribe((updatedActions) => setActions(updatedActions))
  const unsubStatus = debugActionsService.subscribeToStatus((statuses) => { /* ... */ })
  return () => { unsub(); unsubStatus() }
}, [])

// Execute (requires confirmation handled by the component for dangerous actions)
const result = await debugActionsService.executeAction(action.id)
```

## Data Flow / Notes
- **Init**: singleton constructor fires `loadActions()` + `startStatusPolling()` at module import.
- **loadActions** skips re-entry while `isLoading`; on success sets `actions` from `response.data?.actions || []`
  and notifies; on **any thrown error** falls back to `setDefaultActions()` (all disabled). Because the
  backend stub returns `[]` successfully, the fallback never runs and the UI shows zero actions.
- **executeAction**: sets local status `running` → notifies → calls `action.endpoint` if present
  (POST unless GET/DELETE) → builds `ActionResult` from `data.message/output/duration` → adds to
  local history → status `completed`. If the action has no `endpoint`, returns failed `NOT_IMPLEMENTED`
  **without** adding to history. All 8 fallback actions have no endpoint and `enabled: false`,
  so nothing is actually executable.
- **History**: local-only in practice (GET history 404s); capped at 50 entries; `clearHistory` always
  clears local state even if the DELETE fails.
- **Polling**: every 2s, only when at least one action is `running`; each poll GETs status (404s → keeps
  local status). `destroy()` stops the interval and clears subscribers.
- Subscriber callbacks fire immediately on subscribe with current state.

## Related
- `components/features/debugging/DebugControls.tsx` — **main consumer**; imports the singleton +
  `DebugAction`/`DebugActionStatus`/`ActionResult`; calls `loadActions`, `subscribe`, `subscribeToStatus`,
  `executeAction`, `getActionStatus`. Renders "Mock Actions - Coming Soon" badge and disables all actions
  (`!action.enabled` → "Not Implemented").
- `pages/Debugging.tsx` — imports `type DebugAction` only (for `handleActionExecute` callback logging);
  renders `<DebugControls>`.
- `services/domain/__tests__/DebugActionsService.test.ts` — unit tests constructing `new DebugActionsService()`.
- Backend: `backend/app/api/v1/debug/router.py` (stub endpoints).

## Deprecation / Obsolete Notes
- **No `@deprecated` / "legacy" markers** anywhere in the source — the service is not formally deprecated.
- **Not obsolete by consumer count**: 2 real consumers (`DebugControls.tsx`, `Debugging.tsx`) plus a unit
  test file — the service is actively imported and wired into the Debugging page.
- **Functionally inert, however**: the class docblock claims "Real backend integration (not mock)", but the
  actual backend (`backend/app/api/v1/debug/router.py`) returns empty stubs for the action list and lacks
  the status/history endpoints the service polls. Header comment `// Set default actions if backend
  unavailable` only covers thrown errors, not the empty-`[]` stub response.
- All surfaced actions are `enabled: false` and endpoint-less, so `executeAction` can only ever return
  `NOT_IMPLEMENTED` failures. The service is best described as **scaffolding for a feature that is still
  "Coming Soon"** — keep it if/when the backend implements real actions; until then it is dead weight on
  the Debugging page (empty action list + "Mock Actions - Coming Soon" UI).
