---
title: SessionCards
type: atlas-component
path: frontend/src/components/history/SessionCards.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# SessionCards

**Path**: `frontend/src/components/history/SessionCards.tsx`
**Last Updated**: 2026-08-01

## Purpose
Grid of session analysis summary cards with loading skeletons.

## Props Interface
```typescript
interface SessionCardsProps {
  sessions?: SessionAnalysisSummary[]
  isLoading?: boolean
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| SessionAnalysisSummary | types | Per-session summary |

## Usage Example
```tsx
<SessionCards sessions={summaries} isLoading={loading} />
```

## State Used
None — presentational.

## Related Components
- history/SessionSummaryCards.tsx — aggregate variant
- pages/SystemHistory.tsx — owner