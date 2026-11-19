---
title: History Service
type: atlas-service
path: frontend/src/services/domain/HistoryService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# History Service

**Path**: `frontend/src/services/domain/HistoryService.ts`
**Type**: service

## Purpose
Client-side log/session analysis service for "historical insights". Per the source header philosophy: history is derived from logs (single source of truth), the service itself has no Zustand store dependency (pure log/session analysis), no persistence (compute on-demand), and is a pure function of `logs → insights`. It exposes log histogram / top-messages / stats / issue-detection computed over fetched log entries, plus message performance, message length distribution, provider/model stats, and session analysis computed from cached sessions data. There are **no dedicated history endpoints** — all analysis happens client-side over data fetched through `logsService` and the `SessionsService` cache.

## Exported API
Multi-export file: 10 interfaces, 1 class (`HistoryService`), and 1 singleton instance (`historyService`).

### Interfaces (exact)
```ts
interface LogHistogram {
  message: string
  count: number
  firstSeen: Date
  lastSeen: Date
  sources: string[]
  levels: string[]
}

interface TimeRange {
  from: Date
  to: Date
}

interface HistogramOptions {
  timeRange?: TimeRange
  minCount?: number           // Minimum count threshold (filter out rare messages)
  groupSimilar?: boolean      // Group similar messages by pattern (future feature — NOT implemented)
}

interface IssueReport {
  frequentErrors: LogHistogram[]
  spikes: LogHistogram[]
  timestamp: Date
}

interface MessagePerformance {
  averageTokenCount: number
  averageDurationMs: number
  averageTokensPerSecond: number
  totalMessages: number
  fastestProvider: string
  fastestModel: string
}

interface MessageLengthDistribution {
  short: number    // < 100 chars
  medium: number   // 100-500 chars
  long: number     // 500-1000 chars
  veryLong: number // > 1000 chars
}

interface ProviderStats {
  provider: string
  model?: string
  messageCount: number
  avgTokenCount: number
  avgDurationMs: number
  avgTokensPerSecond: number
}

interface MessageAnalysis {
  performance: MessagePerformance
  distribution: MessageLengthDistribution
  providerStats: ProviderStats[]
  timeRange?: TimeRange
}

interface SessionAnalysisSummary {
  sessionId: string
  title: string
  agentId: string
  messageCount: number
  totalTokens: number
  avgResponseTimeMs: number
  avgTokensPerSecond: number
  createdAt: Date
  updatedAt: Date
  duration: number // ms from first to last message
}

interface SessionAnalysisResult {
  sessions: SessionAnalysisSummary[]
  totalSessions: number
  totalMessages: number
  totalTokens: number
  avgMessagesPerSession: number
  avgTokensPerSession: number
  avgSessionDurationMs: number
  limit: number
}
```

### `class HistoryService` methods (exact signatures)
```ts
async getLogsHistogram(options?: HistogramOptions): Promise<LogHistogram[]>          // fetch logs, group by message, minCount filter, sort by count desc
async getTopMessages(limit: number = 20): Promise<LogHistogram[]>                     // histogram.slice(0, limit)
async getLogsByTimeRange(timeRange: TimeRange): Promise<LogEntry[]>                   // fetch logs with from/to filters
async detectIssues(): Promise<IssueReport>                                            // frequentErrors = histogram entries with level 'error'|'critical'; spikes = detectSpikes()
async getStats(timeRange?: TimeRange): Promise<{
  totalLogs: number
  uniqueMessages: number
  errorCount: number
  warningCount: number
  topSources: { source: string; count: number }[]                                    // top 10 by count
}>
async getMessagePerformance(timeRange?: TimeRange): Promise<MessagePerformance>       // from sessions cache; assistant msgs w/ metadata.tokenCount|totalTimeMs; fastest provider/model by avg tokensPerSecond
async getMessageLengthDistribution(timeRange?: TimeRange): Promise<MessageLengthDistribution> // from sessions cache; assistant msgs w/ content; char buckets <100 / <500 / <1000 / else
async getProviderModelStats(timeRange?: TimeRange): Promise<ProviderStats[]>          // grouped by `${provider}:${model || 'unknown'}`, sorted by messageCount desc
async getMessageAnalysis(timeRange?: TimeRange): Promise<MessageAnalysis>             // Promise.all of the three above
async getLastSessionsAnalysis(limit: number = 10): Promise<SessionAnalysisResult>     // cached sessions sorted by updatedAt desc; per-session totals from metadata
async getSessionSummary(limit: number = 10): Promise<{
  totalSessions: number
  totalMessages: number
  totalTokens: number
  avgMessagesPerSession: number
  avgTokensPerSession: number
}>                                                                                    // wrapper over getLastSessionsAnalysis
```
Private helpers: `formatDateTimeForBackend(date: Date): string` (ISO string without milliseconds, `Z` → `+00:00`, for Python `fromisoformat()` compatibility) and `detectSpikes(histogram: LogHistogram[]): LogHistogram[]` (messages with count > 2× average).

### Singleton export
```ts
export const historyService = new HistoryService()   // line 818
```

## Endpoints
No dedicated history endpoints — analysis is fully client-side over fetched data:
- `GET /api/v1/logs/file/recent?n=<N>&from=<iso>&to=<iso>&level=&source=&search=&session_id=` — via `logsService.getLogs(filters, 1, 100)` from `getLogsHistogram`, `getLogsByTimeRange`, `getStats`, `detectIssues`. `logsService` multiplies page size by 10 for `n` (capped at 1000); `from`/`to` are formatted by `formatDateTimeForBackend`.
- `GET /api/v1/logs/system/recent` — exists in `logsService` for the dedicated system-log source only; HistoryService never sets that filter, so this endpoint is not hit by this service.
- Session-derived methods (`getMessagePerformance`, `getMessageLengthDistribution`, `getProviderModelStats`, `getMessageAnalysis`, `getLastSessionsAnalysis`, `getSessionSummary`) make **no API calls** — they read `sessionsService.getSessions()` (Zustand `cognitiveHubStore` cache, background-synced by `sessionSyncService`).

## Dependencies
| Dependency | Type | Purpose |
|---|---|---|
| `logsService` (`../logsService`) | singleton object | Fetches log entries from `GET /api/v1/logs/file/recent` with in-memory `globalLogStore` fallback; source of data for all log-derived methods |
| `sessionsService` (`./SessionsService`) | class instance | Reads sessions/messages from Zustand `cognitiveHubStore` cache (no API call); store populated in background by `sessionSyncService` |
| `LogEntry`, `LogFilter` (`../../types`) | types | Log entry shape and filter type used by log-derived methods |
| `useQuery` (@tanstack/react-query) | library (in `useHistory` hook) | Wraps service calls as cached queries with `staleTime: 0` / `refetchOnWindowFocus: true` |

## Usage Example
```ts
import { historyService } from '../services/domain/HistoryService'

// Log-derived analysis
const histogram = await historyService.getLogsHistogram({ minCount: 3 })
const stats = await historyService.getStats({ from, to })
const issues = await historyService.detectIssues()

// Session-derived analysis (no API call — reads sessions cache)
const analysis = await historyService.getMessageAnalysis()
const sessionAnalysis = await historyService.getLastSessionsAnalysis(10)
```

Via hooks (as used in `SystemHistory.tsx`):
```ts
const { data: stats } = useHistoryStats(timeRange)
const { data: issues } = useHistoryIssues()
```

## Data Flow / Notes
- **Log-derived path**: `HistoryService` → `logsService.getLogs` → `GET /api/v1/logs/file/recent` → client-side grouping/counting (histogram, top messages, stats, issue detection). Computed on demand, never persisted.
- **Session-derived path**: `HistoryService` → `sessionsService.getSessions()` (Zustand cache) → client-side aggregation of per-message metadata (`tokenCount`, `totalTimeMs`, `tokensPerSecond`, `provider`, `model`) and content length.
- **Fetch-window limitation**: log methods request page 1 with pageSize 100 (which `logsService` expands to `n` up to 1000); histogram/stats/issues only reflect that single fetch window.
- **Spike heuristic**: `detectSpikes` flags messages whose count exceeds 2× the mean histogram count.
- Performance stats only count assistant messages carrying `metadata.tokenCount` / `metadata.totalTimeMs`; `getProviderModelStats` uses `'unknown'` fallbacks for missing provider/model.
- `getLastSessionsAnalysis` sorts the cached array in place via `.sort()` on `updatedAt` (descending).
- The file contains many commented-out `traceService.trace(...)` calls (dead code).

## Related
- `frontend/src/hooks/useHistory.ts` — exports `useLogsHistogram`, `useHistoryStats`, `useHistoryIssues`, `useMessageAnalysis`, `useMessagePerformance`, `useMessageDistribution`, `useProviderModelStats`, `useSessionAnalysis`, `useSessionSummary`; all wrap `historyService` in `useQuery`.
- `frontend/src/pages/SystemHistory.tsx` — the only page consuming the hooks (`useHistoryStats`, `useHistoryIssues`).
- Depends on `logsService` (`services/logsService.ts`), `SessionsService` (`services/domain/SessionsService.ts`), `cognitiveHubStore` (Zustand), `sessionSyncService`.

## Deprecation / Obsolete Notes
- **No deprecation markers**: no `@deprecated`, "legacy", or "unused" markers — and no unfinished-work markers — in `HistoryService.ts` itself.
- **Service is live, not dead**: `historyService` is imported by `useHistory.ts`, and `useHistoryStats` + `useHistoryIssues` are consumed by the `SystemHistory.tsx` page.
- **Partially unused API**: 7 of the 9 exported hooks have zero consumers anywhere in `frontend/src` — `useLogsHistogram`, `useMessageAnalysis`, `useMessagePerformance`, `useMessageDistribution`, `useProviderModelStats`, `useSessionAnalysis`, `useSessionSummary` (and their underlying service methods: `getTopMessages`, `getLogsByTimeRange`, `getMessagePerformance`, `getMessageLengthDistribution`, `getProviderModelStats`, `getMessageAnalysis`, `getLastSessionsAnalysis`, `getSessionSummary`). The session/message-analysis half of the service is currently exercised only through `useHistoryStats`' sibling paths or not at all; flag for possible removal or planned UI.
- `groupSimilar` in `HistogramOptions` is explicitly marked "(future feature)" in the source and is ignored by `getLogsHistogram`.
