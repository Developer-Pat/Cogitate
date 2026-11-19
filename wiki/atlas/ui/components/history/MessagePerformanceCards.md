---
title: MessagePerformanceCards
type: atlas-component
path: frontend/src/components/history/MessagePerformanceCards.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# MessagePerformanceCards

**Path**: `frontend/src/components/history/MessagePerformanceCards.tsx`
**Last Updated**: 2026-08-01

## Purpose

Renders a responsive grid of stat cards summarizing message performance metrics on the History page's "Message Analysis" tab: average token count, average response time (duration), average tokens/second, total messages analyzed, and the fastest provider/model.

This is a **live, presentational component** in active use — it shows per-message token/duration stats and is unrelated to any removed feature. (Its name has previously tripped false-positive scans for the removed Performance feature; it is not that feature.)

Render behavior:
- `isLoading` is `true` → 4 skeleton placeholder cards
- `performance` is `undefined`/`null` → renders `null` (nothing)
- otherwise → the metric cards below

## Props Interface

Exact interface from the source:

```typescript
interface MessagePerformanceCardsProps {
  performance?: MessagePerformance
  isLoading?: boolean
}
```

The `performance` prop's shape comes from `MessagePerformance` (type-only import from `../../services/domain/HistoryService`), copied exactly from `frontend/src/services/domain/HistoryService.ts`:

```typescript
export interface MessagePerformance {
  averageTokenCount: number
  averageDurationMs: number
  averageTokensPerSecond: number
  totalMessages: number
  fastestProvider: string
  fastestModel: string
}
```

Metrics rendered per card:
| Card | Field | Formatting |
|---|---|---|
| Avg Token Count | `averageTokenCount` | `toLocaleString()` when > 0, else `N/A` (tokens per message) |
| Avg Response Time | `averageDurationMs` | ms → seconds `(ms / 1000).toFixed(2) + 's'` when > 0, else `N/A` (per message) |
| Avg Speed | `averageTokensPerSecond` | raw value when > 0, else `N/A` (tokens/second) |
| Total Messages | `totalMessages` | `toLocaleString()` (analyzed) |
| Fastest Provider | `fastestProvider` | value or `N/A`; `Fastest` badge when present |
| Fastest Model | `fastestModel` | value or `N/A`; `Fastest` badge when present |

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `MessagePerformance` (`frontend/src/services/domain/HistoryService.ts`) | Type-only import | Defines the `performance` prop shape (token count, duration, tokens/sec, totals, fastest provider/model) |
| `useMessagePerformance` (`frontend/src/hooks/useHistory.ts`) | React Query hook (indirect — consumed by the parent page) | Data source: calls `historyService.getMessagePerformance(timeRange)` with query key `['message-performance', timeRange]`; result flows down as `messageAnalysis?.performance` |
| Tailwind CSS + DaisyUI (`card`, `skeleton`, `badge`, `bg-base-200`, theme text colors) | Styling | Responsive grid (`grid-cols-1 md:grid-cols-2 lg:grid-cols-4`), card chrome, loading skeletons, `Fastest` badges |

The component itself uses no hooks, stores, or services directly — it is a pure function of its props.

## Usage Example

```tsx
// frontend/src/pages/SystemHistory.tsx — "messages" tab
{activeTab === 'messages' && (
  <div className="space-y-6">
    {/* Performance Cards */}
    <MessagePerformanceCards
      performance={messageAnalysis?.performance}
      isLoading={messageLoading}
    />
```

## State Used

None internally — no `useState`, `useEffect`, `useMemo`, or context. All state arrives via props from the parent (`SystemHistory`), which sources it from React Query:

- `performance` ← `messageAnalysis?.performance` (from `useMessagePerformance` via `useMessageAnalysis`)
- `isLoading` ← `messageLoading` (the same query's pending state)

## Related Components

- `frontend/src/pages/SystemHistory.tsx` — parent page; renders this component in the Message Analysis tab
- `frontend/src/components/history/MessageDistributionChart.tsx` — sibling card rendered directly below it in the same tab
- `frontend/src/components/history/StatsCards.tsx`, `frontend/src/components/history/HistogramTable.tsx`, `frontend/src/components/history/IssueAlerts.tsx`, `frontend/src/components/history/ProviderComparisonTable.tsx`, `frontend/src/components/history/SessionSummaryCards.tsx`, `frontend/src/components/history/SessionCards.tsx`, `frontend/src/components/history/DateRangeSelector.tsx` — other History page components
- `frontend/src/hooks/useHistory.ts` — `useMessagePerformance` hook supplying the data
- `frontend/src/services/domain/HistoryService.ts` — `MessagePerformance` type and `historyService.getMessagePerformance()` service method (data source)
