---
title: CollectionsFilters
type: atlas-component
path: frontend/src/components/features/collections/CollectionsFilters.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# CollectionsFilters

**Path**: `frontend/src/components/features/collections/CollectionsFilters.tsx`
**Last Updated**: 2026-08-01

## Purpose
Collections filter bar — entity-type dropdown (None/All/Tools/Providers/Macro Sets/Templates), search input, and sort select (name/itemCount/createdAt/updatedAt).

## Props Interface
```typescript
type SortOption = 'name' | 'itemCount' | 'createdAt' | 'updatedAt'

interface CollectionsFiltersProps {
  filterType: EntityType | 'all' | 'none'
  onFilterTypeChange: (type: EntityType | 'all' | 'none') => void
  searchQuery: string
  onSearchQueryChange: (query: string) => void
  sortOption: SortOption
  onSortOptionChange: (option: SortOption) => void
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| EntityType | mocks/collectionsData | Type union for dropdown options |

## Usage Example
```tsx
<CollectionsFilters filterType={ft} onFilterTypeChange={setFt} searchQuery={q} onSearchQueryChange={setQ} sortOption={s} onSortOptionChange={setS} />
```

## State Used
None — fully controlled.

## Related Components
- features/collections/EmptyState.tsx — empty results state
- features/collections/CollectionsHeader.tsx — page header