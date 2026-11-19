---
title: StatsCards
type: atlas-component
path: frontend/src/components/history/StatsCards.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# StatsCards

**Path**: `frontend/src/components/history/StatsCards.tsx`
**Last Updated**: 2026-08-01

## Purpose
Log stats cards — total messages, error count, warning count (derived from histogram + explicit counts).

## Props Interface
```typescript
interface StatsCardsProps {
  histogram: LogHistogram[]
  totalLogs?: number
  errorCount?: number
  warningCount?: number
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| LogHistogram | types | Histogram rows |

## Usage Example
```tsx
<StatsCards histogram={hist} totalLogs={total} errorCount={errs} warningCount={warns} />
```

## State Used
None — derived from props.

## Related Components
- pages/SystemHistory.tsx — owner
- history/HistogramTable.tsx — sibling histogram view