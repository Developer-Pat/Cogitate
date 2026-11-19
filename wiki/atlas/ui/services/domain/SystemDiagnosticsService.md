---
title: System Diagnostics Service
type: atlas-service
path: frontend/src/services/domain/SystemDiagnosticsService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# System Diagnostics Service

**Path**: `frontend/src/services/domain/SystemDiagnosticsService.ts`
**Type**: service (class + singleton export)

## Purpose

Real system diagnostics and health checks for the frontend. The service:

- Runs system diagnostics / health checks against the backend and caches the results in memory.
- Pulls real-time system metrics (CPU / memory / disk usage) from the backend.
- Tracks diagnostic history.
- Pushes reactive updates to UI subscribers (subscriber pattern, decoupled from React/Zustand).

Backend status: the `/api/v1/diagnostics/*` and `/api/v1/health` endpoints are **implemented and mounted** (`backend/app/api/v1/diagnostics/router.py`, psutil-backed real data — not a mock). However, the only UI consumer component (`SystemDiagnostics.tsx`) is **orphaned — nothing renders it**, so in practice the service's frontend chain is unwired (see [Deprecation / Obsolete Notes](#deprecation--obsolete-notes)).

## Exported API

### Types (all exported)

```typescript
export type DiagnosticStatus = 'pass' | 'fail' | 'warning'
export type MetricTrend = 'up' | 'down' | 'stable'

export interface SystemMetric {
  name: string
  value: number
  unit: string
  status: 'healthy' | 'warning' | 'critical'
  threshold: number
  trend: MetricTrend
  timestamp: string
}

export interface DiagnosticResult {
  id: string
  name: string
  status: DiagnosticStatus
  message: string
  timestamp: string
  details?: string
  metric?: {
    name: string
    value: number
    unit: string
    threshold: number
  }
  duration?: number
}

export interface DiagnosticHistory {
  id: string
  diagnosticId: string
  name: string
  status: DiagnosticStatus
  timestamp: string
  duration: number
}

export interface SystemHealth {
  overall: 'healthy' | 'degraded' | 'critical'
  services: {
    name: string
    status: 'healthy' | 'degraded' | 'unhealthy'
    message?: string
  }[]
  resources: {
    cpu: number
    memory: number
    disk: number
    network: number
  }
  timestamp: string
}
```

Non-exported internal interfaces (consumers cannot see them): `DiagnosticsRunResponse`, `DiagnosticRunResponse`, `MetricsResponse`, `HistoryResponse`, `HealthResponse` — the response wrappers declared at the top of the file.

### Class `SystemDiagnosticsService` (exported) — methods

```typescript
constructor()                        // starts background metrics sync (10s interval)
getMetrics(): SystemMetric[]         // cached metrics (copy)
getDiagnostics(): DiagnosticResult[] // cached diagnostic results (copy)
subscribeToMetrics(callback: (metrics: SystemMetric[]) => void): () => void      // immediate callback with current state; returns unsubscribe
subscribeToDiagnostics(callback: (results: DiagnosticResult[]) => void): () => void
runDiagnostics(): Promise<DiagnosticResult[]>      // POST /api/v1/diagnostics/run; rethrows on error; returns cache while a run is in progress
runDiagnostic(diagnosticId: string): Promise<DiagnosticResult>  // POST /api/v1/diagnostics/{id}/run; replaces the cached entry for that id; rethrows wrapped Error
loadMetrics(): Promise<void>         // GET /api/v1/diagnostics/metrics; updates cache + lastSyncTime; rethrows on error
getDiagnosticHistory(): Promise<DiagnosticHistory[]>  // GET /api/v1/diagnostics/history; swallows errors and returns []
getSystemHealth(): Promise<SystemHealth>  // GET /api/v1/health; swallows errors, returns fallback; success path also falls back (see Notes)
clearMetrics(): void                 // empties metric cache, notifies subscribers
clearDiagnostics(): void             // empties diagnostic cache, notifies subscribers
stopMetricsSync(): void              // clears the 10s background interval
destroy(): void                      // stopMetricsSync + clears all subscribers
getStatus(): {
  metricCount: number
  diagnosticCount: number
  metricSubscriberCount: number
  diagnosticSubscriberCount: number
  isLoading: boolean
  lastSyncTime: Date | null
}
```

### Singleton

```typescript
export const systemDiagnosticsService = new SystemDiagnosticsService()
```

Instantiated at module load — importing this module starts the 10-second background metrics sync immediately.

## Endpoints

All requests go through `apiClient` (`frontend/src/services/apiClient.ts`, base URL from `VITE_API_URL` defaulting to `http://localhost:8000`).

| Method | Endpoint | Purpose | Backend status |
|--------|----------|---------|----------------|
| POST | `/api/v1/diagnostics/run` | Run all diagnostics | Exists (`diagnostics/router.py` `run_all_diagnostics`, psutil-backed) |
| POST | `/api/v1/diagnostics/{id}/run` | Run a single diagnostic by id | Exists — response shape mismatch (returns result unwrapped; service reads `{data: ...}`, see Notes) |
| GET | `/api/v1/diagnostics/metrics` | Fetch live system metrics | Exists (`get_diagnostics_metrics`) |
| GET | `/api/v1/diagnostics/history` | Fetch diagnostic history | **Not in router** — 404 swallowed, always returns `[]` |
| GET | `/api/v1/health` | Fetch system health | Exists (`health/router.py`) — returns only `{"status": "healthy"}`, not the `SystemHealth` shape (see Notes) |

Backend-only endpoints the service does NOT call (present in `diagnostics/router.py`): `GET /api/v1/diagnostics` (list with pass/warning/fail counts), `POST /api/v1/diagnostics/{id}/resolve`, `DELETE /api/v1/diagnostics/{id}`, `DELETE /api/v1/diagnostics/resolved`.

## Dependencies

| Dependency | Type | Purpose |
|------------|------|---------|
| `apiClient` (`../apiClient`) | singleton client | All HTTP calls (`EnhancedApiClient`; 10s timeout, 3 retries, Bearer auth) |
| `frontendLoggingService` (`../frontendLoggingService`) | singleton service | info/error/debug logging for every operation |

## Usage Example

From `components/features/debugging/SystemDiagnostics.tsx` (the only functional consumer):

```typescript
// On mount: load metrics, subscribe for reactive updates
systemDiagnosticsService.loadMetrics()
  .catch(err => { /* re-thrown to surface backend unavailability */ })
  .finally(() => setIsLoading(false))

const unsubscribeMetrics = systemDiagnosticsService.subscribeToMetrics(setMetrics)
const unsubscribeDiagnostics = systemDiagnosticsService.subscribeToDiagnostics(setDiagnostics)
// cleanup on unmount: unsubscribeMetrics(); unsubscribeDiagnostics()

// Button handler
const results = await systemDiagnosticsService.runDiagnostics()
onDiagnosticComplete?.(results)
```

## Data Flow / Notes

- **Background sync**: the constructor calls `startMetricsSync()` — a real, running `setInterval(..., 10000)` that calls `loadMetrics()` every 10 seconds with `.catch(() => {})` (silent failure). The sync is live (only the `traceService` lines inside are commented out). Because the singleton is created at module load, the interval only runs while the module is actually imported.
- **Subscriber pattern**: `subscribeToMetrics` / `subscribeToDiagnostics` invoke the callback immediately with current state, then on every cache change; both return an unsubscribe closure. `clearMetrics` / `clearDiagnostics` also notify subscribers.
- **Concurrency guard**: `runDiagnostics()` early-returns the cached results while `isLoading` is true; `isLoading` is reset in `finally`.
- **Error semantics**: `runDiagnostics()` and `loadMetrics()` rethrow; `runDiagnostic()` rethrows a new `Error` preferring the backend `detail` message; `getDiagnosticHistory()` swallows errors and returns `[]`; `getSystemHealth()` swallows errors and returns a fallback with `overall: 'critical'`.
- **Response shape mismatch — `runDiagnostic`**: the service types the response as `{ data: DiagnosticResult }` and reads `response.data?.data`, but the backend returns the diagnostic object **unwrapped** (`{id, name, status, message, timestamp, duration}`). `result` is therefore `undefined`, and the cache entry pushed + delivered to subscribers is `undefined`. The method would need to read `response.data` directly.
- **Response shape mismatch — `getSystemHealth`**: the service expects `{ data: SystemHealth }`, but `GET /api/v1/health` returns `{"status": "healthy"}`. The optional chain yields `undefined` on success too, so the method **always** returns a hardcoded fallback (`{overall: 'healthy', ...}` on success, `{overall: 'critical', ...}` on error) — real backend health data never surfaces.
- **Missing endpoint — history**: `getDiagnosticHistory()` targets `/api/v1/diagnostics/history`, which the backend router does not define. The 404 is swallowed, so history is always `[]`.
- **Timestamp units**: the backend sends `timestamp` as a Unix-seconds float (`time.time()`), while the frontend types declare `timestamp: string`; the component's `new Date(diagnostic.timestamp)` would interpret the seconds value as milliseconds (1970-era dates) if it were wired up.
- **Stale UI copy**: the `SystemDiagnostics` component header shows a "Mock Data - Coming Soon" badge and a "simulated metrics" alert, but the backend endpoints are real and implemented (psutil). The badge is stale, not the backend.

## Related

| Consumer | Path | Relationship |
|----------|------|--------------|
| `SystemDiagnostics` component | `frontend/src/components/features/debugging/SystemDiagnostics.tsx` | Sole functional consumer: calls `loadMetrics()`, `subscribeToMetrics`, `subscribeToDiagnostics`, `runDiagnostics()` — itself **orphaned** (nothing imports/renders it; the Debugging page has no diagnostics tab) |
| `Debugging` page | `frontend/src/pages/Debugging.tsx` | Type-only import of `DiagnosticResult` (erased at compile time); holds unused `_diagnosticResults` state (no UI wiring) |
| Unit tests | `frontend/src/services/domain/__tests__/SystemDiagnosticsService.test.ts` | Instantiates `new SystemDiagnosticsService()` directly |

`TraceAnalysis.tsx` mentions `SystemDiagnosticsService` only as a string (trace-filter suggestions / placeholder) — not a consumer.

## Deprecation / Obsolete Notes

**Three-check verdict — not formally deprecated, but the frontend chain is orphaned (backend-live + frontend-dead):**

1. **Markers**: none. No `@deprecated` tags, no legacy/unused comments; the only inert code is commented-out `traceService` calls.
2. **Live consumers**: the service is imported by the `SystemDiagnostics` component, but that component has **zero import/render sites** across `frontend/src` — the Debugging page (its natural home) renders other tools/tabs and no diagnostics tab, and holds an unused `_diagnosticResults` state suggesting dropped wiring. `Debugging.tsx` imports only the `DiagnosticResult` type; unit tests instantiate the class. The running app never mounts the diagnostics UI.
3. **Functional reality**: the backend endpoints are fully implemented and mounted (real psutil metrics — not a mock), so the service is not dead on the backend side. But two of its five methods are broken against the real contract (`runDiagnostic` unwrap mismatch, `getSystemHealth` shape mismatch — always fallback) and one hits a missing route (`getDiagnosticHistory` — 404, always `[]`).

**Verdict**: obsolete candidate on the frontend — wire the service + component into the Debugging page (or a diagnostics surface) or remove them from the frontend; the backend router stays. If wiring is pursued, also fix the stale "Mock Data - Coming Soon" badge, the two response-shape mismatches, and the missing `/history` route. Note the module-level singleton: merely importing the module starts a 10s polling interval.
