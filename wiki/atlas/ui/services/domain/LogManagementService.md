---
title: Log Management Service
type: atlas-service
path: frontend/src/services/domain/LogManagementService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# Log Management Service

**Path**: `frontend/src/services/domain/LogManagementService.ts`
**Type**: service

## Purpose
Enhanced log management service layered on top of the existing logsService. Provides frontend log clearing (deletes log files), SSE log streaming, log-source and level summaries, a 500-entry in-memory recent-log cache with a subscriber (observer) pattern for reactive updates, and background sync (every 5 s) against file-based backend endpoints. Deliberately decoupled from React/Zustand so it can be driven from any UI (currently the LogViewer debugging component). The module exports the class plus a singleton instance `logManagementService`.

## Exported API
Multi-export module: interfaces `LogStats`, `LogSource`, `LevelSummary` (response-shape interfaces `FileRecentResponse`, `SystemLogsResponse`, `LogExportResponse`, `LogStatsResponse`, `LogSourceItem`, `ApiErrorResponse` are module-private), the `LogManagementService` class, and the singleton `logManagementService`.

### Types
```ts
export interface LogStats {
  total: number
  byLevel: Record<string, number>
  bySource: Record<string, number>
  recentActivity: number
  frontendLogs: number
  backendLogs: number
  last24Hours: number
  trend: 'up' | 'down' | 'stable'
}

export interface LogSource {
  name: string
  count: number
  lastActivity?: string
}

export interface LevelSummary {
  level: string
  count: number
  percentage: number
}
```

### Class methods (exact signatures)
```ts
class LogManagementService {
  getLogs(filters?: LogFilter, limit: number = 100): LogEntry[]
  subscribe(callback: LogSubscriber): () => void   // LogSubscriber = (logs: LogEntry[]) => void
  addLog(log: LogEntry): void
  loadRecentLogs(limit: number = 100, _filters?: LogFilter): Promise<void>
  getLogsFromBackend(filters?: LogFilter, page: number = 1, pageSize: number = 50)
  exportLogs(format: 'json' | 'csv' = 'json', filters?: LogFilter): Promise<Blob>
  getLogStats(): Promise<LogStats>
  getLogSources(): Promise<LogSource[]>
  getLevelSummary(): Promise<LevelSummary[]>
  clearFrontendLogs(): Promise<void>
  clearAllLogs(olderThan?: string): Promise<void>
  streamLogs(callback: (log: LogEntry) => void): () => void
  clearAll(): void
  stopBackgroundSync(): void
  stopStreaming(): void
  destroy(): void
  getStatus(): {
    logCount: number
    subscriberCount: number
    isLoading: boolean
    lastSyncTime: Date | null
    isStreaming: boolean
  }
}
```

Notes on behavior:
- The constructor starts background sync: `setInterval` every 5000 ms calls `loadRecentLogs(100)` with errors silently swallowed.
- `loadRecentLogs` reads the file endpoint and replaces the cache with the response `items` array; `addLog` and `streamLogs` prepend and cap the cache at the most recent 500 entries.
- `getLogs` is client-side filtering of the cache: level (array membership), source (substring match), search (message substring).
- `getLogStats` normalizes both snake_case (`by_level`, `last_24_hours`, ...) and camelCase response keys; on failure it returns a zeroed `LogStats` instead of throwing.
- `getLevelSummary` computes percentage against the debug+info+warning+error+critical total.
- `clearAllLogs` accepts `olderThan` but never sends it in the DELETE request.
- `streamLogs` opens an `EventSource` against the absolute backend URL and returns an unsubscribe/cleanup closure.
- `clearFrontendLogs` / `clearAllLogs` surface backend errors via the nested `response.data.detail` message.

## Endpoints
HTTP endpoints use the relative base path `/api/v1/logs`; the SSE endpoint uses the absolute `baseUrl` (`import.meta.env.VITE_API_URL || 'http://localhost:8000'`).

| Method | Endpoint | Purpose | Response shape |
|---|---|---|---|
| GET | `/api/v1/logs/file/recent?n={limit}` | Recent logs from log files (`loadRecentLogs`) | `{ items: LogEntry[]; total: number; file: string }` |
| GET | `/api/v1/logs/export?format=&level=&source=` | Export logs as JSON/CSV blob (`exportLogs`) | `{ size: number; blob?: Blob }` |
| GET | `/api/v1/logs/stats` | Aggregate log statistics (`getLogStats`) | `LogStatsResponse` (snake_case and/or camelCase keys) |
| GET | `/api/v1/logs/sources` | Available log sources (`getLogSources`) | `LogSourceItem[]` (`{ value?/name?, count, last_activity? }`) |
| DELETE | `/api/v1/logs/file/clear?frontend=true&backend=false` | Delete frontend log file (`clearFrontendLogs`) | — |
| DELETE | `/api/v1/logs/file/clear?frontend=true&backend=true` | Delete frontend + backend log files, admin (`clearAllLogs`) | — |
| SSE | `{baseUrl}/api/v1/logs/stream` | Real-time log stream (`streamLogs`) | `EventSource` messages carrying `LogEntry` JSON |

## Dependencies
| Dependency | Type | Purpose |
|---|---|---|
| `apiClient` (`../apiClient`) | HTTP client | All GET/DELETE calls to `/api/v1/logs` endpoints |
| `frontendLoggingService` (`../frontendLoggingService`) | Logging service | info/warning/error telemetry for load/export/clear/stream operations |
| `logsService` (`../domains/system/logsService`) | `ILogsService` implementation (class `LogsService`) | `getLogsFromBackend()` delegates paginated backend log fetching |
| `LogEntry`, `LogFilter` (`../../types`) | TypeScript types | Log entry shape and filter options |
| `EventSource` | Browser API | SSE streaming of live logs |
| `import.meta.env.VITE_API_URL` | Build-time env var | Backend base URL for the SSE stream (default `http://localhost:8000`) |

## Usage Example
```ts
import { logManagementService } from '../services/domain/LogManagementService'

// Subscribe to cache updates (callback fires immediately with current logs)
const unsubscribe = logManagementService.subscribe((logs) => {
  console.log(`${logs.length} recent logs`)
})

// Load from backend and stream live
await logManagementService.loadRecentLogs(100)
const stopStream = logManagementService.streamLogs((log) => console.log(log.message))

// Read cache with filters (level array, source substring, search)
const errors = logManagementService.getLogs({ level: 'error' })

// Stats, export, and clear
const stats = await logManagementService.getLogStats()
const blob = await logManagementService.exportLogs('csv')
await logManagementService.clearFrontendLogs()

// Teardown
stopStream()
logManagementService.destroy()
```

## Data Flow / Notes
- Background sync: the constructor starts a 5000 ms interval that calls `loadRecentLogs(100)` and swallows failures, so the cache stays fresh without UI involvement.
- Cache semantics: `loadRecentLogs` replaces `recentLogs` wholesale from the file endpoint's `items` array; `addLog` and `streamLogs` prepend and slice to the most recent 500 entries. `notifySubscribers()` pushes the full array to every subscriber; `subscribe()` returns an unsubscribe closure and fires once immediately.
- `getLogs` is purely client-side filtering of the cache; for server-side filtered/paginated queries callers use `getLogsFromBackend()` (delegates to the domains/system `logsService.getLogs`) or the Logs page hooks.
- `getLogStats` tolerates both snake_case and camelCase keys from the backend; failures return a zeroed `LogStats`.
- Clear operations DELETE the physical log files (frontend only vs frontend+backend), then empty the cache and notify subscribers; API errors surface via nested `response.data.detail`.
- SSE uses the absolute backend URL rather than the relative path so the frontend dev server does not intercept the connection; connection errors close the `EventSource`.

## Related
- `components/features/debugging/LogViewer.tsx` — the only direct consumer of `logManagementService` (`loadRecentLogs`, `subscribe`, `streamLogs`, `exportLogs`, `clearFrontendLogs`, `stopStreaming`).
- `pages/Debugging.tsx` — hosts `LogViewer`.
- `hooks/useLogs.ts` — `useLogs`, `useLogSources`, `useLogStats`, `useClearLogs`; these consume the ROOT `services/logsService.ts` (via `services/index.ts`), not `logManagementService`.
- `pages/Logs.tsx` — the Logs page uses the `useLogs`/`useLogStats`/`useLogsFilters` hooks, which go through the root `logsService`.
- `services/logsService.ts` — root `logsService` object (implements `ILogsService`); exported as `logsService` from `services/index.ts`; used by all log hooks and the Logs page. Shares `/api/v1/logs/file/recent`, `/sources` endpoints, plus `/file/stats`, `/frontend`, `/frontend/batch`, `/{id}`.
- `services/domains/system/logsService.ts` — class `LogsService` with base path `/api/v1/system/logs`; imported by `LogManagementService` for `getLogsFromBackend()` and re-exported as `domainLogsService` from `services/index.ts` "for backward compatibility".
- `services/domain/__tests__/LogManagementService.test.ts` — unit tests for this service.

## Deprecation / Obsolete Notes
- No `@deprecated`, "legacy", "unused", or "no longer used" markers exist in `LogManagementService.ts`. It is actively consumed (`LogViewer.tsx`) and NOT deprecated.
- Which logs service is used where:
  - `logManagementService` (this file) powers the Debugging/LogViewer UI: SSE streaming, file-based clear, cache + subscriber pattern.
  - The Logs page and `useLogs` hooks use the ROOT `services/logsService.ts` object (in-memory store + backend fallback) exported as `logsService` from `services/index.ts`.
  - The class-based `services/domains/system/logsService.ts` is used only via `getLogsFromBackend()` and re-exported as `domainLogsService` for backward compatibility; its base path is `/api/v1/system/logs`, which differs from the `/api/v1/logs` paths used everywhere else.
- `domains/system/logsService.ts` contains unimplemented stubs: `streamLogs` and `exportLogs` log "not yet implemented", and `addLog` is a no-op. The real streaming/export implementations live in `LogManagementService`.
- `services/index.ts` labels some re-exports "legacy services for backward compatibility" (`legacyAgentService`, `legacyApiClient`) and comments the root `logsService` as "In-memory logs service".
