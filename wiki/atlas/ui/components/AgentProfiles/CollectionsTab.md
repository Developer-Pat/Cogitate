---
title: CollectionsTab
type: atlas-component
path: frontend/src/components/AgentProfiles/CollectionsTab.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---

# CollectionsTab

**Path**: `frontend/src/components/AgentProfiles/CollectionsTab.tsx`
**Last Updated**: 2026-08-01

## Purpose

Tab panel rendered inside the agent profile detail view (`ProfileDetail`) that manages which collections an agent belongs to. It loads the list of collections containing the agent on mount (and whenever `profileId` changes), shows a loading spinner while in flight, and renders each collection as a card with its icon, name, description, item count, and the date the agent was added. An "Add to Collection" button (in the header, or as the empty-state CTA) opens `AddToCollectionModal`, which performs the actual add via the collections API; a per-card "Remove" button deletes the membership after a native `confirm()` dialog. All mutations and failures surface as toasts through the notification store.

Unlike the hybrid delegation pattern (read-direct, mutate-via-props), this component performs both its read AND its remove mutation directly through `collectionsService`; only the add mutation is delegated to the child modal.

## Props Interface

```typescript
interface CollectionsTabProps {
  profileId: string
  profileName: string
}
```

- `profileId` — the agent profile's id; used as the entity id in every API call (`findCollectionsContainingEntity('agent', profileId)`, `removeItemFromCollection(collectionId, profileId)`) and passed to the modal as `entityId`.
- `profileName` — the agent's display name; shown in the remove confirmation dialog and passed to the modal as `entityName` (the modal sends it as `entity_name` in the add payload).

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `useState`, `useEffect` (from `react`) | hook | Local state: `collections` (membership list), `loading`, `showAddModal`; `useEffect` triggers `loadCollections()` on mount and whenever `profileId` changes (with `eslint-disable-next-line react-hooks/exhaustive-deps`). |
| `collectionsService` (from `../../services/domain/CollectionsService`) | service singleton (`basePath = '/api/v1/collections'`) | `findCollectionsContainingEntity('agent', profileId)` loads membership; `removeItemFromCollection(collectionId, profileId)` removes it. Unlike `listCollections`, `findCollectionsContainingEntity` is NOT cached — every mount/profileId change hits the backend. |
| `AddToCollectionModal` (from `../features/collections/AddToCollectionModal`) | child component | Modal that lists collections of type `agent`, toggles selections, and performs the add (`POST /api/v1/collections/{id}/items`) via `collectionsService.addItemToCollection`; calls `onAdded` on success. |
| `useNotificationStore` (from `../../stores/notificationStore`) | zustand store hook | `addNotification({ type, title, message })` selector surfaces success ("Added to collection(s)", "Removed from ...") and error ("Failed to load collections", "Failed to remove from collection") toasts. |
| `Collection` (from `../../types/collections`) | type | Shape of each membership card: `id`, `name`, `description`, `icon`, `item_count`, `created_at`, ... |

## Usage Example

```tsx
// frontend/src/components/AgentProfiles/ProfileDetail.tsx (line 943)
import CollectionsTab from './CollectionsTab'
...
<CollectionsTab profileId={profile.id} profileName={profile.name} />
```

## State Used

All state is local `useState`; the only external store read is the notification store:

- `collections: Collection[]` — collections containing this agent, loaded via `findCollectionsContainingEntity`; rendered as cards (icon, name, optional description, `item_count` badge with singular/plural "item"/"items", and "Added {toLocaleDateString(created_at)}").
- `loading: boolean` — true during the initial membership load; renders a centered spinner + "Loading collections..." while set. It is only set around the load, not around remove (removal reloads via `loadCollections` after success).
- `showAddModal: boolean` — toggles `AddToCollectionModal`; set true by the header or empty-state "Add to Collection" buttons, false by `onClose` and after a successful add.

## Add/Remove Behavior

1. **Mount / profile change**: `useEffect` on `[profileId]` calls `loadCollections()` → `GET /api/v1/collections/contains/agent/{profileId}`. Success stores `result.collections`; failure logs to console and shows an error toast. `loading` is set/unset in `finally`.
2. **Add**: header or empty-state "Add to Collection" → `showAddModal = true` → renders `AddToCollectionModal` with `entityId={profileId}`, `entityName={profileName}`, `entityType="agent"`, `onClose`, and `onAdded={handleAddedToCollections}`. The modal calls `collectionsService.addItemToCollection` (`POST /api/v1/collections/{collectionId}/items`) for each selected collection, then invokes `onAdded(selectedCollectionIds)`. `handleAddedToCollections` ignores the passed ids, shows a success toast, closes the modal, and reloads the list.
   - ⚠️ Unwired path inside the modal: its "Create new collection" form (`handleCreateCollection`) only closes the modal — per its source comment "creation handled elsewhere" — it does NOT create a collection.
3. **Remove**: per-card "Remove" → `handleRemoveFromCollection(collection.id, collection.name)` → native `confirm('Remove "{profileName}" from "{collectionName}"?')` → on accept, `DELETE /api/v1/collections/{collectionId}/items/{profileId}` (the second argument is the agent profile id — the entity id — not a membership-row id) → success toast "Removed from ..." then `loadCollections()`. Failure logs and shows an error toast.

## API Endpoints Called

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/collections/contains/agent/{profileId}` | `findCollectionsContainingEntity('agent', profileId)` — load the agent's collection membership list. |
| DELETE | `/api/v1/collections/{collectionId}/items/{profileId}` | `removeItemFromCollection(collectionId, profileId)` — remove the agent from a collection. |
| POST | `/api/v1/collections/{collectionId}/items` | `addItemToCollection` — called by `AddToCollectionModal` (child) with `{entity_id: profileId, entity_type: 'agent', entity_name: profileName}` for each selected collection; not called by this component directly. |

## Related Components

- `frontend/src/components/AgentProfiles/ProfileDetail.tsx` — parent; renders `<CollectionsTab profileId={profile.id} profileName={profile.name} />` on the Collections tab.
- `frontend/src/components/features/collections/AddToCollectionModal.tsx` — child; performs the add mutation and calls back `onAdded`.
- `frontend/src/components/AgentProfiles/index.ts` — barrel that re-exports `CollectionsTab`.
- `frontend/src/components/Tools/ToolCollectionsTab.tsx` — sibling pattern for tool entities (same collection-membership UI for tools).
- `frontend/src/services/domain/CollectionsService.ts` — service backing all reads/mutations (`basePath = '/api/v1/collections'`).
- `frontend/src/types/collections.ts` — `Collection`, `CollectionItem`, `CollectionEntityType` types.
