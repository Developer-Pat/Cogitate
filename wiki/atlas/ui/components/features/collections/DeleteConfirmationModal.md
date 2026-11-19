---
title: DeleteConfirmationModal
type: atlas-component
path: frontend/src/components/features/collections/DeleteConfirmationModal.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# DeleteConfirmationModal

**Path**: `frontend/src/components/features/collections/DeleteConfirmationModal.tsx`
**Last Updated**: 2026-08-01

## Purpose
Modal dialog confirming collection deletion — shows collection name/type, Cancel + Confirm (danger) buttons.

## Props Interface
```typescript
interface DeleteConfirmationModalProps {
  collection: Collection
  onClose: () => void
  onConfirm: (id: string) => void
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| Collection | types/collections | Data shape |

## Usage Example
```tsx
<DeleteConfirmationModal collection={c} onClose={() => setDel(null)} onConfirm={(id) => del(id)} />
```

## State Used
None — controlled.

## Related Components
- features/collections/CollectionCard.tsx — delete action opens this
- pages/CollectionsManagement.tsx — owner