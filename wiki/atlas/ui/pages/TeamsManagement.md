---
title: Teams Management
type: atlas-page
path: frontend/src/pages/TeamsManagement.tsx
confidence: high
updated: 2026-09-10
tags: [type/page, domain/atlas-ui]
---
# Teams Management

**Component**: `frontend/src/pages/TeamsManagement.tsx`
**Route**: `/teams` (title/breadcrumb: 'Collectives', `requiresAuth: true`, icon: 'users') from `frontend/src/config/routes.ts`
**Last Updated**: 2026-09-10

## Purpose
List all agent teams — labelled **Collectives** in the UI — with full CRUD (create, read, update, delete) and search/sort capabilities. A "team" is a collection whose `entity_type` is `agent`; this page is the collections-management UI specialized for the `agent` entity type. Clicking a team row (or its Open button) navigates to the TeamDetail page at `/teams/:teamId`.

## Key Features
- Loads all agent teams from the backend on mount via `collectionsService.listCollections({ entity_type: 'agent' })`.
- Client-side search filter over team name and description (case-insensitive substring match).
- Sort options: Name (alphabetical), Member Count (`item_count` desc), Newest First (`created_at` desc), Recently Updated (`updated_at` desc).
- TeamsTable listing each team's icon, name, description, member count badge, and localized last-updated date.
- Row actions: Open (navigate to detail), Edit (opens edit modal), Delete (opens confirmation modal).
- Create modal locked to `entity_type='agent'` (title "Create New Collective", submit "Create Collective").
- Edit modal for name/description/color/icon with read-only item count and created date, plus a disabled submit until a change is made.
- Delete confirmation modal warning that the team and all its items will be permanently removed.
- Teams-specific empty state ("No teams yet" + "Create Your First Team" CTA) and a search no-results state.
- Loading spinner while fetching; error alert with a Retry button on failure.
- Page title/meta set via `usePageTitle('Collectives', 'Organize agents into collectives')`.

## Components Used
| Component | Path | Purpose |
|---|---|---|
| `CollectionsHeader` | `frontend/src/components/features/collections/CollectionsHeader.tsx` | Page header: "Collectives" title, "Groups of agents by a common attribute" subtitle, "New Collective" button (view-mode toggle is rendered but wired to a no-op). |
| `TeamsTable` | `frontend/src/components/Teams/TeamsTable.tsx` | Table of teams with icon, name, description, members badge, updated date; Open/Edit/Delete actions (row click = open). |
| `EmptyState` | `frontend/src/components/features/collections/EmptyState.tsx` | Renders "No teams yet" CTA when no teams exist, or a search no-results message when the query matches nothing. |
| `CreateCollectionModal` | `frontend/src/components/features/collections/CreateCollectionModal.tsx` | Form modal for creating a team; `entityType="agent"` prop locks the type selector and switches labels to collective wording. |
| `EditCollectionModal` | `frontend/src/components/features/collections/EditCollectionModal.tsx` | Form modal pre-filled with the team being edited; submits a `CollectionUpdate` payload. |
| `DeleteConfirmationModal` | `frontend/src/components/features/collections/DeleteConfirmationModal.tsx` | Confirm-before-delete dialog showing the team name and item count. |

## Hooks Used
| Hook | Path | Purpose |
|---|---|---|
| `usePageTitle` | `frontend/src/hooks/usePageTitle.tsx` | Sets `document.title` to "Collectives" and injects a Helmet meta description. |
| `useTeamSync` | `frontend/src/hooks/useTeamSync.ts` | Cross-window/-tab sync (roadmap Phase 4) — re-runs `loadCollections()` when a team mutates elsewhere. |
| `useState` / `useEffect` / `useMemo` / `useCallback` | React built-in | Local state (collectives, loading, error, search, sort, modal flags); initial load effect; filtered/sorted list memo; stable `loadCollections` callback. |
| `useNavigate` | `react-router-dom` | Navigates to `/teams/${collectionId}` (TeamDetail) when a team is opened. |

## Data Flow
1. **Load**: On mount, `loadCollections()` (a `useCallback`) calls `collectionsService.listCollections({ entity_type: 'agent' })`. The service builds `GET /api/v1/collections?entity_type=agent&limit=100&offset=0`, returns `CollectionListResponse { collections, total }`, and the page stores `response.collections` in local state. Because `entity_type` is always set, the service's 2-minute in-memory cache is bypassed (cache only applies to unfiltered listings).
2. **Derive**: `useMemo` filters `collections` by `searchQuery` (name/description substring) and sorts by the selected `sortOption`, producing `filteredCollections` passed to `TeamsTable` (or `EmptyState` when empty).
3. **Create**: `handleCreateCollection(name, description, _entityType, color, icon)` builds a `CollectionCreate` (`entity_type: 'agent'`, description optional) → `POST /api/v1/collections` → on success reloads the list (which re-fetches after the service invalidated its cache) and closes the modal.
4. **Update**: `handleSaveEditCollection(id, updates)` → `PUT /api/v1/collections/{id}` with `CollectionUpdate` → reload list → close modal.
5. **Delete**: `handleConfirmDelete(id)` → `DELETE /api/v1/collections/{id}` → reload list → close modal.
6. **Errors**: any thrown error sets `error` state (displayed in an `alert-error` box with a Retry button that calls `loadCollections()` again) and clears the teams list.

## State Management
No global stores (no Zustand/Redux) are read or written. All state is local `useState` inside the page: `collections`, `isLoading`, `error`, `searchQuery`, `sortOption`, `showCreateModal`, `editingCollection`, `deletingCollection`. The only shared state is the module-level 2-minute cache inside the `collectionsService` singleton (`frontend/src/services/domain/CollectionsService.ts`), which is invalidated on create/update/delete and bypassed entirely by this page's filtered request.

## API Endpoints Called
All requests go through `apiClient` via the `collectionsService` singleton (`frontend/src/services/domain/CollectionsService.ts`, base path `/api/v1/collections`). This page reaches teams through the collections API (not the separate `/api/v1/teams` endpoint, which does exist and is used by `teamToolService` on the Agent Profiles page) — a team is a collection with `entity_type='agent'`.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/collections?entity_type=agent&limit=100&offset=0` | List all agent teams on mount and after every mutation. |
| POST | `/api/v1/collections` | Create a new team (`CollectionCreate` with `entity_type: 'agent'`, name, description, color, icon). |
| PUT | `/api/v1/collections/{id}` | Update a team's name/description/color/icon (`CollectionUpdate`). |
| DELETE | `/api/v1/collections/{id}` | Delete a team and its items. |

## Related Pages
- [[TeamDetail]] — destination when a team is opened (`/teams/:teamId`); manages team members and tools.
- [[CollectionsManagement]] — the same collections UI unfiltered by entity type (`/collections`).
- [[CollectionDetail]] — detail view for a generic collection (`/collections/:collectionId`).
- [[ToolCollectionsManagement]] — toolkit variant (`/toolkits`; `/toolboxes` is a redirect) reusing the same `collectionsService`.
