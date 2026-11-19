---
title: LoadingSkeleton
type: atlas-component
path: frontend/src/components/LoadingSkeleton.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# LoadingSkeleton

**Path**: `frontend/src/components/LoadingSkeleton.tsx`
**Last Updated**: 2026-08-01

## Purpose
Collection of animate-pulse skeleton loading placeholders — full page skeleton, table rows, cards, and stat grids. Used while async data loads.

## Props Interface
```typescript
// LoadingSkeleton()          — no props; full page skeleton
// TableSkeleton({ rows })   — rows?: number (default 5)
// CardSkeleton()            — no props
// StatsSkeleton({ count })  — count?: number (default 4)
```

## Dependencies
None (pure JSX with Tailwind/DaisyUI classes).

## Usage Example
```tsx
{loading && <LoadingSkeleton />}
{loading && <TableSkeleton rows={8} />}
```

## State Used
None — stateless presentational components.

## Related Components
- Loading/PageLoader.tsx, Loading/SkeletonLoader.tsx — alternative loading components in the Loading/ directory