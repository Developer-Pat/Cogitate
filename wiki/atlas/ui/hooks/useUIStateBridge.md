---
title: useUIStateBridge
type: atlas-hook
path: frontend/src/hooks/useUIStateBridge.ts
confidence: high
updated: 2026-08-01
tags: [type/hook, domain/atlas-ui]
---
# useUIStateBridge

**Path**: `frontend/src/hooks/useUIStateBridge.ts`
**Type**: hook

## Purpose

Integrates the WebSocket UI State Bridge (the `uiStateBridge` singleton from `frontend/src/services/uiStateBridge.ts`) with the React app. It is a top-level lifecycle hook that:

- Connects the WebSocket on mount and disconnects on unmount
- Pushes UI state changes (route, sidebar collapsed, theater mode, active agent/session, theme) to the backend whenever tracked values change
- Handles incoming `navigation_request` messages from the backend by performing programmatic navigation via `react-router`
- Tracks WebSocket connection status and the latest UI state received from the backend
- Sends periodic pings every 30s to keep the connection alive and pushes an initial state 500ms after mount

The hook is the bridge between **Zustand stores + React Router** (source of truth on the client) and the **`uiStateBridge` WebSocket service** (which syncs state to the backend over `/api/v1/agent-chat/ws`).

## Exported API

```ts
export interface UseUIStateBridgeResult {
  /** Whether the WebSocket is currently connected */
  isConnected: boolean
  /** The latest UI state received from the backend */
  latestState: UIState | null
  /** Manually trigger a state push to the backend */
  pushState: () => void
  /** Manually reconnect the WebSocket */
  reconnect: () => void
}

export function useUIStateBridge(): UseUIStateBridgeResult
```

Also exported as default (`export default useUIStateBridge`). Takes no parameters.

The `UIState` type it exchanges comes from the service:

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
```

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `react` (`useEffect`, `useRef`, `useState`, `useCallback`) | React hooks | Component state, change tracking via refs, lifecycle effects |
| `react-router-dom` (`useLocation`, `useNavigate`) | Router hooks | Read the current route and perform programmatic navigation on incoming `navigation_request` |
| `uiStateBridge` + `UIState` (`../services/uiStateBridge`) | WebSocket service singleton | Send UI state (`sendUIState`), ping (`sendPing`), connect/disconnect, and subscribe to state/navigation/connection events |
| `frontendLoggingService` (`../services/frontendLoggingService`) | Logging service | Log incoming navigation requests |
| `useUIStore` (`../stores/uiStore`) | Zustand store | Source for `sidebarCollapsed` and `theaterModeActive` |
| `useCognitiveHubStore` (`../stores/cognitiveHubStore`) | Zustand store | Source for `activeAgent` and `activeSession` |
| `useSettingsStore` (`../stores/settingsStore`) | Zustand store | Source for `settings.appearance.theme` |

## Usage Example

```tsx
// Place in a top-level component (e.g. Layout in App.tsx) so it runs
// for the lifetime of the app.
function Layout({ children }: { children: React.ReactNode }) {
  const { isConnected, latestState, pushState, reconnect } = useUIStateBridge()

  return (
    <div>
      <div>WebSocket: {isConnected ? '🟢' : '🔴'}</div>
      <button onClick={pushState}>Sync state now</button>
      <button onClick={reconnect}>Reconnect</button>
      {children}
    </div>
  )
}
```

## State / Data Flow

**Outbound (React → backend):** The hook subscribes to `useUIStore` (`sidebarCollapsed`, `theaterModeActive`), `useCognitiveHubStore` (`activeAgent`, `activeSession`), `useSettingsStore` (`theme`), and `useLocation` (`pathname`). A `prevRef` tracks the previous snapshot of all seven values. When any value changes (and the WebSocket is connected), `pushState()` sends a `ui_state_update` WebSocket message with the full state payload via `uiStateBridge.sendUIState()`. `pushState` is also invoked once 500ms after mount to push initial state.

**Inbound (backend → React):**
- `navigation_request` messages → `uiStateBridge.onNavigation(...)` → `navigate(route, { replace })` (replace honored via the `replace` flag)
- `ui_state_update` messages → `uiStateBridge.onUIState(...)` → stored in local `latestState` state
- Connection open/close → `uiStateBridge.onConnectionChange(...)` → local `isConnected` state

**Connection lifecycle:** `uiStateBridge.connect()` on mount; `uiStateBridge.disconnect()` on unmount (with cleanup of the initial-push timeout and the 30s ping interval). `reconnect()` tears down and re-establishes the socket after 100ms. The service itself handles exponential backoff reconnection (max 10 retries, base 1s, capped at 30s with jitter).

Note: incoming backend UI state is surfaced via `latestState` but is not written back into the Zustand stores — the stores remain the client-side source of truth for outbound pushes.

## Related

- `frontend/src/services/uiStateBridge.ts` — the WebSocket client singleton this hook wraps (connection management, exponential-backoff reconnection, listener registration)
- `frontend/src/App.tsx` — calls `useUIStateBridge()` inside `Layout` (line ~66) to initialize the bridge for the app lifetime; `Layout` also consumes `useUIStore` for `sidebarCollapsed`/`toggleSidebar`
- `frontend/src/stores/uiStore.ts` — Zustand store holding `sidebarCollapsed` / `theaterModeActive`
- `frontend/src/stores/cognitiveHubStore.ts` — Zustand store holding `activeAgent` / `activeSession`
- `frontend/src/stores/settingsStore.ts` — Zustand store holding `settings.appearance.theme`
- `frontend/src/services/frontendLoggingService.ts` — logging used for navigation requests and bridge events
- Backend: `backend/app/api/v1/agent_chat/router.py` (WebSocket endpoint `/api/v1/agent-chat/ws`) per the service doc reference
