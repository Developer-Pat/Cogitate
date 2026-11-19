---
title: UIStateBridge
type: atlas-service
path: frontend/src/services/uiStateBridge.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---

# UIStateBridge

**Path**: `frontend/src/services/uiStateBridge.ts`
**Type**: service

## Purpose

WebSocket client for real-time UI state sync between the frontend and the backend. It connects to the backend WebSocket endpoint at `/api/v1/agent-chat/ws` (host derived from `VITE_API_URL`, default `http://localhost:8000`) and provides:

- Real-time UI state push (route, sidebar collapsed, theater mode, active agent/session, theme)
- Reception of backend-driven `ui_state_update` messages (cached in memory and fan-out to listeners)
- Programmatic navigation via incoming `navigation_request` messages
- Automatic reconnection with exponential backoff + jitter (max 10 retries, capped at 30s)

It is a **transient sync channel only — it persists nothing**. There is no `localStorage`/sessionStorage write anywhere in the module; the only "persistence" is the in-memory `_latestState` cache that lets late subscribers immediately receive the last known state. The backend is the source of truth; the frontend re-pushes state on change (and the hook does an initial push after connect). Note that the bridged state covers route, sidebar, theater mode, active agent/session and theme — **modal state is NOT part of `UIState`**.

Backend counterpart: `backend/app/api/v1/agent_chat/router.py:773` (per the source JSDoc).

## Exported API

Multi-export module: the `UIStateBridge` class (not exported), three listener types, two interfaces, and a singleton instance exported both named and as default.

### Interfaces (verbatim)

```ts
export interface UIState {
  current_route: string
  sidebar_collapsed: boolean
  theater_mode_active: boolean
  active_agent_id: string | null
  active_agent_name: string | null
  active_session_id: string | null
  active_session_title: string | null
  theme: string
  timestamp: string
}

export interface WSMessage {
  type: 'ui_state_update' | 'navigation_request' | 'ping' | 'pong' | 'error'
  payload?: Record<string, unknown>
  timestamp: string
}
```

### Listener types

```ts
export type UIStateListener = (state: UIState) => void
export type NavigationListener = (route: string, replace: boolean) => void
export type ConnectionListener = (connected: boolean) => void
```

### Singleton export

```ts
export const uiStateBridge = new UIStateBridge()
export default uiStateBridge
```

The singleton is the entire public surface — the class itself is not exported, so all consumers use `uiStateBridge` to avoid duplicate WebSocket connections.

### Instance members (`class UIStateBridge`)

```ts
get isConnected(): boolean
get latestState(): UIState | null
```

```ts
connect(): void
```
Opens the WebSocket. No-op if already `WebSocket.OPEN`. Resets `retryCount` on open, notifies connection listeners, logs via `frontendLoggingService`. On close/error schedules reconnection via `scheduleReconnect()` (unless the close was intentional).

```ts
disconnect(): void
```
Sets `isIntentionalClose = true`, cancels any pending reconnect, closes the socket with code 1000 (`'Client disconnecting'`), nulls the reference, and notifies connection listeners with `false`.

```ts
sendUIState(state: Partial<UIState>): void
```
Sends a `ui_state_update` WSMessage with the given partial state and an ISO timestamp. **Silently drops when the socket is not open** (comment: "the state will be sent on next connect or periodic sync") — no queue, no error thrown.

```ts
sendPing(): void
```
Sends a `ping` WSMessage. No-op unless the socket is open.

```ts
onUIState(listener: UIStateListener): () => void
```
Registers a state listener; **immediately invokes it with `_latestState` if one exists**. Returns an unsubscribe closure that removes the listener.

```ts
onNavigation(listener: NavigationListener): () => void
```
Registers a navigation listener. Returns an unsubscribe closure.

```ts
onConnectionChange(listener: ConnectionListener): () => void
```
Registers a connection listener; **immediately invokes it with the current `_isConnected` value**. Returns an unsubscribe closure.

Private helpers (not exported): `handleMessage`, `notifyStateListeners`, `notifyNavigationListeners`, `notifyConnectionListeners`, `scheduleReconnect`, `cancelReconnect`. Each notify helper wraps listener calls in try/catch and logs listener errors without breaking the loop.

## Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| WebSocket (ws/wss) | `ws://<VITE_API_URL host>/api/v1/agent-chat/ws` | Bidirectional UI state sync; receives `ui_state_update` / `navigation_request` / `pong` / `error`, sends `ui_state_update` / `ping` |

`WS_URL` is computed as `API_BASE_URL.replace(/^http/, 'ws') + '/api/v1/agent-chat/ws'` where `API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'` — so `http`/`https` become `ws`/`wss`.

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `frontendLoggingService` (`./frontendLoggingService`) | service | Structured logging — connection events, parse failures, listener errors, reconnect attempts, server errors |
| `import.meta.env.VITE_API_URL` | env var | API base URL override for the WebSocket host (default `http://localhost:8000`) |
| Browser `WebSocket` API | platform | Underlying connection, `onopen`/`onmessage`/`onclose`/`onerror` handlers |
| `frontend/src/hooks/useUIStateBridge.ts` | hook (consumer) | Sole consumer; wires the singleton to React (see Related) |

The service itself has no React, store, or router imports — all of that lives in the hook.

## Usage Example

Real consumer — `frontend/src/App.tsx` mounts the hook at app level and reads connection status:

```tsx
// App.tsx
import { useUIStateBridge } from './hooks/useUIStateBridge'
// ...
const { isConnected } = useUIStateBridge()
```

The hook (the service's only consumer) uses the bridge directly — e.g. pushing state (`hooks/useUIStateBridge.ts`):

```ts
uiStateBridge.sendUIState({
  current_route: location.pathname,
  sidebar_collapsed: sidebarCollapsed,
  theater_mode_active: theaterModeActive,
  active_agent_id: agentId,
  active_agent_name: activeAgent?.name ?? null,
  active_session_id: sessionId,
  active_session_title: activeSession?.title ?? null,
  theme: themeSetting || 'light',
})
```

Direct singleton use (for non-hook contexts): `uiStateBridge.connect()` / `uiStateBridge.disconnect()` / `uiStateBridge.onUIState((state) => ...)` — each listener registration returns an unsubscribe function.

## Data Flow / Notes

**Send path (frontend → backend)**: `useUIStateBridge` subscribes to `uiStore` (`sidebarCollapsed`, `theaterModeActive`), `cognitiveHubStore` (`activeAgent`, `activeSession`) and `settingsStore` (`appearance.theme`). A diff effect compares those plus `location.pathname` against a `prevRef`; on any change (and only `if (uiStateBridge.isConnected)`) it calls `pushState()` → `sendUIState(...)`. On mount it connects, pushes initial state after a 500ms delay, and pings every 30s; on unmount it clears both timers and disconnects.

**Receive path (backend → frontend)**: `handleMessage` switches on `WSMessage.type`:
- `ui_state_update` → caches payload as `_latestState`, notifies state listeners (hook stores it in React state via `setLatestState`).
- `navigation_request` → extracts `route` (default `'/'`) and `replace` (default `false`), notifies navigation listeners (hook calls `navigate(route, { replace })` or `navigate(route)`).
- `pong` → keep-alive response, no-op.
- `error` → logged via `frontendLoggingService.error` with the payload.

**Reconnect policy**: `scheduleReconnect()` cancels any pending timer, bails with a logged error once `retryCount >= maxRetries` (10), otherwise schedules `connect()` after `min(1000 * 2^retryCount + random()*1000, 30000)` ms and increments the counter. `retryCount` resets to 0 on successful open. `disconnect()` sets `isIntentionalClose` so no reconnect is scheduled.

**Listener semantics**: `onUIState` and `onConnectionChange` fire immediately with current state (last-known `_latestState` / `_isConnected`), so subscribers never wait for the next message; all unsubscribes are idempotent `Set.delete` closures.

**Persistence**: none. In-memory `_latestState` cache only; dropped `sendUIState` calls while disconnected are not queued (re-sync relies on the hook's change-driven pushes after reconnect).

## Related

- **`useUIStateBridge`** (`hooks/useUIStateBridge.ts`) — the sole consumer of the service; owns connect/disconnect lifecycle, change-diffed state pushes, navigation handling, connection tracking, and the 30s ping loop. Returns `{ isConnected, latestState, pushState, reconnect }`.
- **`App.tsx`** — mounts the hook at the top level (line 66: `const { isConnected } = useUIStateBridge()`).
- **`uiStore`** (`stores/uiStore.ts`) — supplies `sidebarCollapsed`, `theaterModeActive` to the push path.
- **`cognitiveHubStore`** (`stores/cognitiveHubStore.ts`) — supplies `activeAgent`, `activeSession`.
- **`settingsStore`** (`stores/settingsStore.ts`) — supplies `settings.appearance.theme`.
- **`frontendLoggingService`** (`services/frontendLoggingService.ts`) — logging dependency.
- **Backend** — `backend/app/api/v1/agent_chat/router.py:773` (WebSocket endpoint implementation).

## Deprecation / Obsolete Notes

**Not deprecated.** No `@deprecated` markers, no "legacy"/"unused" comments in the source. The service is actively consumed: `uiStateBridge` → `useUIStateBridge` → `App.tsx` (live mount at app root). Grep confirms the singleton has exactly one importer (`hooks/useUIStateBridge.ts`, both named `UIState` type and default import), so the consumer chain is healthy and single-path. The module name ("bridge") is accurate — it is a transient sync channel, not a persisted store; do not mistake the in-memory `latestState` cache for persistence.
