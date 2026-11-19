---
title: SessionSummaryCards
type: atlas-component
path: frontend/src/components/history/SessionSummaryCards.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# SessionSummaryCards

**Path**: `frontend/src/components/history/SessionSummaryCards.tsx`
**Last Updated**: 2026-08-01

## Purpose
4-up summary stat cards for a session-analysis result (totals per category) with loading skeletons.

## Props Interface
```typescript
interface SessionSummaryCardsProps {
  result?: SessionAnalysisResult
  isLoading?: boolean
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| SessionAnalysisResult | types | Aggregate analysis |

## Usage Example
```tsx
<SessionSummaryCards result={result} isLoading={loading} />
```

## State Used
None — presentational.

## Related Components
- history/SessionCards.tsx — per-session variant
- pages/SystemHistory.tsx — owner