---
title: ModelTable
type: atlas-component
path: frontend/src/components/features/providers/ModelBrowser/ModelTable.tsx
confidence: high
updated: 2026-10-09
tags: [type/component, domain/atlas-ui]
---
# ModelTable

**Path**: `frontend/src/components/features/providers/ModelBrowser/ModelTable.tsx`
**Last Updated**: 2026-10-09

## Purpose
Paginated model table with expandable rows — name/provider/context length (K/M formatted)/pricing columns, capability badge chips (color-mapped), expand-to-details, loading/error states, and Pagination footer.

## The Pricing column (2026-10-09)
The stored figure is **per token**; the column renders it **per million** with the unit spelled out
(`$2.50 / 1M`) — a per-token value at four decimals printed every real price as `$0.0000`.

`priceOf(model, side)` reads **whichever shape the provider sent**: the nested
`pricing: {prompt, completion}` or the flat `pricing_prompt` / `pricing_completion`. The payload is
NOT uniform — openrouter's rows carry only the nested shape, deepseek's carry both — so reading only
the flat fields left openrouter's entire column as `N/A`.

`formatPrice` renders `Free` for a zero and **`Variable`** for a NEGATIVE price: openrouter's `-1`
means "pricing not published", and the old formatter printed it as `$-1.0000`.

There is **no price-tier badge**: `pricing_tier` was computed in the provider browsers
(`openrouter_browser`, `deepseek_browser`, `ollama_browser`) but never delivered to this table, so the
badge could never render. Removed 2026-10-09. A tier is a derived value — it can be re-added from the
price with no schema or payload change if it is ever wanted.

## Curated badges (2026-08-03)
Models that are curated (per the browse endpoint's `curated` enrichment)
render badges next to the display name: **✓ Verified** (badge-success, confirmed in
the provider catalog). Non-curated models render no badges. See the
browse endpoint enrichment in `models_router.py` (loads the provider's
curated set once and annotates each model).

## Props Interface
```typescript
interface ModelTableProps {
  models: ModelInfo[]
  loading: boolean
  error: string | null
  currentPage: number
  totalPages: number
  pageSize: number
  totalItems: number
  onPageChange: (page: number) => void
  onPageSizeChange: (size: number) => void
  onSelectModel: (model: ModelInfo) => void
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| Pagination | ui/tables/Pagination | Page footer |
| ModelInfo, ModelCapabilityBadge | modelBrowserService | Data shapes |

## Usage Example
```tsx
<ModelTable models={models} loading={loading} error={err} currentPage={page} totalPages={totalPages} pageSize={size} totalItems={total} onPageChange={setPage} onPageSizeChange={setSize} onSelectModel={select} />
```

## State Used
- expandedModelId (row expansion, local useState)

## Related Components
- features/providers/ModelBrowser/ModelFilters.tsx — sibling filter bar
- pages/ProviderModelsBrowser.tsx — owner page
- ui/tables/Pagination.tsx — pagination component
