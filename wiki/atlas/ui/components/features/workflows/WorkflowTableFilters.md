---
title: WorkflowTableFilters
type: atlas-component
path: frontend/src/components/features/workflows/WorkflowTableFilters.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# WorkflowTableFilters

**Path**: `frontend/src/components/features/workflows/WorkflowTableFilters.tsx`
**Last Updated**: 2026-08-01

## Purpose
Filter bar for the workflow (lists) table — search input + toggleable tag chips (click to add/remove; active tags show as badges with ✕) and a Clear Filters action.

## Props Interface
```typescript
interface WorkflowTableFiltersProps {
  searchQuery: string
  tags: string[]
  filterTags: string[]
  onSearch: (query: string) => void
  onFilterTagsChange: (tags: string[]) => void
}
```

## Dependencies
None (pure JSX, controlled component).

## Usage Example
```tsx
<WorkflowTableFilters searchQuery={q} tags={tags} filterTags={ft} onSearch={setQ} onFilterTagsChange={setFt} />
```

## State Used
None — fully controlled.

## Related Components
- features/workflows/WorkflowTable.tsx — owner table
- features/workflows/WorkflowTemplateTableFilters.tsx — template variant (adds category/type dropdowns)