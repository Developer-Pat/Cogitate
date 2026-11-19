---
title: HistogramTable
type: atlas-component
path: frontend/src/components/history/HistogramTable.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---

# HistogramTable

**Path**: `frontend/src/components/history/HistogramTable.tsx`
**Last Updated**: 2026-08-01

## Purpose

Displays a log message frequency histogram (log-level histogram) as a table on the History page (Log Analysis tab). Each row is a distinct log message grouped by its text, showing how many times it occurred within the selected time range, which components/sources emitted it, which severity levels it appeared at, and its first/last seen timestamps. The component handles three render states: a loading spinner while data is being fetched, an empty state when no logs match the range ("No logs found"), and the data table itself.

## Props Interface

```typescript
interface HistogramTableProps {
  data: LogHistogram[]
  isLoading?: boolean
  maxRows?: number
}
```

- `data` — array of histogram entries (grouped log messages with counts).
- `isLoading` — when `true`, renders a spinner card instead of the table.
- `maxRows` — maximum number of rows to render (default `100`). When `data` is longer, a footer reads "Showing {maxRows} of {data.length} messages".

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `LogHistogram` (from `../../services/domain/HistoryService`) | Type import | Row shape for the table: `message`, `count`, `firstSeen`, `lastSeen`, `sources: string[]`, `levels: string[]` |

No hooks, stores, or services are used internally — the component is a pure presentational component. It also defines a local `formatDate(date: Date)` helper (not exported) that renders timestamps as e.g. "Aug 1, 2:30 PM" (short month, day, hour, minute).

## Usage Example

```tsx
// In src/pages/SystemHistory.tsx (Log Analysis tab)
import HistogramTable from '../components/history/HistogramTable'

const {
  data: histogram,
  isLoading: histogramLoading
} = useLogsHistogram(timeRange)

<HistogramTable
  data={histogram || []}
  isLoading={histogramLoading || statsLoading}
/>
```

## State Used

None — fully controlled via props. The only derived values are local: `displayData` (`data.slice(0, maxRows)`) and `hasMore` (`data.length > maxRows`).

## Related Components

- `frontend/src/pages/SystemHistory.tsx` — the History page that owns the data and renders this component.
- `frontend/src/hooks/useHistory.ts` — `useLogsHistogram(timeRange)` hook that supplies `data`/`isLoading`/`error`/`refetch`.
- `frontend/src/services/domain/HistoryService.ts` — defines `LogHistogram` and `getLogsHistogram()`; the data source is the backend log API, fetched and grouped by message (count, first/last seen, sources, levels).
- `frontend/src/components/history/StatsCards.tsx` — sibling card summarizing the same `LogHistogram[]` data.
- `frontend/src/components/history/IssueAlerts.tsx` — sibling component also consuming histogram-derived data (`frequentErrors`, `spikes`).
