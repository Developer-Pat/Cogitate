---
title: Collections Management
type: atlas-page
path: frontend/src/pages/CollectionsManagement.tsx
confidence: high
updated: 2026-09-10
tags: [type/page, domain/atlas-ui]
---
# Collections Management

**Component**: `frontend/src/pages/CollectionsManagement.tsx`
**Route**: `/collections` (protected, lazy-loaded)
**Last Updated**: 2026-09-10

## Purpose

Hub page for viewing, creating, editing, and deleting entity collections (tools, providers, macro sets, templates). Users pick an entity-type filter to reveal collections, then search, sort, and manage them via cards and modals. Backed by the backend via `CollectionsService` (GET/POST/PUT/DELETE against `/api/v1/collections`); the sibling page [[ToolCollectionsManagement]] is the tool-only variant served at `/toolkits` (the Toolkit surface; each kit card shows the agents that own it).

## Key Features

- **Full CRUD**: create (CreateCollectionModal), edit (EditCollectionModal), delete with confirmation (DeleteConfirmationModal) - all wired to `collectionsService` and followed by a list reload.
- **Entity-type filtering**: filter dropdown (`none` / `all` / `tool` / `provider` / `macro_set` / `template`) gates which sections render; a type must be selected before any collections display, otherwise a "No filter selected" badge is shown.
- **Client-side search**: case-insensitive match on collection name and description.
- **Client-side sorting**: by name, item count, created date, or updated date.
- **Recent Collections rail**: top 3 collections by `updated_at`, shown only when the filter is `all` and no search query is active.
- **Grid/list view toggle** (CollectionsHeader) controlling card layout via CollectionsSection.
- **Active-filter badges**: type and search badges with one-click clearing, plus a "No results" indicator when the filtered list is empty.
- **Empty states** (EmptyState) with contextual CTA to create the first collection.
- **Loading spinner and error alert with Retry** (re-invokes `loadCollections`).
- **Navigation to detail**: opening a collection navigates to `/collections/{id}` ([[CollectionDetail]]).

## Components Used

| Component | Path | Purpose |
|---|---|---|
| CollectionsHeader | `frontend/src/components/features/collections/CollectionsHeader.tsx` | Page title/subtitle, grid vs list view toggle, "New Collection" button |
| CollectionsFilters | `frontend/src/components/features/collections/CollectionsFilters.tsx` | Entity-type filter dropdown, search input with clear button, sort dropdown |
| CollectionsSection | `frontend/src/components/features/collections/CollectionsSection.tsx` | Section wrapper with title, count badge, and grid/list layout classes |
| CollectionCard | `frontend/src/components/features/collections/CollectionCard.tsx` | Renders one collection (grid card or list row) with Open, Edit, Delete actions |
| EmptyState | `frontend/src/components/features/collections/EmptyState.tsx` | Shown when no collections match the current filters; search-specific and "create first collection" variants |
| CreateCollectionModal | `frontend/src/components/features/collections/CreateCollectionModal.tsx` | Form modal for a new collection (name, description, entity type, color, icon) |
| EditCollectionModal | `frontend/src/components/features/collections/EditCollectionModal.tsx` | Pre-filled edit modal with read-only item count and created-date stats |
| DeleteConfirmationModal | `frontend/src/components/features/collections/DeleteConfirmationModal.tsx` | Confirmation dialog before destructive delete |

## Hooks Used

| Hook | Path | Purpose |
|---|---|---|
| usePageTitle | `frontend/src/hooks/usePageTitle.tsx` | Sets document title ("Collections") via `formatPageTitle` and renders a Helmet meta description; restores previous title on unmount |
| useNavigate | `react-router-dom` | Programmatic navigation to `/collections/{id}` when a collection is opened |
| useCollectionSync | `frontend/src/hooks/useCollectionSync.ts` | Cross-window/-tab sync (roadmap Phase 3) — reloads the list when a collection mutates elsewhere |
| useDomainSync | `frontend/src/hooks/useDomainSync.ts` | Reloads on the `agent-list` and `workflow-list` domain events (roadmap Phase 6 — both are collections-backed) |
| useState / useEffect / useMemo / useCallback | `react` | Local state for collections, loading, error, view mode, filters, sort, and modal visibility; `useMemo` derives recent + filtered/sorted lists |

## Data Flow

1. **Load (mount)**: `loadCollections` (useCallback) calls `collectionsService.listCollections()` which hits `GET /api/v1/collections`. Success stores `response.collections` in local state; failure sets an error message and clears the list; `isLoading` gates the spinner.
2. **Derived views** (pure client-side, `useMemo`): `recentCollections` = top 3 by `updated_at`; `filteredCollections` = entity-type filter, then search filter, then sort. No server round-trips for filtering, sorting, or searching.
3. **Create**: `handleCreateCollection` builds a `CollectionCreate` payload → `collectionsService.createCollection()` → `POST /api/v1/collections` → `loadCollections()` refresh → close modal.
4. **Edit**: `handleSaveEditCollection` → `collectionsService.updateCollection(id, updates)` → `PUT /api/v1/collections/{id}` → refresh → close modal.
5. **Delete**: `handleConfirmDelete` → `collectionsService.deleteCollection(id)` → `DELETE /api/v1/collections/{id}` → refresh → close modal.
6. **Open**: `handleOpenCollection` navigates to `/collections/{collectionId}`.
7. Every mutation failure surfaces as an inline error alert (with Retry) instead of a modal error.

## State Management

- **No Zustand/Redux stores** - the page is fully local-state driven (`useState`), with derived data memoized via `useMemo`.
- **Service-level cache**: `CollectionsService` (singleton, `frontend/src/services/domain/CollectionsService.ts`) keeps an in-memory list cache with a 2-minute TTL for unfiltered basic listings; `createCollection`, `updateCollection`, and `deleteCollection` invalidate the cache (`invalidateCache`), so the next `listCollections` call hits the backend again.
- `apiClient` (`frontend/src/services/apiClient.ts`) wraps all HTTP calls; `frontendLoggingService` logs service activity at debug/info/error levels.

## API Endpoints Called

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/collections` | List collections (query params: `entity_type`, `search`, `is_active`, `limit`, `offset`); basic listings cached for 2 minutes |
| POST | `/api/v1/collections` | Create a new collection (body: name, description, entity_type, color, icon) |
| PUT | `/api/v1/collections/{id}` | Update an existing collection (body: name, description, color, icon) |
| DELETE | `/api/v1/collections/{id}` | Delete a collection |

Note: `CollectionsService` also exposes `getCollection`, `getCollectionItems`, `addItemToCollection`, `removeItemFromCollection`, `findCollectionsContainingEntity`, and `isEntityInAnyCollection` (items and `contains` sub-endpoints), but those are exercised by other pages (e.g. [[CollectionDetail]]) rather than this one.

## Related Pages

- [[CollectionDetail]] - `/collections/:collectionId`; destination when a collection is opened from this page.
- [[ToolCollectionsManagement]] - the tool-only (toolkit) variant at `/toolkits`, sharing the same `components/features/collections/*` components.
- [[TeamsManagement]] - reuses the shared collection modals (e.g. CreateCollectionModal locked to the `agent` entity type).
- [[ToolManagement]] - `/tools`; tools are the primary entity type collected here.
