---
title: AddToolsToToolboxModal
type: atlas-component
path: frontend/src/components/features/collections/AddToolsToToolboxModal.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# AddToolsToToolboxModal

**Path**: `frontend/src/components/features/collections/AddToolsToToolboxModal.tsx`
**Last Updated**: 2026-08-01

## Purpose

Modal for selecting and adding tools to a toolbox (a `Collection` of tools). On mount it fetches all active tools via `ToolService.listTools({ is_active: true })`, filters out tools already present in the toolbox (`toolbox.items` with `entity_type === 'tool'`), and lets the user search, select (individually or select-all), and add the chosen tools. Each selected tool is persisted with `collectionsService.addItemToCollection(toolbox.id, itemData)`, then `onToolsAdded` fires and the modal closes. Load and add failures surface as error toasts via the notification store.

## Props Interface

```typescript
interface AddToolsToToolboxModalProps {
  toolbox: Collection
  onClose: () => void
  onToolsAdded: () => void
}
```

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `useState`, `useEffect` | React hook | Local state (available/selected tools, search query, loading flags); loads available tools on mount and whenever `toolbox.items` changes |
| `Collection`, `CollectionItemCreate` | Type (`src/types/collections.ts`) | Typing for the `toolbox` prop and the add-item payload shape |
| `Tool`, `ToolListResponse` | Type (`src/types/tools.ts`) | Typing for the available-tool list and the `listTools` response |
| `ToolService` | Service class (`src/services/domain/ToolService.ts`) | Instantiated per load; `listTools({ is_active: true })` fetches active tools |
| `collectionsService` | Service singleton (`src/services/domain/CollectionsService.ts`) | `addItemToCollection(toolbox.id, itemData)` persists each selected tool into the toolbox |
| `useNotificationStore` | Zustand store (`src/stores/notificationStore.ts`) | `addError` / `addSuccess` toasts for load failures, add failures, and success confirmation |

## Usage Example

```tsx
import { AddToolsToToolboxModal } from '@/components/features/collections/AddToolsToToolboxModal'

{showAddModal && (
  <AddToolsToToolboxModal
    toolbox={collection}
    onClose={() => setShowAddModal(false)}
    onToolsAdded={handleToolsAdded}
  />
)}
```

## State Used

- `availableTools: Tool[]` — active tools not already in the toolbox; populated in the `useEffect` and filtered client-side by `searchQuery`
- `selectedTools: Set<string>` — ids of tools ticked for addition; drives the add button's disabled state and the "N selected" counter
- `searchQuery: string` — free-text filter matched case-insensitively against `tool.name` and `tool.description`
- `isLoading: boolean` — shows a spinner while tools are being fetched
- `isAdding: boolean` — disables the add button and shows "Adding..." while items are being persisted

## Related Components

- `frontend/src/pages/ToolCollectionDetail.tsx` — parent page that renders the modal (owns `showAddModal` state and the `handleToolsAdded` callback)
- `frontend/src/components/features/collections/EditCollectionModal.tsx` — sibling modal in the same directory
- `frontend/src/components/features/collections/DeleteConfirmationModal.tsx` — sibling modal in the same directory
