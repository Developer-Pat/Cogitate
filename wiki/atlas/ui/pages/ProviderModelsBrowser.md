---
title: Provider Models Browser
type: atlas-page
path: frontend/src/pages/ProviderModelsBrowser.tsx
confidence: high
updated: 2026-07-31
tags: [type/page, domain/atlas-ui]
---
# Provider Models Browser

**Component**: `frontend/src/pages/ProviderModelsBrowser.tsx`
**Route**: `/providers/:providerId/models`
**Last Updated**: 2026-07-31

## Purpose
Browse and select models for a specific provider. Supports search, filtering, pagination; selection feeds back to agent creation.

## Key Features
- URL-param-driven filters (page, page_size, search, free_only, sort_by, sort_order) synced via useSearchParams
- Debounced search (300ms) via useDebounce
- **ModelFilters**: search/free-only/sort controls
- **ModelTable**: paginated model list with select + refresh
- Cache indicator ('From cache') when data served from provider cache
- Model selection stored in sessionStorage ('selectedModel') then navigates to `/agent-profiles` with `{ modelSelected: true }` state

## Components Used
| Component | Path | Purpose |
|-----------|------|---------|
| ErrorBoundary | `components/ErrorBoundary.tsx` | Crash containment |
| ModelFilters | `components/features/providers/ModelBrowser/ModelFilters.tsx` | Filter controls |
| ModelTable | `components/features/providers/ModelBrowser/ModelTable.tsx` | Model table + pagination |

## Hooks Used
| Hook | Path | Purpose |
|------|------|---------|
| usePageTitle | `hooks/usePageTitle.ts` | Sets document title |
| useDebounce | `hooks/useDebounce.ts` | Debounced search input |

## Data Flow
- **Load**: `modelBrowserService.browseModels(providerId, filters)` -> `GET /api/v1/providers/{id}/models/browse?{params}` -> models/total/total_pages/provider_name/from_cache
- **Selection**: model -> sessionStorage 'selectedModel' JSON -> navigate('/agent-profiles', { state: { modelSelected: true } })
- Filter changes update URL search params (deep-linkable state)

## State Management
- Local state: models, loading, error, total, totalPages, fromCache, providerName, filters
- URL search params as filter source of truth
- sessionStorage for model selection handoff

## API Endpoints Called
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v1/providers/{providerId}/models/browse` | Paginated/filtered model list |

## Related Pages
- ProviderDashboard — provider management (inline model browser)
- AgentProfiles — receives model selection for agent creation