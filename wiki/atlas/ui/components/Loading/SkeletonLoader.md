---
title: SkeletonLoader
type: atlas-component
path: frontend/src/components/Loading/SkeletonLoader.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# SkeletonLoader

**Path**: `frontend/src/components/Loading/SkeletonLoader.tsx`
**Last Updated**: 2026-08-01

## Purpose
Configurable skeleton loading placeholder — renders `count` copies of a card/table/text/stat skeleton with animate-pulse.

## Props Interface
```typescript
interface SkeletonLoaderProps {
  type?: 'card' | 'table' | 'text' | 'stat'  // default 'card'
  count?: number                            // default 1
  className?: string                       // default ''
}
```

## Dependencies
None (pure JSX).

## Usage Example
```tsx
<SkeletonLoader type="table" count={4} />
```

## State Used
None — stateless.

## Related Components
- Loading/PageLoader.tsx — dot-pulse loader
- LoadingSkeleton.tsx (top-level) — fixed-page skeleton exports