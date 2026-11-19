---
title: useLogs
type: atlas-hook
path: frontend/src/hooks/useLogs.ts
confidence: high
updated: 2026-08-01
tags: [type/hook, domain/atlas-ui]
---

# useLogs

**Path**: `frontend/src/hooks/useLogs.ts`
**Type**: hook

## Purpose

TanStack Query-backed hooks for the system logs feature. The module exports four hooks: `useLogs` (paginated log feed with 1-second active-page polling), `useLogSources` (available log sources), `useLogStats` (log-file statistics, polled in sync with `useLogs`), and `useClearLogs` (admin clear-logs mutation). All four wrap methods on the shared `logsService` singleton imported from `../services`; service errors are converted to thrown `Error`s so failures surface through TanStack Query's `error` state.

## Exported API

### `useLogs(filters?: LogFilter)`

```ts
export function useLogs(filters: LogFilter = {}): UseQueryResult<any>
```

- Query key: `['logs', filters]` — the filters object is part of the key, so changing filters creates a distinct cached query.
- Query function: `logsService.getLogs(filters, filters.page, filters.page_size)`; returns `response.data` (a `PaginatedResponse<LogEntry>`: `{ data: LogEntry[], pagination: { page, limit, total }, has_more }`).
- Throws `new Error(response.error.message)` when `response.error` is present.
- `retry: false` — never retries failed fetches (prevents error loops).
- `refetchInterval: 1000` — refreshes every 1 second while the page is active.
- `refetchIntervalInBackground: false` — no polling while the tab is inactive.
- `refetchOnWindowFocus: true` — refreshes when the user returns to the page.
- `staleTime: 0` — data is always considered stale (force refresh).

### `useLogSources()`

```ts
export function useLogSources(): UseQueryResult<{ value: string; label: string; count: number }[]>
```

- Query key: `['log-sources']`.
- Query function: `logsService.getLogSources()`; returns `response.data`, an array of `{ value, label, count }` (count is always 0 — the API only returns source names).
- Throws `new Error(response.error.message)` when `response.error` is present.
- `staleTime: 300000` — data considered stale after 5 minutes (no polling).

### `useLogStats()`

```ts
export function useLogStats(): UseQueryResult<{
  total: number;                          // total_size_mb of all log files
  byLevel: Record<string, number>;        // always {} (file endpoint does not break down by level)
  bySource: Record<string, number>;       // always {} (file endpoint does not break down by source)
  recentActivity: number;                 // always 0
  frontendLogs: number;                   // size_mb of frontend.log
  backendLogs: number;                    // size_mb of app.log
}>
```

- Query key: `['log-stats-v2']`.
- Query function: `logsService.getLogStats()`; returns `response.data` with the shape above.
- Throws `new Error(response.error.message)` when `response.error` is present.
- `refetchInterval: 1000` — synced with `useLogs` (1 second).
- `refetchIntervalInBackground: false`, `refetchOnWindowFocus: true`.

### `useClearLogs()`

```ts
export function useClearLogs(): UseMutationResult<{ message: string; deletedCount: number }, Error, void>
```

- `mutationFn`: `logsService.clearLogs()`; throws `new Error(response.error.message)` when `response.error` is present; returns `response.data` (`{ message: string; deletedCount: number }`).
- `onSuccess`: invalidates all log-related queries via `queryClient.invalidateQueries({ queryKey: ['logs'] })` and `queryClient.invalidateQueries({ queryKey: ['log-stats'] })` (prefix matching covers `['logs', filters]` and `['log-stats-v2']`).
- Returns the `useMutation` result object (`mutate`, `mutateAsync`, `isPending`, `isError`, `error`, ...).
- Admin only: clears the in-memory log store; no backend endpoint is called.

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `@tanstack/react-query` | external (npm) | `useQuery`, `useMutation`, `useQueryClient` — server-state caching, 1s polling, window-focus refetch, query invalidation |
| `logsService` (from `../services`) | internal service singleton | API calls: `getLogs`, `getLogSources`, `getLogStats`, `clearLogs` |
| `LogFilter` (from `../types`) | internal type | Filter shape: `level`, `source`, `sourceType`, `startDate`, `endDate`, `from`, `to`, `search`, `limit`, `offset`, `page`, `page_size`, `session_id`, `user_id` |

> **Service resolution note**: `frontend/src/services/index.ts` imports two log services — the root `./logsService` (`src/services/logsService.ts`, ~484 lines, in-memory store + backend API with fallback) and `./domains/system/logsService` (`src/services/domains/system/logsService.ts`, ~150 lines, pure API client). Only the root one is exported as `logsService` (the domain one is re-exported separately as `domainLogsService`). This hook's `import { logsService } from '../services'` therefore resolves to the **root** service.

## Usage Example

```tsx
import { useLogs, useLogStats, useClearLogs } from '../hooks';

function LogsViewer() {
  const { data, isLoading, error } = useLogs({ level: 'error', limit: 100 });
  const stats = useLogStats();
  const clearLogs = useClearLogs();

  if (isLoading) return <div>Loading…</div>;
  if (error) return <div>{(error as Error).message}</div>;

  return (
    <div>
      <p>{stats.data?.total ?? 0} MB total log size</p>
      <button onClick={() => clearLogs.mutate()} disabled={clearLogs.isPending}>
        Clear logs
      </button>
      <ul>
        {data?.data?.map((log) => (
          <li key={log.id}>{log.timestamp} [{log.level}] {log.source}: {log.message}</li>
        ))}
      </ul>
    </div>
  );
}
```

## State / Data Flow

- **No local state** — all server state lives in the TanStack Query cache under three key families: `['logs', filters]`, `['log-sources']`, `['log-stats-v2']`. `useClearLogs` holds only mutation state (`isPending`, `error`, ...).
- **Polling**: `useLogs` and `useLogStats` refetch every 1 second, but only while the tab is visible (`refetchIntervalInBackground: false`); returning to the tab (`refetchOnWindowFocus: true`) triggers an immediate refetch. `useLogSources` does not poll (5-minute stale time).
- **No SSE** — all data is pulled via REST through the root `logsService` (which uses `apiClient`):
  - `GET /api/v1/logs/file/recent?n=<pageSize*10>&level=&log_type=&source=&search=&from=&to=&session_id=` — file-based log feed; `n` is capped at 1000, pagination is simulated client-side and `has_more` is always `false`.
  - `GET /api/v1/logs/system/recent?n=<pageSize>` — used instead of the file endpoint when the dedicated system source type is selected.
  - `GET /api/v1/logs/sources` — available log sources.
  - `GET /api/v1/logs/file/stats` — log-file stats (`total_size_mb`, `archive_count`, `files`).
  - `clearLogs()` — in-memory only: clears `globalLogStore`; makes no backend call.
- **Error handling**: every queryFn/mutationFn throws `new Error(response.error.message)` when `response.error` is set; `useLogs` additionally sets `retry: false` to avoid refetch loops.
- **Fallback**: the root service falls back to the in-memory `globalLogStore` (`src/services/logStoreInstance.ts`) whenever the backend calls fail, and logs failures via `frontendLoggingService`.

## Related

- **Consumers**: `pages/Logs.tsx` (`useLogs`, `useLogStats`), `components/dashboard/RecentActivity.tsx` (`useLogs({ limit: 5 })`), `hooks/useDashboardData.ts` (`useLogs({ limit: 5 })`, `useLogStats`), `components/logs/LogsTable.tsx` (receives the logs array plus loading/error props).
- **Re-export**: `frontend/src/hooks/index.ts` re-exports all four hooks.
- **Services**: `logsService` (root `src/services/logsService.ts`), `globalLogStore` (`src/services/logStoreInstance.ts`), `apiClient` (`src/services/apiClient.ts`), `frontendLoggingService` (`src/services/frontendLoggingService.ts`).
- **Types**: `LogFilter`, `LogEntry`, `LogLevel`, `ApiResponse`, `PaginatedResponse` (`src/types/index.ts`).
