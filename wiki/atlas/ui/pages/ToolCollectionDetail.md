---
title: Tool Collection Detail
type: atlas-page
path: frontend/src/pages/ToolCollectionDetail.tsx
confidence: high
updated: 2026-07-31
tags: [type/page, domain/atlas-ui]
---
# Tool Collection Detail

**Component**: `frontend/src/pages/ToolCollectionDetail.tsx`
**Route**: `/toolkits/:collectionId` (legacy `/toolboxes/:collectionId` redirects here)
**Last Updated**: 2026-07-31

## Purpose
View and manage the tools within a single tool collection (a 'toolkit' — a tool-typed collection an agent owns): add tools, remove tools, edit/delete the collection itself.

## Key Features
- Header with back button, collection icon/name/description, metadata (item count, created/updated dates)
- Actions: **Add to Toolkit**, **Edit**, **Delete** (with confirm modal)
- Tools grid of ToolItemCards (entity name, added date, remove button)
- Empty state ('No tools in this toolkit') with add CTA
- Not-found state with back button

## Components Used
| Component | Path | Purpose |
|-----------|------|---------|
| ToolItemCard | inline in page | Tool card with remove action |
| EditCollectionModal | `components/features/collections/EditCollectionModal.tsx` | Edit collection details |
| DeleteConfirmationModal | `components/features/collections/DeleteConfirmationModal.tsx` | Delete confirmation |
| AddToolsToToolboxModal | `components/features/collections/AddToolsToToolboxModal.tsx` | Pick tools to add |

## Hooks Used
| Hook | Path | Purpose |
|------|------|---------|
| useParams | react-router-dom | Reads `collectionId` from URL |
| useNavigate | react-router-dom | Back navigation |

## Data Flow
- **Load**: `collectionsService.getCollection(collectionId)` -> `GET /api/v1/collections/{id}`
- **Add tools**: `AddToolsToToolboxModal` -> `POST /api/v1/collections/{id}/items` -> reload
- **Remove tool**: `removeItemFromCollection(id, itemId)` -> `DELETE /api/v1/collections/{id}/items/{itemId}` -> reload
- **Update**: `updateCollection(id, updates)` -> `PUT /api/v1/collections/{id}` -> reload
- **Delete**: `deleteCollection(id)` -> `DELETE /api/v1/collections/{id}` -> navigate back to `/toolkits`

## State Management
- `notificationStore` — success/error toasts for remove/update/delete
- Local state: collection, loading, error, modal states

## API Endpoints Called
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v1/collections/{id}` | Load toolbox |
| POST | `/api/v1/collections/{id}/items` | Add tools |
| DELETE | `/api/v1/collections/{id}/items/{itemId}` | Remove tool |
| PUT | `/api/v1/collections/{id}` | Update collection |
| DELETE | `/api/v1/collections/{id}` | Delete collection |

## Related Pages
- ToolCollectionsManagement — parent listing page
- CollectionsManagement / CollectionDetail — non-tool variant