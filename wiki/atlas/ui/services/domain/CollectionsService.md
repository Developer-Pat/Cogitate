---
title: Collections Service
type: atlas-service
path: frontend/src/services/domain/CollectionsService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# Collections Service

**Path**: `frontend/src/services/domain/CollectionsService.ts`
**Type**: service

## Purpose

API client for collection management. Collections are named, colored, icon-bearing containers of entities (agents, tools, providers, macro sets, templates, workflows). The service provides CRUD for collections, CRUD for collection items (entities added to a collection), lookups of which collections contain a given entity, and a 2-minute in-memory cache for unfiltered collection listings. **Teams are modeled as collections** — see Data Flow / Notes.

The file exports a class, a named singleton, and a default export (multi-export file):

- `export class CollectionsService` (the class)
- `export const collectionsService = new CollectionsService()` (named singleton)
- `export default collectionsService` (default export — same singleton)

Consumers import the named singleton `collectionsService`.

## Exported API (exact signatures)

```ts
class CollectionsService {
  private basePath = '/api/v1/collections';
  private collectionsCache: Collection[] | null = null;
  private cacheTimestamp: number | null = null;
  private readonly CACHE_TTL = 2 * 60 * 1000; // 2 minutes

  async listCollections(filters: CollectionFilters = {}): Promise<CollectionListResponse>
  async getCollection(collectionId: string): Promise<Collection>
  async createCollection(collectionData: CollectionCreate): Promise<Collection>
  async updateCollection(collectionId: string, collectionData: CollectionUpdate): Promise<Collection>
  async deleteCollection(collectionId: string): Promise<void>
  async addItemToCollection(collectionId: string, itemData: CollectionItemCreate): Promise<CollectionItem>
  async removeItemFromCollection(collectionId: string, itemId: string): Promise<void>
  async getCollectionItems(collectionId: string): Promise<CollectionItem[]>
  async findCollectionsContainingEntity(entityType: string, entityId: string): Promise<CollectionContainsResponse>
  async isEntityInAnyCollection(entityType: string, entityId: string): Promise<boolean>
  clearCache(): void
  private invalidateCache(): void
}
```

Method behavior details:

- `listCollections(filters)` — accepts `{ entity_type?, search?, is_active?, limit? (default 100), offset? (default 0) }`. Serves unfiltered basic listings (no `entity_type`, no `search`, `is_active` undefined, `offset === 0`) from cache when fresh (< CACHE_TTL); refreshes and repopulates the cache on a successful fetch. Filtered calls bypass the cache.
- `createCollection` / `updateCollection` / `deleteCollection` / `addItemToCollection` / `removeItemFromCollection` — all invalidate the cache after success.
- `findCollectionsContainingEntity(entityType, entityId)` — looks up every collection containing an entity, keyed by entity type + id.
- `isEntityInAnyCollection(entityType, entityId)` — convenience wrapper returning `result.total > 0`; on error it logs and returns `false` (error-swallowing).
- `clearCache()` — public cache reset (delegates to `invalidateCache()`).

Request/response types (from `frontend/src/types/collections.ts`):

```ts
type CollectionEntityType = 'agent' | 'tool' | 'provider' | 'macro_set' | 'template' | 'workflow';

interface Collection {
  id: string; name: string; description: string | null;
  entity_type: CollectionEntityType; color: string; icon: string;
  user_key: string; is_active: boolean; item_count: number;
  items: CollectionItem[]; created_at: string; updated_at: string;
}
interface CollectionItem {
  id: string; collection_id: string; entity_id: string;
  entity_type: CollectionEntityType; entity_name: string; added_at: string;
}
interface CollectionCreate {
  name: string; description?: string; entity_type: CollectionEntityType;
  color?: string; icon?: string; user_key?: string;
}
interface CollectionUpdate {
  name?: string; description?: string; color?: string; icon?: string; is_active?: boolean;
}
interface CollectionItemCreate { entity_id: string; entity_type: CollectionEntityType; entity_name: string; }
interface CollectionListResponse { collections: Collection[]; total: number; }
interface CollectionContainsResponse { collections: Collection[]; total: number; }
interface CollectionFilters {
  entity_type?: CollectionEntityType; search?: string; is_active?: boolean;
  limit?: number; offset?: number;
}
```

## Endpoints

Base path: `/api/v1/collections`

| Method | Endpoint | Service method |
|---|---|---|
| GET | `/api/v1/collections` (query: `entity_type`, `search`, `is_active`, `limit`, `offset`) | `listCollections` |
| GET | `/api/v1/collections/:collectionId` | `getCollection` |
| POST | `/api/v1/collections` | `createCollection` |
| PUT | `/api/v1/collections/:collectionId` | `updateCollection` |
| DELETE | `/api/v1/collections/:collectionId` | `deleteCollection` |
| POST | `/api/v1/collections/:collectionId/items` | `addItemToCollection` |
| GET | `/api/v1/collections/:collectionId/items` | `getCollectionItems` |
| DELETE | `/api/v1/collections/:collectionId/items/:itemId` | `removeItemFromCollection` |
| GET | `/api/v1/collections/contains/:entityType/:entityId` | `findCollectionsContainingEntity` |

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `frontend/src/types/collections` | import type | Domain types (`Collection`, `CollectionItem`, `CollectionCreate`, `CollectionUpdate`, `CollectionItemCreate`, `CollectionListResponse`, `CollectionContainsResponse`, `CollectionFilters`, `CollectionEntityType`) |
| `../apiClient` (`apiClient`) | module singleton (`EnhancedApiClient`) | HTTP client. Returns `ApiResponse<T>` shaped `{ error?, data? }`; sends `Authorization: Bearer <token>` from localStorage; 10s timeout, 3 retries; base URL from `VITE_API_URL` (default `http://localhost:8000`) |
| `../frontendLoggingService` | module singleton | `debug` / `info` / `error` logging for cache hits, successful ops, and failures |

## Usage Example

```ts
import { collectionsService } from '../services/domain/CollectionsService';

// List all collections (cached for 2 minutes)
const { collections, total } = await collectionsService.listCollections();

// List only tool collections
const toolCollections = await collectionsService.listCollections({ entity_type: 'tool' });

// Create + add an item
const collection = await collectionsService.createCollection({
  name: 'My Tools',
  entity_type: 'tool',
  color: '#3b82f6',
  icon: 'wrench',
});
await collectionsService.addItemToCollection(collection.id, {
  entity_id: tool.id,
  entity_type: 'tool',
  entity_name: tool.name,
});

// Find which collections contain an entity
const { collections: containing } = await collectionsService.findCollectionsContainingEntity('tool', tool.id);
```

## Data Flow / Notes

- All calls go through `apiClient` (fetch wrapper); every method checks `response.error` and throws `new Error(response.error.message)` on failure, logging via `frontendLoggingService` before rethrowing (except `isEntityInAnyCollection`, which returns `false` on error).
- **Teams are modeled as collections.** There is no separate team entity type — `CollectionEntityType` is `'agent' | 'tool' | 'provider' | 'macro_set' | 'template' | 'workflow'` (no `'team'`). `TeamsManagement.tsx` states "Lists all teams (agent collections)" and loads/creates teams as collections with `entity_type: 'agent'` (`listCollections({ entity_type: 'agent' })`, `createCollection({ ... entity_type: 'agent' })`). Team routes navigate to `/teams/:collectionId`.
- `entity_type` values in use by consumers: `'agent'` (teams, agent lists, agent profiles), `'tool'` (toolboxes, tool collections), `'provider'` (provider cards).
- Cache: only the unfiltered `listCollections()` listing is cached (2-minute TTL). Every mutation (collection or item create/update/delete) invalidates the cache. `clearCache()` exposes manual invalidation (e.g., for tests).
- Item identity: an item is keyed by `entity_id` + `entity_type`; `removeItemFromCollection(collectionId, itemId)` takes the item's own `id` (not `entity_id`) — callers pass `item.id` from the item list.
- `item_count` on `Collection` is populated by the backend (list responses include it; the frontend sorts by it in `TeamsManagement`).

## Related

Consumers (16 files import `collectionsService`):

- Pages: `frontend/src/pages/CollectionsManagement.tsx` (list + create/update/delete), `frontend/src/pages/CollectionDetail.tsx` (get, remove item, update, delete), `frontend/src/pages/ToolCollectionsManagement.tsx` (tool collections CRUD), `frontend/src/pages/ToolCollectionDetail.tsx` (get, remove item, update, delete), `frontend/src/pages/TeamsManagement.tsx` (teams-as-`agent`-collections CRUD), `frontend/src/pages/AgentInteraction.tsx` (`getCollectionItems` for the selected agent list).
- Components: `frontend/src/components/features/collections/AddToCollectionModal.tsx` (list by `entity_type` + `addItemToCollection`), `frontend/src/components/features/collections/AddToolsToToolboxModal.tsx` (`addItemToCollection`), `frontend/src/components/features/agentTools/ToolBrowser/ToolCard.tsx` (`findCollectionsContainingEntity('tool', ...)`), `frontend/src/components/features/providers/ProviderCard.tsx` (`findCollectionsContainingEntity('provider', ...)`), `frontend/src/components/features/agentInteraction/AgentListSelector.tsx` (`listCollections({ entity_type: 'agent' })`), `frontend/src/components/Tools/ToolCollectionsTab.tsx`, `frontend/src/components/AgentProfiles/CollectionsTab.tsx`, `frontend/src/components/AgentProfiles/CollectionsBadges.tsx`, `frontend/src/components/Teams/AddToolboxesModal.tsx` (`listCollections({ entity_type: 'tool' })`).

## Deprecation / Obsolete Notes

- **No deprecation markers** (`@deprecated`, "legacy", "no longer used") exist in the source; the service is actively consumed by 16 files across pages and components.
- **`isEntityInAnyCollection` has zero consumers** — it is defined and exported but never called outside the service itself. Likely a candidate for removal or future use; flag for review.
- **`clearCache()` has no external callers** in the frontend (only its definition; the pattern exists elsewhere — e.g. `AgentService.clearCache()` is called by `useAgentSelection`). Retained as a public utility (tests may use it).
- The old atlas at `docs/atlas/` was NOT used as a source for this doc; content is derived from the current source only.
