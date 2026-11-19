---
title: CollectionCard
type: atlas-component
path: frontend/src/components/features/collections/CollectionCard.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# CollectionCard

**Path**: `frontend/src/components/features/collections/CollectionCard.tsx`
**Last Updated**: 2026-08-01

## Purpose
Displays a single collection in grid or list view with entity-type label (Agents/Tools/Providers/Macro Sets/Templates), item count, and Open/Edit/Delete actions.

## Props Interface
```typescript
interface CollectionCardProps {
  collection: Collection   // from types/collections
  viewMode: 'grid' | 'list'
  onOpen: () => void
  onEdit: () => void
  onDelete: () => void
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| Collection | types/collections | Data shape |

## Usage Example
```tsx
<CollectionCard collection={c} viewMode={viewMode} onOpen={() => nav(c.id)} onEdit={...} onDelete={...} />
```

## State Used
None — stateless.

## Related Components
- features/collections/CollectionsSection.tsx — grid wrapper
- features/collections/CreateCollectionModal.tsx / EditCollectionModal.tsx — edit/create actions