---
title: PageLoader
type: atlas-component
path: frontend/src/components/Loading/PageLoader.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# PageLoader

**Path**: `frontend/src/components/Loading/PageLoader.tsx`
**Last Updated**: 2026-08-01

## Purpose
Simple page-level loading indicator — three pulsing dots plus 'Loading page...' text. Used for route-level loading states.

## Props Interface
None — no props.

## Dependencies
None (pure JSX, default export).

## Usage Example
```tsx
import PageLoader from './Loading/PageLoader'

<PageLoader />
```

## State Used
None — stateless.

## Related Components
- Loading/SkeletonLoader.tsx — skeleton variant
- LoadingSkeleton.tsx (top-level) — larger page skeleton