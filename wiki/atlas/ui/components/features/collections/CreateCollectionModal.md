---
title: CreateCollectionModal
type: atlas-component
path: frontend/src/components/features/collections/CreateCollectionModal.tsx
confidence: high
updated: 2026-09-10
tags: [type/component, domain/atlas-ui]
---
# CreateCollectionModal

**Path**: `frontend/src/components/features/collections/CreateCollectionModal.tsx`
**Last Updated**: 2026-09-10

## Purpose

Modal dialog for creating a new collection. It is a fully controlled form component: it collects the collection's **name**, **description**, **entity type** (tools / providers / macro sets / templates), **color**, and **icon**, then reports the result upward through the `onCreate` callback. The modal makes **no API calls itself** — the parent page owns the create request and calls `collectionsService.createCollection(collectionData)` with a `CollectionCreate` payload.

When the optional `entityType` prop is provided, the modal is "locked" to that type: the type selector is hidden and the copy adapts (e.g. `TeamsManagement.tsx` passes `entityType="agent"`, which turns the title into **"Create New Collective"**, the subtitle into **"Group agents together by a common attribute"**, and the submit label into **"Create Collective"**).

## Props Interface

```typescript
interface CreateCollectionModalProps {
  onClose: () => void
  onCreate: (
    name: string,
    description: string,
    entityType: CollectionEntityType,
    color: string,
    icon: string
  ) => void
  /** When provided, locks the modal to this entity type and hides the type selector */
  entityType?: CollectionEntityType
}
```

`CollectionEntityType` is defined in `frontend/src/types/collections.ts`:

```typescript
export type CollectionEntityType = 'agent' | 'tool' | 'provider' | 'macro_set' | 'template' | 'workflow';
```

Note: the type selector only offers `tool`, `provider`, `macro_set`, and `template` (`ENTITY_TYPE_OPTIONS`). `agent` is used exclusively via the locked `entityType="agent"` path (the Collectives page); `workflow` is a valid type but is not offered by this modal.

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `react` (`useState`) | Hook | Local form state: `entityType`, `name`, `description`, `color`, `selectedIcon` |
| `@/types/collections` (`CollectionEntityType`) | Type import | Typing for the entity type state, props, and `onCreate` signature |
| `collectionsService.createCollection` (invoked by parent via `onCreate`) | Service (indirect) | Persists the collection as `CollectionCreate` `{ name, description?, entity_type, color, icon }`; the modal itself performs no API calls |
| DaisyUI classes (`btn`, `btn-primary`, `input input-bordered`, `bg-base-200`) | CSS framework | Modal shell, form controls, and color swatches |

## Usage Example

Used by `CollectionsManagement.tsx` (generic collections — type selector shown, defaults to `tool`):

```tsx
{showCreateModal && (
  <CreateCollectionModal
    onClose={() => setShowCreateModal(false)}
    onCreate={handleCreateCollection}
  />
)}
```

Parent handler (`CollectionsManagement.tsx`):

```tsx
const handleCreateCollection = async (
  name: string,
  description: string,
  entityType: CollectionEntityType,
  color: string,
  icon: string
) => {
  try {
    const collectionData: CollectionCreate = {
      name,
      description: description || undefined,
      entity_type: entityType,
      color,
      icon,
    }
    await collectionsService.createCollection(collectionData)
    await loadCollections()
    setShowCreateModal(false)
  } catch (err) {
    setError(err instanceof Error ? err.message : 'Failed to create collection')
  }
}
```

Locked variant used by `TeamsManagement.tsx` (teams are collections with `entity_type: 'agent'`):

```tsx
<CreateCollectionModal
  onClose={() => setShowCreateModal(false)}
  onCreate={handleCreateCollection}
  entityType="agent"
/>
```

## State Used

All state is local (`useState`); the modal is uncontrolled by its parent except for the optional locked `entityType` prop:

| State | Initial value | Purpose |
|---|---|---|
| `entityType` | `lockedEntityType \|\| 'tool'` | Selected collection type; hidden from UI when `isLocked` |
| `name` | `''` | Collection name (required; submit is disabled when blank) |
| `description` | `''` | Optional description |
| `color` | `'primary'` | Color theme, one of `primary` / `secondary` / `accent` / `info` / `success` / `warning` / `error` |
| `selectedIcon` | `'📁'` | Emoji icon, one of **13** options (`📁 ⭐ 🔥 💎 🎯 🚀 💡 📚 🎨 ⚡ 🛠️ 🤖 👁️`) |

Derived values: `isLocked` (`lockedEntityType !== undefined`), `isTeams` (`lockedEntityType === 'agent'`), plus `modalTitle` / `modalSubtitle` / `submitLabel` which switch between "collection" and "team" copy.

On submit, `handleSubmit` guards on a non-blank trimmed `name` and calls `onCreate(name.trim(), description.trim(), entityType, color, selectedIcon)`.

## Related Components

- `frontend/src/components/features/collections/EditCollectionModal.tsx` — sibling edit form; used together with this modal on the same pages
- `frontend/src/components/features/collections/DeleteConfirmationModal.tsx` — sibling delete confirmation, rendered alongside on the same pages
- `frontend/src/components/features/collections/CollectionCard.tsx` — displays the collections this modal creates
- `frontend/src/components/features/collections/CollectionsSection.tsx` — sections the created collections by type
- `frontend/src/components/features/collections/CollectionsHeader.tsx` — hosts the "create" trigger button on the collections pages
- Consumers: `frontend/src/pages/CollectionsManagement.tsx`, `frontend/src/pages/TeamsManagement.tsx` (locked to `agent`), `frontend/src/pages/ToolCollectionsManagement.tsx`
- Data layer: `frontend/src/types/collections.ts` (`CollectionEntityType`, `CollectionCreate`) and the collections service backing `collectionsService.createCollection`

## Naming alias

The **user-facing name is Collective** (a group of agents by a
common attribute). The **implementation name stays `collections`**
(the `collections` table, `entity_type='agent'`) and the wire
protocol stays — a language flip, not a schema change (ARM Phase C,
study 15: collectives are user-facing organization only).
