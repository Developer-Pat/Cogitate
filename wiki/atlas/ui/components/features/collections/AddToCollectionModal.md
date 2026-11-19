---
title: AddToCollectionModal
type: atlas-component
path: frontend/src/components/features/collections/AddToCollectionModal.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# AddToCollectionModal

**Path**: `frontend/src/components/features/collections/AddToCollectionModal.tsx`
**Last Updated**: 2026-08-01

## Purpose

Modal dialog for adding an entity (agent, tool, provider, etc.) to one or more collections. It fetches the list of collections for the entity's type from the backend, shows which collections already contain the entity (read-only, with a checkmark) and which are available to add to (checkbox list). The user can select multiple collections and confirm; each selected collection gets the entity appended via `CollectionsService.addItemToCollection`, and success/error feedback is surfaced through the notification store. Includes a lightweight inline "create new collection" form (currently closes the modal — creation itself is handled elsewhere) and an empty state prompting creation of the first collection.

## Props Interface

```typescript
interface AddToCollectionModalProps {
  entityId: string
  entityName: string
  entityType: CollectionEntityType
  onClose: () => void
  onAdded: (collectionIds: string[]) => void
}
```

## Dependencies

| Dependency | Type | Purpose |
| --- | --- | --- |
| `collectionsService` (`CollectionsService` singleton, `frontend/src/services/domain/CollectionsService.ts`) | Service | Backend API client — `listCollections({ entity_type })` loads collections on mount; `addItemToCollection(collectionId, { entity_id, entity_type, entity_name })` appends the entity to each selected collection |
| `Collection`, `CollectionEntityType` (`frontend/src/types/collections.ts`) | Types | Domain types — `CollectionEntityType` (`'agent' \| 'tool' \| 'provider' \| 'macro_set' \| 'template' \| 'workflow'`) drives the fetch filter and membership checks; `Collection` carries the `items` array used to split collections into "already contains entity" vs "available" |
| `useNotificationStore` (`frontend/src/stores/notificationStore`) | Store | Zustand store — `getState().addSuccess(...)` / `addError(...)` show toast feedback after the add action succeeds or fails |

## Usage Example

```tsx
// From ToolCard.tsx (features/agentTools/ToolBrowser)
const [showAddToCollection, setShowAddToCollection] = useState(false)

// ...
{showAddToCollection && (
  <AddToCollectionModal
    entityId={tool.id}
    entityName={tool.name}
    entityType="tool"
    onClose={() => setShowAddToCollection(false)}
    onAdded={handleAddedToCollections}
  />
)}
```

## State Used

Local component state (via `useState`), no external store state:

| State | Type | Purpose |
| --- | --- | --- |
| `collections` | `Collection[]` | Collections fetched for the current `entityType` |
| `isLoading` | `boolean` | True while the collection list is being fetched; renders a full-screen spinner overlay |
| `selectedCollectionIds` | `string[]` | Checkbox selections among `availableCollections`; drives the footer button label/count and the `disabled` state |
| `showCreateForm` | `boolean` | Toggles the inline "create new collection" input form |
| `newCollectionName` | `string` | Text of the new-collection name input |

Derived via `useMemo`:

| Memo | Derivation |
| --- | --- |
| `collectionsWithEntity` | Collections whose `items` contain an entry with `entity_id === entityId && entity_type === entityType` (displayed read-only) |
| `availableCollections` | Collections *not* containing the entity (displayed with checkboxes) |

## Related Components

- `frontend/src/components/features/agentTools/ToolBrowser/ToolCard.tsx` — renders the modal for adding a tool
- `frontend/src/components/features/providers/ProviderCard.tsx` — renders the modal for adding a provider
- `frontend/src/components/Tools/ToolsTableActions.tsx` — tools table row action that opens the modal
- `frontend/src/components/Tools/ToolCollectionsTab.tsx` — tool collections tab usage
- `frontend/src/components/AgentProfiles/ProfileList.tsx` — agent profile card action that opens the modal (notification already shown by the modal)
- `frontend/src/components/AgentProfiles/AgentTableActions.tsx` — agent table row action that opens the modal
- `frontend/src/components/AgentProfiles/CollectionsTab.tsx` — agent collections tab usage
- `frontend/src/services/domain/CollectionsService.ts` — backing API client
- `frontend/src/stores/notificationStore.ts` — success/error feedback
