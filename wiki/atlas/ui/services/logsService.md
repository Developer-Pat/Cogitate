---
title: Logs Service
type: atlas-service
path: frontend/src/services/logsService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# Logs Service

**Path**: `frontend/src/services/logsService.ts`
**Type**: service

## Purpose

Root (top-level) logs service. Handles system log and event endpoints for the frontend, connecting to the backend API for persistent storage while maintaining an in-memory store (`globalLogStore`) as cache/fallback. It is the *file-based* implementation: it reads recent logs from the file-backed endpoints under `/api/v1/logs/file/...` and computes stats from on-disk log file sizes. A sibling, database-based implementation lives at `frontend/src/services/domains/system/logsService.ts` (endpoints under `/api/v1/system/logs/...`); this file only imports the `ILogsService` interface from there, not its implementation.

This file exports a singleton object literal (`logsService`) typed as `ILogsService`, plus one module-private helper (`convertLogsToCSV`). The domain variant is re-exported from `services/index.ts` as `domainLogsService`; this root service is re-exported as `logsService`.

## Exported API

Single export: `export const logsService: ILogsService = { ... }` (object literal implementing `ILogsService` from `./domains/system/logsService`).

```ts
async getLogs(filters: LogFilter = {}, _page?: number, pageSize?: number): Promise<ApiResponse<PaginatedResponse<LogEntry>>>
async getLogById(id: string): Promise<ApiResponse<LogEntry>>
async getLogSources(): Promise<ApiResponse<{ value: string; label: string; count: number }[]>>
async getLogStats(): Promise<ApiResponse<{
  total: number;
  byLevel: Record<string, number>;
  bySource: Record<string, number>;
  recentActivity: number;
  frontendLogs: number;
  backendLogs: number;
}>>
async sendLogToBackend(entry: {
  timestamp: string;
  level: string;
  source: string;
  message: string;
  context?: Record<string, unknown>;
  user_agent?: string;
  url?: string;
  session_id?: string;
  trace_id?: string;
}): Promise<ApiResponse<{ id: string }>>
async sendBatchLogsToBackend(entries: Array<{
  timestamp: string;
  level: string;
  source: string;
  message: string;
  context?: Record<string, unknown>;
  user_agent?: string;
  url?: string;
  session_id?: string;
  trace_id?: string;
}>): Promise<ApiResponse<{ sent: number; failed: number }>>
async exportLogs(filters: LogFilter = {}, format: 'csv' | 'json' = 'csv'): Promise<ApiResponse<{ download_url: string }>>
async clearLogs(_olderThan?: string): Promise<ApiResponse<{ message: string; deletedCount: number }>>
addLog(log: LogEntry): void
```

Notes:
- `_page` is accepted (interface compatibility) but unused; `pageSize` defaults to `pageSize || filters.page_size || filters.limit || 100`.
- `clearLogs` accepts `_olderThan` but ignores it (in-memory store has no age-based clear).
- `streamLogs` exists on the interface but is NOT implemented on this object (no WebSocket streaming here).
- `convertLogsToCSV(logs: LogEntry[]): string` is a module-private helper (not exported) used by `exportLogs` for CSV formatting.

## Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/logs/file/recent?<params>` | File-based recent log listing. Response shape `{ items: LogEntry[] }`. Query params: `n` (always set to `Math.min(pageSize * 10, 1000)` — the file endpoint does not paginate, so the client over-fetches and filters client-side), `level`, `log_type` (for source `frontend`/`backend`), `source` (other sources), `search` (full-text), `from`, `to`, `session_id`. Timeout 30000ms. |
| GET | `/api/v1/logs/${id}` | Single log entry by ID. Timeout 10000ms. |
| GET | `/api/v1/logs/sources` | Available log sources. Response shape `{ sources: string[]; total: number }`. Timeout 10000ms. |
| GET | `/api/v1/logs/file/stats` | File-based stats endpoint (per source comments: "Fetch from FILE-based stats endpoint (not database)"). Response shape `{ total_size_mb: number; archive_count: number; files: Record<string, { size_mb: number; exists: boolean }> }`. Timeout 10000ms. |
| POST | `/api/v1/logs/frontend` | Send a single frontend log entry to the backend. `retries: 0`, timeout 2000ms. Response shape `{ id: number; timestamp: string; status: string }`. |
| POST | `/api/v1/logs/frontend/batch` | Send a batch of frontend log entries. Response shape `{ count: number; status: string }`. |

The database-based counterpart endpoints (used by the domain variant, not this file): `GET /api/v1/system/logs` (page/pageSize params), `GET /api/v1/system/logs/sources`, `GET /api/v1/system/logs/stats` (returns snake_case `by_level`, `by_source`, `recent_activity`, `frontend_logs`, `backend_logs`), `GET /api/v1/system/logs/:id`, `DELETE /api/v1/system/logs/clear?olderThan=...`.

## getLogStats mapping (file-based)

`getLogStats` calls `/api/v1/logs/file/stats` and derives the response from file sizes (MB):

| Response field | Derived from |
|---|---|
| `total` | `total_size_mb` |
| `frontendLogs` | `files['frontend.log'].size_mb` |
| `backendLogs` | `files['app.log'].size_mb` |
| `byLevel`, `bySource`, `recentActivity` | always `{}` / `0` (not available from the file endpoint) |

| Dependency | Type | Purpose |
|---|---|---|
| `./apiClient` → `apiClient` | HTTP client (singleton) | All GET/POST requests to the logs endpoints |
| `./logStoreInstance` → `globalLogStore` | In-memory log store (singleton) | Cache and fallback: `getLogs`, `getLogById`, `getSources`, `getStats`, `addLog`, `clearLogs`, `getLength` |
| `./frontendLoggingService` → `frontendLoggingService` | Logging service | Records `error`/`info`/`warning` messages for this service; also the caller that feeds entries in via `addLog` |
| `../types` | TypeScript types (type-only) | `ApiResponse`, `LogEntry`, `LogFilter`, `PaginatedResponse` |
| `./domains/system/logsService` | `ILogsService` interface (type-only) | Contract implemented by this object; sibling database-based implementation |

## Usage Example

```ts
import { logsService } from '../services';

// Fetch recent error logs (file-based endpoint, up to 1000 fetched, client-side page)
const res = await logsService.getLogs(
  { level: 'error', search: 'database', from: '2026-08-01', to: '2026-08-02' },
  1,
  100
);
if (res.data) {
  const page = res.data.data; // LogEntry[]
  console.log(res.data.pagination.total, page.length);
}

// Stats (file sizes in MB)
const stats = await logsService.getLogStats();
console.log(stats.data.total, stats.data.frontendLogs, stats.data.backendLogs);
```

## Data Flow / Notes

- **File-based vs database-based**: comments in `getLogs` and `getLogStats` explicitly state the file endpoint is used ("Fetch from FILE-based endpoint (not database)" / "Fetch from FILE-based stats endpoint (not database)"), implying a database-based stats endpoint exists — that is the domain variant at `/api/v1/system/logs/stats` (snake_case fields). The root service is the file-based implementation; `services/index.ts` exports both (`logsService` = root, `domainLogsService` = domain).
- **Pagination is emulated client-side**: the file endpoint does not paginate. `getLogs` requests `n = Math.min(pageSize * 10, 1000)` entries and returns a `PaginatedResponse` with `page: 1`, `limit: normalizedItems.length`, `total: normalizedItems.length`, `has_more: false`. In-memory fallbacks paginate with `filters.offset`/`filters.limit` (default 50) and compute `page = floor(offset / limit) + 1`.
- **Level normalization**: response items have `level` lower-cased (`item.level?.toLowerCase()`).
- **Source filter mapping**: `frontend`/`backend` sources map to the `log_type` query param; other sources use `source`. Only the first element is used when the filter value is an array.
- **Cache write guard**: fetched logs are added to `globalLogStore` only when the current path does not include `/logs` (prevents feedback loops while the logs page itself is rendering).
- **`sendLogToBackend`**: enabled for debugging; posts a single entry with `retries: 0` and 2000ms timeout; on failure returns `status: 500` with `error.code = 'backend_log_error'` and `id: '0'` (no logging-service call).
- **`exportLogs`**: purely client-side — fetches logs via `getLogs`, builds a JSON or CSV blob (`convertLogsToCSV`; headers `Timestamp,Level,Source,Message,Context`; cells quoted, embedded `"` escaped as `""`), and returns an object URL as `download_url`. On failure returns empty `download_url` with `error.code = 'logs_error'`.
- **`clearLogs`**: clears only the in-memory store (`globalLogStore.clearLogs()`); reports `deletedCount` from the store length before clearing. No backend endpoint is called (unlike the domain variant's `DELETE /api/v1/system/logs/clear`).
- **`addLog`**: synchronous passthrough to `globalLogStore.addLog`, called by `frontendLoggingService`.
- **Fallback semantics**: every read method wraps the API call in try/catch; on error it logs via `frontendLoggingService.error` and returns in-memory store data with `status: 200`. `getLogById` returns `status: 404` with `error.code = 'not_found'` when the store has no match. In `getLogStats`, the no-data success path spreads `{ ...stats }` (no extra fields), while the catch path returns store `stats` directly.

## Related

- `frontend/src/services/index.ts` — re-exports this service as `logsService` (and the domain variant as `domainLogsService`)
- `frontend/src/hooks/useLogs.ts` — main consumer, imports `logsService` from `../services`
- `frontend/src/hooks/useSystemInfo.ts` — imports `logsService` from `../services`
- `frontend/src/services/frontendLoggingService.ts` — writes captured frontend logs into this service via `addLog` and reads its error responses
- `frontend/src/services/domain/HistoryService.ts` — imports the root `logsService` directly from `../logsService`
- `frontend/src/services/domains/system/logsService.ts` — defines the `ILogsService` interface this object implements, and the sibling database-based implementation
- `frontend/src/services/domain/LogManagementService.ts` — consumes the domain variant (`../domains/system/logsService`)
- `frontend/src/services/logStoreInstance.ts` — provides `globalLogStore`, the in-memory cache/fallback
