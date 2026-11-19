---
title: LogsTable
type: atlas-component
path: frontend/src/components/logs/LogsTable.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---

# LogsTable

**Path**: `frontend/src/components/logs/LogsTable.tsx`
**Last Updated**: 2026-08-01

## Purpose

Presentational table that renders a list of log entries (`LogEntry[]`) in a DaisyUI zebra-striped table. It displays six columns — Timestamp, Level, Source, Type, Message, Actions — with a level badge per row, a frontend/backend source indicator, and a "View" action button that fires `onLogSelect(log)`. It also handles the three main display states: loading (spinner), error (inline alert + full-row error state), and empty (with debugging hints). The component is fully controlled — it owns no state and receives everything via props.

Key behaviors:
- **Timestamp formatting**: `formatTimestamp` normalizes `"2026-03-20 13:20:39"` / `"2026-03-20T13:20:39"` timestamps (treated as local time) into a localized datetime string with timezone name; invalid/empty timestamps are returned as-is. A tooltip on the column header notes timestamps are shown in the local timezone.
- **Level badges**: rows import the shared `levelBadge.ts` map (`levelBadge(level)`) — one theme-keyed level → DaisyUI semantic badge mapping used by both the table and the detail modal (critical = solid error; the old per-file drifting maps are gone).
- **Source badge**: `getSourceBadge` distinguishes frontend logs (🖥️, tooltip "Frontend log") from backend logs (⚙️, tooltip "Backend log") by checking `log_type === 'frontend'`, source name containing `navigation`/`performance`/`error`, or a truthy `user_agent`.
- **Context count**: when `log.context` has keys, a muted line under the message shows `{N} context fields`.
- **Footer count**: when rows are shown, a footer strip displays "Showing N logs".

## Props Interface

Exact interfaces from the source (both exported and internal):

```typescript
// Exported from LogsTable.tsx (also used by LogViewer)
export interface LogFilters {
  selectedLevel: string
  searchTerm: string
}

interface LogsTableProps {
  logs: LogEntry[]
  logsLoading: boolean
  logsError: Error | null
  onLogSelect: (log: LogEntry) => void
}
```

The `LogEntry` shape (imported from `../../types`, i.e. `frontend/src/types/index.ts`):

```typescript
export interface LogEntry {
  id: number | string;
  timestamp: string;
  level: LogLevel;
  source: string;
  message: string;
  context?: Record<string, unknown>;
  userId?: string;
  sessionId?: string;
  user_agent?: string;
  url?: string;
  trace_id?: string;
  log_type?: 'frontend' | 'backend';
  created_at?: string;
}

export type LogLevel = 'debug' | 'info' | 'warning' | 'error' | 'critical';
```

## Dependencies

| Dependency | Type | Purpose |
| --- | --- | --- |
| `../../types` (`LogEntry`, `LogLevel`) | type import | Data shape of the rows rendered by the table |
| DaisyUI `badge` / `table table-zebra` / `card` / `alert alert-error` / `tooltip` / `loading` | CSS classes (Tailwind + DaisyUI) | Table chrome, level badges, error alert, tooltips, and loading spinner styling |
| Design tokens `--card-shadow`, `--card-radius`, `--card-padding`, `--button-radius`, `--button-padding`, `--button-transition` | CSS custom properties | Card and button styling consistent with the rest of the UI |

No hooks, stores, or services are used — `LogsTable` is a pure presentational component.

## Usage Example

As used by the Logs page (`frontend/src/pages/Logs.tsx`):

```tsx
import LogsTable from '../components/logs/LogsTable'
import type { LogEntry } from '../types'

// In the parent: const [selectedLog, setSelectedLog] = useState<LogEntry | null>(null)
const handleLogSelect = (log: LogEntry) => {
  setSelectedLog(log)
}

<LogsTable
  logs={paginatedLogs}        // client-side filtered + paginated slice of useLogs() data
  logsLoading={logsLoading}    // isLoading from useLogs()
  logsError={logsError}        // error from useLogs()
  onLogSelect={handleLogSelect} // opens LogDetailsModal with the selected log
/>
```

## State Used

None internally. `LogsTable` is fully controlled/presentational — no `useState`, `useEffect`, `useMemo`, or refs. All state lives in the parent page:

- `logs`, `logsLoading`, `logsError` — derived from the `useLogs()` hook in `frontend/src/pages/Logs.tsx` (which fetches up to 1000 logs and filters/paginates client-side via `useLogsFilters`).
- `onLogSelect` — wired to the parent's `selectedLog` state, which drives `LogDetailsModal`.

## Level Badge Styling

`getLevelBadgeStyle(level)` returns `{ cls, label }` per level; the row renders `<div className={`badge ${style.cls} badge-sm font-semibold`}>{style.label}</div>`:

| Level | Badge classes | Label | Notes |
| --- | --- | --- | --- |
| `error`, `critical` | `badge-error` | `ERROR` | DaisyUI error badge; pinkish in night theme → dark text handled by DaisyUI |
| `warning` | `badge-warning` | `WARNING` | Yellow (light) background → DaisyUI contrast |
| `info` | `badge-info` | `INFO` | Cyan (light) background → DaisyUI contrast |
| `debug` | `badge-ghost text-white` | `DEBUG` | Dark gray background → light text |
| anything else | `badge-ghost` | `level.toUpperCase()` | Fallback |

## Related Components

- `frontend/src/pages/Logs.tsx` — parent page; owns all state and renders the table with `paginatedLogs`.
- `frontend/src/components/logs/LogFilters.tsx` — sibling filter bar above the table; its props mirror the exported `LogFilters` interface.
- `frontend/src/components/logs/LogDetailsModal.tsx` — opens with the log passed to `onLogSelect` ("View" button target).
- `frontend/src/components/features/debugging/LogViewer.tsx` — separate consumer of the exported `LogFilters` interface.
- `frontend/src/hooks/useLogsFilters.ts` — hook used by the page to apply level/source filters client-side before passing rows down.
- `frontend/src/hooks/useLogs.ts` / `useLogStats.ts` — data hooks feeding `logsLoading` / `logsError` / `logs` on the page.
