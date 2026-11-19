---
title: Tool Collections Management
type: atlas-page
path: frontend/src/pages/ToolCollectionsManagement.tsx
confidence: high
updated: 2026-07-31
tags: [type/page, domain/atlas-ui]
---
# Tool Collections Management

**Component**: `frontend/src/pages/ToolCollectionsManagement.tsx`
**Route**: `/toolkits` (legacy `/toolboxes` redirects here)
**Last Updated**: 2026-07-31

## Purpose
Main hub for viewing and managing tool collections ('Toolkits') — create, edit, delete, search, and open collections of tools. Each kit card also shows the agents that OWN it (the agent_kits join, 2026-09-04).

## Key Features
- **Recent Collections** (top 3 by updatedAt) + **All Toolkits** sections
- Grid/list view toggle, search, sort (name/itemCount/createdAt/updatedAt)
- CRUD modals: create, edit, delete-confirmation
- Empty state with create CTA; error state with retry; loading spinner
- Navigates to `/toolkits/{id}` on open

## Components Used
| Component | Path | Purpose |
|-----------|------|---------|
| CollectionsHeader | `components/features/collections/CollectionsHeader.tsx` | Title + create button + view toggle |
| CollectionsFilters | `components/features/collections/CollectionsFilters.tsx` | Search + sort controls |
| CollectionsSection | `components/features/collections/CollectionsSection.tsx` | Section wrapper with title/count |
| CollectionCard | `components/features/collections/CollectionCard.tsx` | Collection card (grid/list) |
| EmptyState | `components/features/collections/EmptyState.tsx` | Empty collections state |
| CreateCollectionModal | `components/features/collections/CreateCollectionModal.tsx` | Create form |
| EditCollectionModal | `components/features/collections/EditCollectionModal.tsx` | Edit form |
| DeleteConfirmationModal | `components/features/collections/DeleteConfirmationModal.tsx` | Delete confirm |

## Hooks Used
| Hook | Path | Purpose |
|------|------|---------|
| usePageTitle | `hooks/usePageTitle.ts` | Sets document title |

## Data Flow
- **Load**: `collectionsService.listCollections({ entity_type: 'tool' })` -> `GET /api/v1/collections` -> local state
- **Create**: `createCollection({name, description, entity_type: 'tool', color, icon})` -> reload
- **Update**: `updateCollection(id, updates)` -> reload
- **Delete**: `deleteCollection(id)` -> reload
- **Filtering**: client-side useMemo (search + sort + recent-exclusion)

## State Management
- Local state only (collections, viewMode, searchQuery, sortOption, modal states, loading, error)

## API Endpoints Called
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v1/collections?entity_type=tool` | List tool collections |
| POST | `/api/v1/collections` | Create collection |
| PUT | `/api/v1/collections/{id}` | Update collection |
| DELETE | `/api/v1/collections/{id}` | Delete collection |

## Related Pages
- ToolCollectionDetail — single toolbox contents
- CollectionsManagement — non-tool collections variant
- ToolManagement — flat tool list