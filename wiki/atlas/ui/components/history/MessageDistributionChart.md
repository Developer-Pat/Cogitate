---
title: MessageDistributionChart
type: atlas-component
path: frontend/src/components/history/MessageDistributionChart.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# MessageDistributionChart

**Path**: `frontend/src/components/history/MessageDistributionChart.tsx`
**Last Updated**: 2026-08-01

## Purpose
Chart of message-length distribution (bucketed counts) with loading skeleton.

## Props Interface
```typescript
interface MessageDistributionChartProps {
  distribution?: MessageLengthDistribution
  isLoading?: boolean
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| MessageLengthDistribution | types | Distribution buckets |

## Usage Example
```tsx
<MessageDistributionChart distribution={dist} isLoading={loading} />
```

## State Used
None — presentational.

## Related Components
- pages/SystemHistory.tsx — owner
- history/SessionSummaryCards.tsx — sibling