---
title: EmptyState (collections)
type: atlas-component
path: frontend/src/components/features/collections/EmptyState.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# EmptyState (collections)

**Path**: `frontend/src/components/features/collections/EmptyState.tsx`
**Last Updated**: 2026-08-01

## Purpose
Empty-results state for the collections page — 'No collections found' (search variant with 🔍) or team-specific empty state with a create CTA.

## Props Interface
```typescript
interface EmptyStateProps {
  filterType: EntityType | 'all' | 'team'
  searchQuery: string
  onCreate: () => void
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| EntityType | mocks/collectionsData | Type union |

## Usage Example
```tsx
{filtered.length === 0 && <EmptyState filterType={ft} searchQuery={q} onCreate={openCreate} />}
```

## State Used
None — stateless.

## Related Components
- features/collections/CollectionsFilters.tsx — filters that lead to empty state
- pages/CollectionsManagement.tsx — owner