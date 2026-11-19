---
title: useHistory
type: atlas-hook
path: frontend/src/hooks/useHistory.ts
confidence: high
updated: 2026-08-01
tags: [type/hook, domain/atlas-ui]
---

# useHistory

**Path**: `frontend/src/hooks/useHistory.ts`
**Type**: hook

## Purpose

Nine TanStack Query hooks that back the System History page (`pages/SystemHistory.tsx`). Every hook wraps one method of the shared `historyService` singleton (`frontend/src/services/domain/HistoryService.ts`, 818 lines), which computes historical insights on demand — the service's own philosophy is "pure function: logs → insights" (no Zustand store, no persistence, compute on demand). Two data sources feed the service: backend logs via `logsService` (log histogram, log stats, issue detection) and the in-memory `sessionsService` cache of database sessions (message performance, message length distribution, provider/model stats, session analysis). All queries use `staleTime: 0` (always stale) and `refetchOnWindowFocus: true`; there is no polling and no SSE — data is pulled on mount, on argument change, and on manual `refetch()`.

## Exported API

All nine hooks return the standard TanStack Query `UseQueryResult<T>` shape (`data`, `isLoading`, `isError`, `error`, `refetch`, ...). The result type `T` is listed per hook. All result types (`TimeRange`, `HistogramOptions`, `LogHistogram`, `IssueReport`, `MessagePerformance`, `MessageLengthDistribution`, `ProviderStats`, `MessageAnalysis`, `SessionAnalysisSummary`, `SessionAnalysisResult`) are defined in `services/domain/HistoryService.ts`.

### `useLogsHistogram(timeRange: TimeRange, options?: Omit<HistogramOptions, 'timeRange'>)`

```ts
export function useLogsHistogram(timeRange: TimeRange, options?: Omit<HistogramOptions, 'timeRange'>)
// -> UseQueryResult<LogHistogram[]>
```

- Query key: `['logs-histogram', timeRange, options]` — both the range and the options are part of the key, so changing either creates a distinct cached query.
- Query function: `historyService.getLogsHistogram({ timeRange, ...options })` → `Promise<LogHistogram[]>`, where `LogHistogram = { message: string; count: number; firstSeen: Date; lastSeen: Date; sources: string[]; levels: string[] }`, sorted by `count` descending.
- `HistogramOptions = { timeRange?: TimeRange; minCount?: number; groupSimilar?: boolean }` — `groupSimilar` is marked "(future feature)" in the service; `minCount` defaults to 1.
- Backed by `logsService.getLogs(filters, 1, 100)` — the service only fetches the first page (≤ 100 logs), so the histogram is computed from a capped sample.
- `staleTime: 0`, `refetchOnWindowFocus: true`.

### `useHistoryStats(timeRange?: TimeRange)`

```ts
export function useHistoryStats(timeRange?: TimeRange)
// -> UseQueryResult<{
//      totalLogs: number
//      uniqueMessages: number
//      errorCount: number
//      warningCount: number
//      topSources: { source: string; count: number }[]
//    }>
```

- Query key: `['history-stats', timeRange]`.
- Query function: `historyService.getStats(timeRange)` — same single-page (≤ 100 log) sample as the histogram; `topSources` is the top 10 sources by count.
- `staleTime: 0`, `refetchOnWindowFocus: true`.

### `useHistoryIssues()`

```ts
export function useHistoryIssues()
// -> UseQueryResult<IssueReport>
```

- Query key: `['history-issues']` — takes no arguments, so a single shared query.
- Query function: `historyService.detectIssues()` → `IssueReport = { frequentErrors: LogHistogram[]; spikes: LogHistogram[]; timestamp: Date }`. `frequentErrors` are histogram entries whose levels include `error`/`critical`; `spikes` are entries with count > 2× the average count (the service's `detectSpikes` heuristic).
- `staleTime: 5000` — the only hook that does not use `staleTime: 0`; data is considered fresh for 5 seconds.

### `useMessageAnalysis(timeRange?: TimeRange)`

```ts
export function useMessageAnalysis(timeRange?: TimeRange)
// -> UseQueryResult<MessageAnalysis>
```

- Query key: `['message-analysis', timeRange]`.
- Query function: `historyService.getMessageAnalysis(timeRange)` → `MessageAnalysis = { performance: MessagePerformance; distribution: MessageLengthDistribution; providerStats: ProviderStats[]; timeRange?: TimeRange }`.
- The service runs `getMessagePerformance` + `getMessageLengthDistribution` + `getProviderModelStats` concurrently via `Promise.all`; the hook exposes the combined result under one query key.
- `staleTime: 0`, `refetchOnWindowFocus: true`; source comment: "Always enabled - will fetch all data if no timeRange provided".

### `useMessagePerformance(timeRange?: TimeRange)`

```ts
export function useMessagePerformance(timeRange?: TimeRange)
// -> UseQueryResult<MessagePerformance>
```

- Query key: `['message-performance', timeRange]`.
- Query function: `historyService.getMessagePerformance(timeRange)` → `MessagePerformance = { averageTokenCount: number; averageDurationMs: number; averageTokensPerSecond: number; totalMessages: number; fastestProvider: string; fastestModel: string }`.
- Computed from assistant messages carrying `metadata.tokenCount` / `metadata.totalTimeMs` / `metadata.tokensPerSecond`, sourced from the `sessionsService` cache (database data, not logs).
- `staleTime: 0`, `refetchOnWindowFocus: true`. (Exported and re-exported but not currently consumed by any page — see Related.)

### `useMessageDistribution(timeRange?: TimeRange)`

```ts
export function useMessageDistribution(timeRange?: TimeRange)
// -> UseQueryResult<MessageLengthDistribution>
```

- Query key: `['message-distribution', timeRange]`.
- Query function: `historyService.getMessageLengthDistribution(timeRange)` → `MessageLengthDistribution = { short: number; medium: number; long: number; veryLong: number }` — counts of assistant messages with content by character length: `< 100`, `100–500`, `500–1000`, `> 1000`.
- `staleTime: 0`, `refetchOnWindowFocus: true`. (Exported but not currently consumed by any page.)

### `useProviderModelStats(timeRange?: TimeRange)`

```ts
export function useProviderModelStats(timeRange?: TimeRange)
// -> UseQueryResult<ProviderStats[]>
```

- Query key: `['provider-model-stats', timeRange]`.
- Query function: `historyService.getProviderModelStats(timeRange)` → `ProviderStats[]`, each `{ provider: string; model?: string; messageCount: number; avgTokenCount: number; avgDurationMs: number; avgTokensPerSecond: number }`, grouped by `provider:model` key and sorted by `messageCount` descending.
- `staleTime: 0`, `refetchOnWindowFocus: true`. (Exported but not currently consumed by any page.)

### `useSessionAnalysis(limit: number = 10)`

```ts
export function useSessionAnalysis(limit: number = 10)
// -> UseQueryResult<SessionAnalysisResult>
```

- Query key: `['session-analysis', limit]`.
- Query function: `historyService.getLastSessionsAnalysis(limit)` → `SessionAnalysisResult = { sessions: SessionAnalysisSummary[]; totalSessions: number; totalMessages: number; totalTokens: number; avgMessagesPerSession: number; avgTokensPerSession: number; avgSessionDurationMs: number; limit: number }`, where `SessionAnalysisSummary = { sessionId: string; title: string; agentId: string; messageCount: number; totalTokens: number; avgResponseTimeMs: number; avgTokensPerSecond: number; createdAt: Date; updatedAt: Date; duration: number }` (duration = ms from first to last message).
- `enabled: limit > 0` — the query is disabled (no fetch) when `limit` is 0 or negative.
- `staleTime: 0`, `refetchOnWindowFocus: true`.

### `useSessionSummary(limit: number = 10)`

```ts
export function useSessionSummary(limit: number = 10)
// -> UseQueryResult<{
//      totalSessions: number
//      totalMessages: number
//      totalTokens: number
//      avgMessagesPerSession: number
//      avgTokensPerSession: number
//    }>
```

- Query key: `['session-summary', limit]`.
- Query function: `historyService.getSessionSummary(limit)` — delegates to `getLastSessionsAnalysis(limit)` and projects the five aggregate fields.
- `staleTime: 0`, `refetchOnWindowFocus: true`. (Exported but not currently consumed by any page.)

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `@tanstack/react-query` | external (npm) | `useQuery` — server-state caching, per-argument query keys, window-focus refetch |
| `historyService` (from `../services/domain/HistoryService`) | internal service singleton | All nine wrapped methods: `getLogsHistogram`, `getStats`, `detectIssues`, `getMessageAnalysis`, `getMessagePerformance`, `getMessageLengthDistribution`, `getProviderModelStats`, `getLastSessionsAnalysis`, `getSessionSummary` |
| `TimeRange` (from HistoryService) | internal type | `{ from: Date; to: Date }` — optional time filter on seven of the nine hooks |
| `HistogramOptions` (from HistoryService) | internal type | `{ timeRange?; minCount?; groupSimilar? }` — options for `useLogsHistogram` |
| `logsService` (from `../logsService`, transitive via HistoryService) | internal service | Backend log API — `getLogs(filters, page 1, page_size 100)` feeds histogram, log stats, and issue detection |
| `sessionsService` (from `./SessionsService`, transitive via HistoryService) | internal service | In-memory session cache — `getSessions()` (database data) feeds message performance, length distribution, provider/model stats, and session analysis |

## Usage Example

```tsx
import { useState } from 'react';
import {
  useLogsHistogram,
  useHistoryStats,
  useHistoryIssues,
  useMessageAnalysis,
  useSessionAnalysis
} from '../hooks';

function HistoryPanel() {
  // Last 24 hours, matching the System History page default
  const timeRange = {
    from: new Date(Date.now() - 24 * 60 * 60 * 1000),
    to: new Date()
  };
  const [sessionLimit, setSessionLimit] = useState(10);

  const histogram = useLogsHistogram(timeRange);
  const stats = useHistoryStats(timeRange);
  const issues = useHistoryIssues();
  const messageAnalysis = useMessageAnalysis(timeRange);
  const sessionAnalysis = useSessionAnalysis(sessionLimit);

  if (histogram.isLoading || stats.isLoading) return <div>Loading…</div>;

  return (
    <div>
      <h2>{stats.data?.totalLogs} logs, {stats.data?.errorCount} errors</h2>
      {issues.data?.frequentErrors.map((e) => (
        <p key={e.message}>{e.message} × {e.count}</p>
      ))}
      <p>Avg tokens/sec: {messageAnalysis.data?.performance.averageTokensPerSecond}</p>
      <button onClick={() => sessionAnalysis.refetch()}>
        Re-analyze {sessionLimit} sessions
      </button>
    </div>
  );
}
```

## State / Data Flow

- **No local state** — all server state lives in the TanStack Query cache under nine key families: `['logs-histogram', timeRange, options]`, `['history-stats', timeRange]`, `['history-issues']`, `['message-analysis', timeRange]`, `['message-performance', timeRange]`, `['message-distribution', timeRange]`, `['provider-model-stats', timeRange]`, `['session-analysis', limit]`, `['session-summary', limit]`. Changing `timeRange`/`limit`/`options` creates a new cached query; the page re-renders with that query's loading/error/data states.
- **No SSE, no polling** — all data is pulled on demand via `useQuery`. `staleTime: 0` makes data always stale, and `refetchOnWindowFocus: true` refreshes when the tab regains focus. The System History page's Refresh buttons call the returned `refetch()`; the Session Analysis "Generate" button calls `refetchSessionAnalysis()`.
- **Two data sources inside the service**:
  - Log-derived (histogram, stats, issues): `logsService.getLogs(filters, 1, 100)` with `from`/`to` formatted by `formatDateTimeForBackend` (ISO without milliseconds, `+00:00` suffix) for Python `fromisoformat()` compatibility. Only the first page (≤ 100 logs) is analyzed — no multi-page pagination.
  - Session/message-derived (performance, distribution, provider stats, session analysis): `sessionsService.getSessions()` cache, filtered client-side by `timeRange` when provided.
- **Query options**: all hooks use `staleTime: 0` + `refetchOnWindowFocus: true` except `useHistoryIssues` (`staleTime: 5000`) and `useSessionAnalysis` (`enabled: limit > 0`).
- **LiveMonitoringService**: no relationship — `useHistory` never touches `LiveMonitoringService` (`src/services/domain/LiveMonitoringService.ts`, WebSocket-based real-time activity events). That service feeds the Debugging page's `LiveMonitoring` component (`pages/Debugging.tsx`, `components/features/debugging/LiveMonitoring.tsx`), which is a separate feature from the System History page.

## Related

- **Consumers**: `pages/SystemHistory.tsx` — uses `useLogsHistogram`, `useHistoryStats`, `useHistoryIssues`, `useMessageAnalysis` (Log Analysis and Message Analysis tabs) and `useSessionAnalysis` (Session Analysis tab). `timeRange` state defaults to the last 24 hours; `sessionLimit` defaults to 10. Child components receive the data via props: `StatsCards`, `HistogramTable`, `IssueAlerts`, `MessagePerformanceCards`, `MessageDistributionChart`, `ProviderComparisonTable`, `SessionSummaryCards`, `SessionCards`, `SessionAnalysisControls` (all in `components/history/`).
- **Re-export**: `frontend/src/hooks/index.ts` re-exports all nine hooks (the "History Hooks" block).
- **Currently unconsumed exports**: `useMessagePerformance`, `useMessageDistribution`, `useProviderModelStats`, and `useSessionSummary` are exported and re-exported but have no page/component consumers — their functionality is reached through the combined `useMessageAnalysis` and `useSessionAnalysis` on the System History page.
- **Service**: `historyService` singleton (`frontend/src/services/domain/HistoryService.ts`, 818 lines); transitive `logsService` (`frontend/src/services/logsService.ts`) and `sessionsService` (`frontend/src/services/domain/SessionsService.ts`).
- **Types**: `TimeRange`, `HistogramOptions`, `LogHistogram`, `IssueReport`, `MessagePerformance`, `MessageLengthDistribution`, `ProviderStats`, `MessageAnalysis`, `SessionAnalysisSummary`, `SessionAnalysisResult` — all defined in `HistoryService.ts`.
