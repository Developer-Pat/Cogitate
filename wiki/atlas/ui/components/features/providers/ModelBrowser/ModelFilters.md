---
title: ModelFilters
type: atlas-component
path: frontend/src/components/features/providers/ModelBrowser/ModelFilters.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# ModelFilters

**Path**: `frontend/src/components/features/providers/ModelBrowser/ModelFilters.tsx`
**Last Updated**: 2026-08-01

## Purpose
Search + filter bar for the model browser — search input (applied live; parent debounces), sort dropdown (name/context_length/pricing_prompt/provider with asc/desc toggle), 'Free models only' checkbox, capability chips (fetched per provider), and Clear Filters.

## Props Interface
```typescript
interface ModelFiltersProps {
  filters: ModelBrowserFilters
  onFilterChange: (filters: Partial<ModelBrowserFilters>) => void
  providerId?: number
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| modelBrowserService.getCapabilities(providerId) | Service | Capability chip list |
| CapabilityInfo, ModelBrowserFilters | modelBrowserService types | Data shapes |
| frontendLoggingService | Service | Error logging |

## Usage Example
```tsx
<ModelFilters filters={filters} onFilterChange={setFilters} providerId={provider?.id} />
```

## State Used
- searchTerm (local mirror), capabilities, loadingCapabilities

## Related Components
- features/providers/ModelBrowser/ModelTable.tsx — sibling results table
- pages/ProviderModelsBrowser.tsx — owner page
- services/domains/providers/modelBrowserService.ts — capabilities endpoint