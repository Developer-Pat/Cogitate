---
title: Model Browser Service
type: atlas-service
path: frontend/src/services/domains/providers/modelBrowserService.ts
confidence: high
updated: 2026-10-09
tags: [type/service, domain/atlas-ui]
---

# Model Browser Service

**Path**: `frontend/src/services/domains/providers/modelBrowserService.ts`
**Type**: service

## Purpose

Provides a unified interface for browsing, searching, and discovering LLM models across different providers. It wraps the provider models-browsing API endpoints behind a singleton (`modelBrowserService`) and supports filtering (search, capabilities, context-length range, free-only, price caps), pagination, and sorting. Also exposes per-model detail lookup and a capabilities catalog used to populate filter UI. Errors are caught internally and normalized into `ApiResponse` error payloads instead of throwing.

## Exported API

The module exports a singleton instance, a service interface, and seven types. The `ModelBrowserService` class itself is **not** exported (module-private).

### Singleton

```ts
export const modelBrowserService: IModelBrowserService = new ModelBrowserService()
export default modelBrowserService
```

### Interface `IModelBrowserService`

```ts
export interface IModelBrowserService {
  browseModels(providerId: number, filters?: ModelBrowserFilters): Promise<ApiResponse<ModelBrowserResponse>>
  getModelDetails(providerId: number, modelId: string): Promise<ApiResponse<ModelDetailsResponse>>
  getCapabilities(providerId: number): Promise<ApiResponse<CapabilitiesResponse>>
}
```

### Methods (implementation `ModelBrowserService`)

```ts
async browseModels(providerId: number, filters: ModelBrowserFilters = {}): Promise<ApiResponse<ModelBrowserResponse>>
```
Browses models for a provider with filtering and pagination. Builds query params from `filters`, then `GET /api/v1/providers/{providerId}/models/browse`. On error returns a normalized `ApiResponse` with `status: 500`, `code: 'BROWSE_ERROR'`.

```ts
async getModelDetails(providerId: number, modelId: string): Promise<ApiResponse<ModelDetailsResponse>>
```
Fetches detailed info for a single model (`modelId` is `encodeURIComponent`-escaped) via `GET /api/v1/providers/{providerId}/models/{modelId}`. Error code: `'DETAILS_ERROR'`.

```ts
async getCapabilities(providerId: number): Promise<ApiResponse<CapabilitiesResponse>>
```
Fetches the catalog of available capabilities for filter UI via `GET /api/v1/providers/{providerId}/models/capabilities`. Error code: `'CAPABILITIES_ERROR'`.

### Types

```ts
export interface ModelBrowserFilters {
  search?: string
  capabilities?: string[]
  min_context_length?: number
  max_context_length?: number
  free_only?: boolean
  max_price_prompt?: number
  max_price_completion?: number
  providers?: string[]
  page?: number
  page_size?: number
  sort_by?: string
  sort_order?: 'asc' | 'desc'
}

export interface ModelInfo {
  id: string
  name: string
  display_name?: string
  description?: string
  context_length?: number
  architecture?: string
  modality?: string
  function_calling?: boolean
  pricing_prompt?: number
  pricing_completion?: number
  /** The nested shape the API also sends (`{prompt, completion}`, per token). openrouter's rows
   *  carry ONLY this, so a reader that looks at the flat fields alone shows `N/A` for them. */
  pricing?: { prompt?: number | null; completion?: number | null }
  top_provider?: string
  capabilities?: string[]
  capability_badges?: ModelCapabilityBadge[]
  context_category?: 'standard' | 'long' | 'very_long' | 'ultra_long'
  _raw?: unknown
}

export interface ModelCapabilityBadge {
  id: string
  label: string
  color: string
  icon: string
}

export interface CapabilityInfo {
  id: string
  name: string
  count?: number
}

export interface ModelBrowserResponse {
  models: ModelInfo[]
  total: number
  page: number
  page_size: number
  total_pages: number
  has_more: boolean
  filters_applied: ModelBrowserFilters
  from_cache: boolean
  provider_name: string
}

export interface ModelDetailsResponse {
  model: ModelInfo
  provider_name: string
}

export interface CapabilitiesResponse {
  capabilities: CapabilityInfo[]
  total: number
  provider_name: string
}
```

## Endpoints

Base path: `/api/v1/providers` (constant `basePath`).

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/providers/{providerId}/models/browse` | Browse/search models with filtering, pagination, sorting |
| GET | `/api/v1/providers/{providerId}/models/{modelId}` | Get details for one model (`modelId` URI-escaped) |
| GET | `/api/v1/providers/{providerId}/models/capabilities` | List available capabilities for filter UI |

Query params on `browse` (note the `min_context_length`/`max_context_length` → `min_context`/`max_context` renames): `search`, `capabilities` (repeated), `min_context`, `max_context`, `free_only=true`, `max_price_prompt`, `max_price_completion`, `providers` (repeated), `page` (default 1), `page_size` (default 50), `sort_by` (default `name`), `sort_order` (default `asc`).

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `apiClient` (`../../apiClient`) | service (import) | Performs the `GET` HTTP calls |
| `frontendLoggingService` (`../../frontendLoggingService`) | service (import) | `debug`/`info`/`error` logging for browse, details, capabilities |
| `ApiResponse` (`../../../types`) | type (import) | Return wrapper for all three methods |

## Usage Example

```ts
import { modelBrowserService, type ModelBrowserFilters } from '../services/domains/providers/modelBrowserService'

const filters: ModelBrowserFilters = {
  search: 'gpt',
  free_only: true,
  page: 1,
  page_size: 50,
  sort_by: 'name',
  sort_order: 'asc',
}

const response = await modelBrowserService.browseModels(1, filters)
if (response.data) {
  console.log(response.data.models, response.data.total_pages, response.data.from_cache)
} else if (response.error) {
  console.error(response.error.code, response.error.message) // e.g. 'BROWSE_ERROR'
}
```

## Data Flow / Notes

- **Filter param mapping**: `min_context_length` → `min_context`, `max_context_length` → `max_context`; `capabilities` and `providers` are appended as repeated query params; defaults `page=1`, `page_size=50`, `sort_by=name`, `sort_order=asc` are always appended.
- **Error handling**: every method wraps its call in try/catch and returns a normalized `ApiResponse` with `status: 500`, `timestamp` (ISO), and an error object (`code` + `message`) rather than throwing. Callers must check both `response.data` and `response.error` (see usage example).
- **Caching**: the browse response carries `from_cache`; the page surfaces it as a "From cache" indicator — caching itself is server-side.
- **Pagination/sorting**: default page size 50; `sort_by` defaults to `name`, `sort_order` to `asc`.
- **Provider ID**: methods take a numeric `providerId` (the page parses it from the route param).

## Related

Consumers (all in `frontend/src`):

- **`pages/ProviderModelsBrowser.tsx`** — primary consumer; route `/providers/:providerId/models`-style browsing page. Calls `browseModels` with debounced search (300ms) and filters synced to URL search params; renders `ModelFilters` + `ModelTable`; stores model selection in `sessionStorage` and navigates back to `/agent-profiles`.
- **`components/features/providers/ModelBrowser/ModelFilters.tsx`** — calls `getCapabilities(providerId)` on mount/provider change to populate the capability filter options; imports `CapabilityInfo`, `ModelBrowserFilters` types.
- **`components/features/providers/ModelBrowser/ModelTable.tsx`** — type-only consumer (`ModelInfo`, `ModelCapabilityBadge`); renders the paginated table with expandable detail rows.
- **`pages/ProviderDashboard.tsx`** — inline model-browser modal; calls `browseModels(browseProviderId, modelFilters)`; imports `ModelBrowserFilters` type.
- **`components/AgentProfiles/ProfileDetail.tsx`** — 3-tier model fetch ("Tier 1: modelBrowserService → Tier 2: curated models → Tier 3: manual input"); calls `browseModels(pid, { page_size: 50 })`, falling back to `getCuratedModelsForProvider` on failure/empty.
- **`config/curatedModels.ts`** — commented-out `import type { ModelInfo }` only; no active dependency.

## Deprecation / Obsolete Notes

- **No deprecation markers** (`@deprecated`, "deprecated", "legacy", etc.) in the source; the service is actively consumed (5 live consumer files).
- **`getModelDetails` is effectively unused**: the only references are its interface declaration (line 108) and its implementation (line 180) — no consumer calls it. It is not marked deprecated, but is dead API surface; the model-details expansion in `ModelTable` is fed by the already-loaded `ModelInfo` rows rather than this method.
- `curatedModels.ts`'s type import is commented out — not a live consumer.
