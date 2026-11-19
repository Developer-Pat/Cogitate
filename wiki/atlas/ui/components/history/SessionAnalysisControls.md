---
title: SessionAnalysisControls
type: atlas-component
path: frontend/src/components/history/SessionAnalysisControls.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# SessionAnalysisControls

**Path**: `frontend/src/components/history/SessionAnalysisControls.tsx`
**Last Updated**: 2026-08-01

## Purpose
Session-analysis controls — limit selector (5/10/20/50) and Generate button.

## Props Interface
```typescript
interface SessionAnalysisControlsProps {
  limit: number
  onLimitChange: (limit: number) => void
  onGenerate: () => void
  isLoading?: boolean
  hasData?: boolean
}
```

## Dependencies
None (pure JSX).

## Usage Example
```tsx
<SessionAnalysisControls limit={limit} onLimitChange={setLimit} onGenerate={analyze} isLoading={busy} />
```

## State Used
None — controlled.

## Related Components
- pages/SystemHistory.tsx — owner
- history/SessionCards.tsx — results display