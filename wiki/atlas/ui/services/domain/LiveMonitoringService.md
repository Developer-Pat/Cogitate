---
title: Live Monitoring Service
type: atlas-service
path: frontend/src/services/domain/LiveMonitoringService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# Live Monitoring Service

**Path**: `frontend/src/services/domain/LiveMonitoringService.ts`
**Type**: service

## Purpose

Real-time activity monitoring for the frontend. Streams live activity events from the backend over a WebSocket (`/api/v1/monitoring/stream`), polls system metrics every 5 seconds, caches recent event history, and pushes both to UI subscribers through a plain subscriber pattern that is decoupled from React/Zustand. It is the engine behind the "Live Monitoring" tab of the Debugging page — and it is the *only* real-time data source there, silently falling back to static mock events/metrics whenever the backend is unreachable (see Data Flow / Notes).

Regarding the "monitoring UI is simulated" finding: this service itself is real infrastructure — a genuine `WebSocket` connection attempt, real REST calls, and a 5 s `setInterval` poller, with no `Math.random()` anywhere. What *is* simulated is (a) the component's session list (hardcoded mock sessions in `LiveMonitoring.tsx`) and (b) the service's static mock fallbacks (`setMockEvents` / `setMockMetrics`) that kick in when the backend is unavailable — which is why the tab can look fully simulated when no backend is running.

## Exported API (exact signatures)

Multi-export file: `export class LiveMonitoringService`, singleton `export const liveMonitoringService = new LiveMonitoringService()`, plus the types below. No default export.

### Exported types

```ts
export type ActivityEventType = 'request' | 'response' | 'error' | 'system' | 'info'

export interface ActivityEvent {
  id: string
  type: ActivityEventType
  timestamp: string
  source: string
  message: string
  metadata?: Record<string, unknown>
  severity?: 'low' | 'medium' | 'high'
  duration?: number
}

export interface MonitoringMetrics {
  requestsPerSecond: number
  errorsPerSecond: number
  activeConnections: number
  networkThroughput: { in: number; out: number }
  avgResponseTime: number
  successRate: number
  timestamp: string
}

export interface MonitoringStats {
  totalEvents: number
  eventsByType: Record<ActivityEventType, number>
  peakRPS: number
  peakErrors: number
  uptime: number
  lastEventAt?: string
}

type EventSubscriber = (event: ActivityEvent) => void
type MetricsSubscriber = (metrics: MonitoringMetrics) => void
```

### Public class methods

```ts
constructor()
// Builds wsUrl from import.meta.env.VITE_API_URL (default 'http://localhost:8000'):
//   protocol = baseUrl.startsWith('https') ? 'wss:' : 'ws:'
//   host = baseUrl without http(s):// prefix
//   wsUrl = `${protocol}//${host}/api/v1/monitoring/stream`

start(): void
// No-op if already running. Sets isRunning = true, connects WebSocket, starts 5 s metrics polling.

stop(): void
// Sets isRunning = false, closes WebSocket, clears the metrics polling interval.

getRecentEvents(limit: number = 100): ActivityEvent[]
// Returns a slice of the in-memory events cache (capped at 500 entries, newest first).

getCurrentMetrics(): MonitoringMetrics | null
// Returns the latest metrics snapshot, or null if none has ever been loaded.

subscribe(callback: EventSubscriber): () => void
// Adds an event subscriber; immediately replays the last 10 cached events to the callback.
// Returns an unsubscribe function.

subscribeToMetrics(callback: MetricsSubscriber): () => void
// Adds a metrics subscriber; immediately invokes callback with current metrics if present.
// Returns an unsubscribe function.

async loadRecentEvents(limit: number = 100): Promise<void>
// GET /api/v1/monitoring/events?limit=<n>; on failure falls back to setMockEvents().

async loadMetrics(): Promise<void>
// GET /api/v1/monitoring/metrics; on failure falls back to setMockMetrics().

async clearEvents(): Promise<void>
// DELETE /api/v1/monitoring/events; clears the local cache even if the request fails.

async getStats(): Promise<MonitoringStats>
// GET /api/v1/monitoring/stats; on failure returns locally-computed stats from the event cache.

destroy(): void
// Calls stop(), clears both subscriber sets, the event cache, and the metrics snapshot.

getStatus(): {
  isRunning: boolean
  eventCount: number
  hasWebSocket: boolean
  subscriberCount: number
  metricsSubscriberCount: number
  reconnectAttempts: number
}
// hasWebSocket is true only when ws !== null && ws.readyState === WebSocket.OPEN.
```

### Private members (behavioral notes)

- `connectWebSocket()` / `disconnectWebSocket()` — open/close the stream. `onmessage` handles `{type: 'event', ...}` frames (normalized into `ActivityEvent`; ids fall back to `event-${Date.now()}`, type to `'info'`, timestamp to now, source to `'unknown'`) and `{type: 'metrics', metrics}` frames; unparseable frames are logged via `frontendLoggingService.error`.
- Reconnect: on close, retries up to `maxReconnectAttempts` (5) with `setTimeout(reconnectDelay * attempt)` (3000 ms × attempt) while `isRunning`; logs "Max reconnect attempts reached" when exhausted.
- `startMetricsPolling()` — `setInterval(() => loadMetrics(), 5000)`; `stopMetricsPolling()` clears it.
- `setMockEvents()` — replaces the cache with a single static `info` event ("Monitoring service initialized (mock mode - backend unavailable)").
- `setMockMetrics()` — all-zero metrics with `successRate: 100`.
- `countEventsByType()` — aggregates the event cache into `Record<ActivityEventType, number>`.

## Endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| WS | `ws(s)://<host>/api/v1/monitoring/stream` | Push stream of `{type: 'event'}` and `{type: 'metrics'}` frames |
| GET | `/api/v1/monitoring/events?limit=<n>` | Fetch recent events (REST fallback / initial load) |
| DELETE | `/api/v1/monitoring/events` | Clear event history |
| GET | `/api/v1/monitoring/metrics` | Fetch current system metrics (polled every 5 s) |
| GET | `/api/v1/monitoring/stats` | Fetch aggregate monitoring stats |

`<host>` is derived from `import.meta.env.VITE_API_URL` (default `http://localhost:8000`); the WebSocket URL points at the backend host, not the Vite dev server.

## Dependencies

| Dependency | Type | Purpose |
| --- | --- | --- |
| `apiClient` (`EnhancedApiClient` singleton, `../apiClient`) | Internal service | REST calls for events / metrics / stats (`get`, `delete`) |
| `frontendLoggingService` (`../frontendLoggingService`) | Internal service | Info / warning / error logging of lifecycle and connection failures |
| `WebSocket` (browser global) | Platform API | Real-time event / metrics stream |
| `import.meta.env.VITE_API_URL` | Env var | Backend base URL (default `http://localhost:8000`) |
| `setInterval` / `setTimeout` | Platform API | 5 s metrics polling; reconnect backoff |

Note: all `traceService.trace(...)` calls in this file are commented out (the Vitest suite still `vi.mock`s `../TraceService`).

## Usage Example

As used by the Live Monitoring tab (`LiveMonitoring.tsx`):

```ts
import { liveMonitoringService, type ActivityEvent, type MonitoringMetrics } from '../../../services/domain/LiveMonitoringService'

liveMonitoringService.start()

const unsubscribeEvents = liveMonitoringService.subscribe((event: ActivityEvent) => {
  // prepend to UI event feed (component keeps last 100)
})

const unsubscribeMetrics = liveMonitoringService.subscribeToMetrics((metrics: MonitoringMetrics) => {
  // render Requests/sec, Errors/sec, Connections, Avg Response
})

// on unmount:
unsubscribeEvents()
unsubscribeMetrics()
liveMonitoringService.stop()
```

## Data Flow / Notes

1. `LiveMonitoring.tsx` mounts → `liveMonitoringService.start()` → WebSocket connect + 5 s metrics poll; `stop()` on unmount.
2. Inbound WS frames: `{type: 'event'}` is normalized into an `ActivityEvent` and prepended to the 500-entry cache, then `notifySubscribers` fires; `{type: 'metrics'}` replaces the snapshot and `notifyMetricsSubscribers` fires.
3. Subscriber pattern is decoupled from React/Zustand; `subscribe()` replays the last 10 cached events immediately so a late-mounting UI still gets recent history.
4. Reconnect: up to 5 attempts with linear backoff (3 s × attempt) while running.
5. Backend-unavailable path: `loadRecentEvents` / `loadMetrics` catch failures and install **static** mock data (one info event; all-zero metrics with 100% success rate). This is a degradation fallback, not a simulation loop — without a backend the tab shows a single mock event and zeroed metrics. The sessions grid in `LiveMonitoring.tsx` is entirely hardcoded mock data and never touches this service.
6. `clearEvents()` and `getStats()` have no UI caller today — only the unit tests exercise them.

## Related

- **Consumer (the only one)**: `frontend/src/components/features/debugging/LiveMonitoring.tsx` — uses `start()`, `subscribe()`, `subscribeToMetrics()`, `stop()`; rendered on the Debugging page (`frontend/src/pages/Debugging.tsx`, tab `'monitoring'`), routed at `/debugging` (`frontend/src/config/routes.ts`, lazy-loaded; nav entry in `App.tsx` and `utils/cogitateDevTools.ts`).
- **Tests**: `frontend/src/services/domain/__tests__/LiveMonitoringService.test.ts` (Vitest; mocks `apiClient`, `frontendLoggingService`, `TraceService`, and the global `WebSocket`).
- Other real-time infrastructure: the `useSSE`-based `ConnectionStatus` component (separate, real SSE monitor). Other "monitoring"-named components (`ProviderStatus`, `useProviderHealth`, etc.) do **not** import this service.

## Deprecation / Obsolete Notes

- **Not deprecated.** No `@deprecated`, "deprecated", "legacy", or "unused" markers anywhere in the file.
- Actively wired: one production consumer (`LiveMonitoring.tsx` → Debugging page → `/debugging` route) plus a Vitest suite, so this is **not** an orphaned service.
- Trace integration is vestigial: every `traceService.trace(...)` call is commented out (dead references), though the test file still mocks `../TraceService`.
- Several public methods (`loadRecentEvents`, `loadMetrics`, `clearEvents`, `getStats`, `destroy`, `getStatus`) have no UI caller — only unit tests. The UI consumer only uses `start` / `stop` / `subscribe` / `subscribeToMetrics`.
- The component is a consolidation remnant: header comment states it was "Extracted from RealTimeMonitor.tsx (now deleted)" during Phase 4 Consolidation (2026-03-07) and moved to the Debugging page's Live Monitoring tab.
- The `Math.random()`-based simulation found elsewhere in the monitoring UI does not live in this service; it only ever produces *static* mock fallbacks when its backend endpoints are unreachable.
