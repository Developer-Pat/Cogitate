---
title: LogViewer
type: atlas-component
path: frontend/src/components/features/debugging/LogViewer.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# LogViewer

**Path**: `frontend/src/components/features/debugging/LogViewer.tsx`
**Last Updated**: 2026-08-01

## Purpose

The debugging log viewer for the frontend. It displays recent application logs in a scrollable card, with client-side filtering by log level, source, time range, and free-text search. Logs come from the **real backend** via `logManagementService` (API base path `/api/v1/logs`, e.g. `GET /api/v1/logs/recent`) — the component is **not** fed simulated data; it fails loudly (logging `BACKEND API NOT AVAILABLE`) when the backend endpoint is missing. It also supports live SSE log streaming (`streamLogs`), manual refresh, JSON/CSV export (client-side blob download), clearing frontend logs, and an inline logging-config panel. The component is a **named export** (`export const LogViewer`), not a default export.

## Props Interface

Exact interfaces from the source (the props interface itself is module-private; `LogFilters` is exported):

```typescript
interface LogViewerProps {
  onLogFilter?: (filters: LogFilters) => void
  onLogExport?: (format: 'json' | 'csv') => void
  enableStreaming?: boolean
}

export interface LogFilters {
  level: string[]
  source: string[]
  timeRange: {
    start: string
    end: string
  }
  search: string
}
```

`enableStreaming` defaults to `true`; it gates whether the SSE log stream is started on mount.

## Dependencies

| Dependency | Type | Purpose |
| --- | --- | --- |
| `useState` / `useEffect` | React hooks | Local state; on mount loads recent logs, subscribes to service updates, starts SSE streaming; cleanup unsubscribes/stopping streaming |
| `logManagementService` | Domain service singleton (`frontend/src/services/domain/LogManagementService.ts`) | Data source — `loadRecentLogs(100)` against the real `/api/v1/logs` backend, subscriber pattern for log updates, `streamLogs`/`stopStreaming` (SSE via `EventSource`), `exportLogs`, `clearFrontendLogs` |
| `frontendLoggingService` | Logging service (`frontend/src/services/frontendLoggingService.ts`) | Component-level `debug`/`info`/`error` logging (mount, filters changed, refresh, export, failures) |
| `ErrorBoundary` | Component (`frontend/src/components/ErrorBoundary.tsx`) | Wraps the entire rendered output to catch render errors |
| `LoggingConfigPanel` | Component (`frontend/src/components/settings/LoggingConfigPanel.tsx`) | Settings panel rendered below the log list when the ⚙ Settings toggle is on |
| `LogEntry`, `LogFilter` | Types (`frontend/src/types/index.ts`) | Log row model (`id`, `timestamp`, `level`, `source`, `message`, `context`, `trace_id`, `userId`, ...) and backend filter shape |

## Usage Example

```tsx
import { LogViewer, type LogFilters } from '../components/features/debugging/LogViewer'

const handleFilter = (filters: LogFilters) => {
  // e.g. sync filter state to a parent or URL
}

<LogViewer
  onLogFilter={handleFilter}
  onLogExport={(format) => console.log('exported as', format)}
  enableStreaming
/>
```

## State Used

- `logs` — `ServiceLogEntry[]`; the latest log list pushed by the service subscriber (`logManagementService.subscribe`)
- `filters` — `LogFilters`; `level`/`source` arrays, `timeRange` (defaults to the last hour: now − 3600000 ms → now), `search`
- `showConfig` — toggles the `LoggingConfigPanel`
- `isStreaming` — live-stream state backing the `● Live / ○ Live` button
- `isLoading` — shows the loading spinner during initial load and manual refresh
- `_unused` — leftover no-op state (dead code in current source)

## Behavior Notes

- **Filtering is client-side**: `filteredLogs` is derived from the in-memory `logs` array — level (exact match on `level`), source (substring match via `source.includes`), time range (timestamp within `start`/`end`), and search (case-insensitive substring on `message`).
- **Level filtering**: multi-select `<select>` over `debug`, `info`, `warning`, `error`, `critical`; the summary strip shows total + per-level counts (level counts are computed over all loaded logs, not the filtered subset).
- **Search**: free-text input matching `log.message.toLowerCase().includes(search.toLowerCase())`.
- **Scroll behavior**: **not virtualized** — all filtered rows are rendered with a plain `.map()` inside a `<div className="space-y-2 max-h-96 overflow-y-auto">` (CSS-only scroll region capped at 24rem). The list is bounded by the 100-log `loadRecentLogs(100)` limit.
- **Data source**: real backend logs (`/api/v1/logs` family) — initial load of the most recent 100 entries, background sync + SSE streaming via the service, and an explicit fail-loud error path when the backend is unreachable. Not simulated.

## Related Components

- `LoggingConfigPanel` — `frontend/src/components/settings/LoggingConfigPanel.tsx` (rendered inline when Settings is open)
- `ErrorBoundary` — `frontend/src/components/ErrorBoundary.tsx`
- Consumed by the `Debugging` page — `frontend/src/pages/Debugging.tsx` (imports `LogViewer` and `LogFilters`)
