---
title: ProviderComparisonTable
type: atlas-component
path: frontend/src/components/history/ProviderComparisonTable.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# ProviderComparisonTable

**Path**: `frontend/src/components/history/ProviderComparisonTable.tsx`
**Last Updated**: 2026-08-01

## Purpose

Renders a comparison table of provider/model performance metrics on the History page (System History). Each row groups message statistics by provider and model, showing usage volume (message count) and performance (average tokens, average duration, tokens/sec). The table auto-highlights the fastest entry (⚡ badge, highest `avgTokensPerSecond`) and the most-used entry (★ badge, highest `messageCount`), with a legend in the footer. It handles three states: a skeleton loading state, an empty state ("No provider/model data available"), and the populated table.

Note: the component compares *usage and performance* (messages, tokens, latency, throughput) — it does not display cost data.

## Props Interface

```typescript
interface ProviderComparisonTableProps {
  stats?: ProviderStats[]
  isLoading?: boolean
}
```

`stats` is the array of `ProviderStats` objects (defined in `frontend/src/services/domain/HistoryService.ts`):

```typescript
export interface ProviderStats {
  provider: string
  model?: string
  messageCount: number
  avgTokenCount: number
  avgDurationMs: number
  avgTokensPerSecond: number
}
```

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `HistoryService.ProviderStats` | Type import (`frontend/src/services/domain/HistoryService.ts`) | Shape of each row's data; produced by `HistoryService.getProviderModelStats(timeRange?)` |
| DaisyUI `table table-zebra` / `card` / `badge` / `skeleton` classes | CSS framework classes | Styling for the table, loading skeleton, empty-state card, and highlight badges |

The component itself uses no hooks, stores, or services directly — data flows in entirely via props.

## Usage Example

```tsx
import ProviderComparisonTable from '../components/history/ProviderComparisonTable'

// Inside SystemHistory.tsx (frontend/src/pages/SystemHistory.tsx):
<ProviderComparisonTable
  stats={messageAnalysis?.providerStats}
  isLoading={messageLoading}
/>
```

## State Used

No internal state. Rendering is driven entirely by props:

- `isLoading` — when truthy, renders a skeleton placeholder (3 skeleton rows) instead of the table.
- `stats` — when undefined or empty, renders the empty-state message. Otherwise each entry becomes a table row; `fastest` and `mostUsed` are derived by reducing over `stats` to find the max `avgTokensPerSecond` and max `messageCount` for highlight styling.

## Related Components

- `frontend/src/pages/SystemHistory.tsx` — parent page; fetches the message analysis and passes `messageAnalysis.providerStats` + loading flag.
- `frontend/src/services/domain/HistoryService.ts` — source of the data: `getProviderModelStats(timeRange?: TimeRange): Promise<ProviderStats[]>` aggregates messages by provider/model.
- `frontend/src/components/history/StatsCards.tsx`, `frontend/src/components/history/HistogramTable.tsx`, `frontend/src/components/history/IssueAlerts.tsx`, `frontend/src/components/history/MessagePerformanceCards.tsx`, `frontend/src/components/history/MessageDistributionChart.tsx`, `frontend/src/components/history/SessionSummaryCards.tsx`, `frontend/src/components/history/SessionCards.tsx`, `frontend/src/components/history/SessionAnalysisControls.tsx` — sibling History-page components rendered alongside this one in `SystemHistory.tsx`.
