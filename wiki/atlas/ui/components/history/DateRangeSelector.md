---
title: DateRangeSelector
type: atlas-component
path: frontend/src/components/history/DateRangeSelector.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# DateRangeSelector

**Path**: `frontend/src/components/history/DateRangeSelector.tsx`
**Last Updated**: 2026-08-01

## Purpose
Time-range selector — quick-range buttons (Last 1h/6h/12h/24h/7d/30d) plus custom from/to date inputs.

## Props Interface
```typescript
interface TimeRange { from: Date; to: Date }

interface DateRangeSelectorProps {
  value: TimeRange
  onChange: (range: TimeRange) => void
}
```

## Dependencies
None (pure JSX).

## Usage Example
```tsx
<DateRangeSelector value={range} onChange={setRange} />
```

## State Used
None — controlled.

## Related Components
- pages/SystemHistory.tsx — owner page
- history/SessionAnalysisControls.tsx — sibling controls