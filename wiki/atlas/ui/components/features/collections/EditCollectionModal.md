---
title: EditCollectionModal
type: atlas-component
path: frontend/src/components/features/collections/EditCollectionModal.tsx
confidence: high
updated: 2026-09-10
tags: [type/component, domain/atlas-ui]
---
# EditCollectionModal

**Path**: `frontend/src/components/features/collections/EditCollectionModal.tsx`
**Last Updated**: 2026-09-10

## Purpose
Modal dialog for editing an existing collection. Pre-fills a form from the passed `collection` (name, description, entity type, color, icon), lets the user update the editable fields, and reports changes back to the parent via `onSave` so the parent can persist them through the collections API. The modal itself performs no direct API calls — the parent owns the `collectionsService.updateCollection` call. It also shows read-only stats (item count and creation date) and disables the Save button until the form actually differs from the original collection.

## Props Interface
```typescript
interface EditCollectionModalProps {
  collection: Collection
  onClose: () => void
  onSave: (id: string, updates: CollectionUpdate) => void
}
```

- `collection` — the `Collection` being edited; its fields seed the form state and the read-only stats section.
- `onClose` — invoked when the user clicks the header X button or Cancel (also invoked after a successful submit).
- `onSave(id, updates)` — invoked on submit with the collection id and a `CollectionUpdate` payload built from the form.

## Dependencies
| Dependency | Type | Purpose |
|---|---|---|
| `react` (`useState`, `useEffect`) | Hook | Local form state; resets the form when the `collection` prop changes |
| `@/types/collections` (`Collection`, `CollectionEntityType`, `CollectionUpdate`) | Type | Prop typing, entity-type option typing, and the update payload type |
| `collectionsService.updateCollection(id, data)` — `frontend/src/services/domain/CollectionsService.ts` | Service | `PUT /collections/{id}`; persists the edit. Called by the parent inside `onSave`, not by this modal |
| DaisyUI / Tailwind utility classes | Styling | Modal overlay, buttons, inputs, color swatches, stats panels |

## Usage Example
```tsx
{editingCollection && (
  <EditCollectionModal
    collection={editingCollection}
    onClose={() => setEditingCollection(null)}
    onSave={handleSaveEditCollection}
  />
)}
```
(From `frontend/src/pages/CollectionsManagement.tsx`; `handleSaveEditCollection` calls `collectionsService.updateCollection(id, updates)`, reloads the list, and closes the modal.)

## State Used
- `entityType` (`CollectionEntityType`) — selected entity type, seeded from `collection.entity_type`. Shown as a picker, but **not** included in the `CollectionUpdate` payload passed to `onSave`.
- `name` (`string`) — collection name; required (submit is guarded by `name.trim()`).
- `description` (`string`) — optional description text.
- `color` (`string`) — selected swatch from `COLOR_OPTIONS`.
- `selectedIcon` (`string`) — selected emoji from `ICON_OPTIONS`.
- `useEffect([collection])` — resets all five fields whenever the `collection` prop identity changes, keeping the form in sync with the collection being edited.
- Module constants (not state): `ENTITY_TYPE_OPTIONS` (agent, tool, provider, macro_set, template — note the domain type `CollectionEntityType` also allows `workflow`), `COLOR_OPTIONS` (7 swatches), `ICON_OPTIONS` (13 emoji — `📁 ⭐ 🔥 💎 🎯 🚀 💡 📚 🎨 ⚡ 🛠️ 🤖 👁️`).
- Submit is disabled unless `name` is non-empty and at least one field differs from `collection`; button label is "Save Changes".

## Related Components
- `frontend/src/pages/CollectionsManagement.tsx` — primary parent; renders the modal when `editingCollection` is set and wires `onSave` to `collectionsService.updateCollection`.
- `frontend/src/components/features/collections/CreateCollectionModal.tsx` — sibling modal for creating a new collection.
- `frontend/src/components/features/collections/DeleteConfirmationModal.tsx` — sibling modal for delete confirmation.
- `frontend/src/components/features/collections/CollectionCard.tsx` — triggers editing via its `onEdit` callback.
- Also consumed by: `frontend/src/pages/TeamsManagement.tsx`, `frontend/src/pages/ToolCollectionDetail.tsx`, `frontend/src/pages/TeamDetail.tsx`, `frontend/src/pages/CollectionDetail.tsx`, `frontend/src/pages/ToolCollectionsManagement.tsx`.
- Types: `frontend/src/types/collections.ts`; service: `frontend/src/services/domain/CollectionsService.ts`.
