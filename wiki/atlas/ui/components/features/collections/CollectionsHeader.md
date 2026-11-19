---
title: CollectionsHeader
type: atlas-component
path: frontend/src/components/features/collections/CollectionsHeader.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# CollectionsHeader

**Path**: `frontend/src/components/features/collections/CollectionsHeader.tsx`
**Last Updated**: 2026-08-01

## Purpose
Collections page header — title + subtitle, 'New Collection' create button, and grid/list view toggle.

## Props Interface
```typescript
interface CollectionsHeaderProps {
  onCreate: () => void
  viewMode: 'grid' | 'list'
  onViewModeChange: (mode: 'grid' | 'list') => void
  title?: string          // default 'Collections'
  subtitle?: string       // default 'Manage all your collections in one place'
  createButtonText?: string  // default 'New Collection'
}
```

## Dependencies
None (pure JSX).

## Usage Example
```tsx
<CollectionsHeader onCreate={openCreate} viewMode={vm} onViewModeChange={setVm} />
```

## State Used
None — stateless.

## Related Components
- features/collections/CreateCollectionModal.tsx — opened by onCreate
- features/collections/CollectionsSection.tsx — content below header