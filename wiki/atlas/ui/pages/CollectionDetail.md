---
title: Collection Detail
type: atlas-page
path: frontend/src/pages/CollectionDetail.tsx
confidence: high
updated: 2026-07-31
tags: [type/page, domain/atlas-ui]
---

# Collection Detail

**Component**: `frontend/src/pages/CollectionDetail.tsx`
**Route**: `/collections/:collectionId` (registered in `frontend/src/config/routes.ts`, `requiresAuth: true`, lazy-loaded via `React.lazy`; `collectionId` is a URL path param)
**Last Updated**: 2026-07-31

## Purpose

Displays a single collection (the non-tool variant of [[ToolCollectionDetail]]) and lets the user manage its metadata and contents. It renders the collection header (icon, name, description, item count, created/updated dates), a responsive card grid of the collection's items, and provides edit/delete/remove-item actions backed by the `CollectionsService` REST client. Item cards carry an entity-type badge (tool, agent, provider, macro_set, template) and a per-item remove button. "Add Items" is currently a placeholder (no-op) — the service method for adding items exists but is not wired to this page yet.

## Key Features

- **Collection header**: icon, name, description, item-count badge, and created/updated timestamps (formatted via `toLocaleDateString()`).
- **Items grid**: responsive card grid (`1/2/3/4` columns) of `CollectionItemCard`s showing `entity_name`, a color-coded `entity_type` badge, and the date the item was added.
- **Remove item**: per-card remove button calls the items DELETE endpoint, then refetches the collection.
- **Edit collection**: opens `EditCollectionModal` (name, description, color, icon, entity type); saving calls PUT and refetches.
- **Delete collection**: opens `DeleteConfirmationModal`; confirming calls DELETE and navigates back to `/collections`.
- **Empty state**: friendly "No items yet" call-to-action when the collection has zero items.
- **Loading & error states**: full-screen spinner while loading; "Collection Not Found" panel with a back button on error/missing collection.
- **Back navigation**: header button navigates to `/collections`.

## Components Used

| Component | Path | Purpose |
|---|---|---|
| `EditCollectionModal` | `frontend/src/components/features/collections/EditCollectionModal.tsx` | Modal form for editing collection metadata (name, description, color, icon pickers, entity type, read-only stats). |
| `DeleteConfirmationModal` | `frontend/src/components/features/collections/DeleteConfirmationModal.tsx` | Confirmation dialog warning before permanent collection deletion (shows item count). |
| `CollectionItemCard` | Defined inline in `CollectionDetail.tsx` (lines 236–291) | Card for a single collection item: entity name, type badge, added date, remove button. |

## Hooks Used

| Hook | Path | Purpose |
|---|---|---|
| `useState` | `react` | Local state: `collection`, `isLoading`, `error`, `editingCollection`, `deletingCollection`. |
| `useEffect` | `react` | Triggers the initial `loadCollection()` on mount / whenever the memoized loader changes. |
| `useCallback` | `react` | Memoizes `loadCollection` so it is stable per `collectionId`. |
| `useParams` | `react-router-dom` | Extracts `collectionId` from the `/collections/:collectionId` route. |
| `useNavigate` | `react-router-dom` | Navigates back to `/collections` after back/delete actions. |

No custom project hooks are used; there are no collection-specific hooks under `frontend/src/hooks/`.

## Data Flow

1. **Load**: On mount, `useParams` supplies `collectionId`; `loadCollection()` calls `collectionsService.getCollection(collectionId)` → `GET /api/v1/collections/{id}`. The resolved `Collection` object (including its `items` array and `item_count`) is stored in local state and drives the whole render.
2. **Render**: Header fields (`icon`, `name`, `description`) and metadata (`item_count`, `created_at`, `updated_at`) render directly from the `Collection`; each `CollectionItem` renders as a `CollectionItemCard` with a color-coded badge derived from `entity_type`.
3. **Remove item**: `handleRemoveItem(itemId)` → `collectionsService.removeItemFromCollection(collection.id, itemId)` → `DELETE /api/v1/collections/{id}/items/{itemId}`, then `loadCollection()` refetches to refresh the grid.
4. **Edit**: `EditCollectionModal` collects `CollectionUpdate` (name, description, color, icon); `handleSaveEdit` → `collectionsService.updateCollection(collection.id, updates)` → `PUT /api/v1/collections/{id}`, then refetches and closes the modal.
5. **Delete**: `DeleteConfirmationModal` confirms → `collectionsService.deleteCollection(id)` → `DELETE /api/v1/collections/{id}`, then `navigate('/collections')`.
6. **Add items**: `handleAddItems` is a stub — it only logs to the console. The service's `addItemToCollection` (`POST /api/v1/collections/{id}/items`) is not yet called from this page.

## State Management

- **No global stores** (no Zustand/Redux/Context) are read or written by this page — all state is local `useState` in the component and its modals.
- **Service-level cache**: `CollectionsService` maintains an in-memory list cache (2-minute TTL) for unfiltered `listCollections()` calls only; `getCollection` is never cached. Mutations (`updateCollection`, `deleteCollection`, `removeItemFromCollection`) invalidate the list cache so the management list stays fresh.

## API Endpoints Called

All requests go through `frontend/src/services/domain/CollectionsService.ts` (singleton `collectionsService`) using the shared `apiClient` (`frontend/src/services/apiClient.ts`); base path is `/api/v1/collections`.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/collections/{collectionId}` | Fetch the collection and its items (`getCollection`). |
| PUT | `/api/v1/collections/{collectionId}` | Update collection metadata from the edit modal (`updateCollection`). |
| DELETE | `/api/v1/collections/{collectionId}` | Delete the collection, then navigate away (`deleteCollection`). |
| DELETE | `/api/v1/collections/{collectionId}/items/{itemId}` | Remove a single item from the collection (`removeItemFromCollection`). |

> Note: `POST /api/v1/collections/{id}/items` (`addItemToCollection`) exists on the service and is the intended add-item endpoint, but is not invoked by this page yet.

## Related Pages

- [[CollectionsManagement]] — the list page at `/collections`; the source of navigation into this page and the destination of back/delete actions.
- [[ToolCollectionDetail]] — the tool-only (toolkit) variant of this page, served at `/toolkits/:collectionId` (the legacy `/toolboxes/:collectionId` paths redirect).
