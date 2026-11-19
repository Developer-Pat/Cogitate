---
title: CollectionsSection
type: atlas-component
path: frontend/src/components/features/collections/CollectionsSection.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# CollectionsSection

**Path**: `frontend/src/components/features/collections/CollectionsSection.tsx`
**Last Updated**: 2026-08-01

## Purpose
Section wrapper with title + count badge, laying children out in a responsive grid (grid view) or stacked list (list view).

## Props Interface
```typescript
interface CollectionsSectionProps {
  title: string
  count: number
  viewMode: 'grid' | 'list'
  children: ReactNode
}
```

## Dependencies
None (pure JSX).

## Usage Example
```tsx
<CollectionsSection title="Agents" count={3} viewMode={vm}>{cards}</CollectionsSection>
```

## State Used
None.

## Related Components
- features/collections/CollectionCard.tsx — typical child
- pages/CollectionsManagement.tsx — page using sections