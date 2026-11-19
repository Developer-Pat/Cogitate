---
title: WorkflowTemplateTableFilters
type: atlas-component
path: frontend/src/components/features/workflows/WorkflowTemplateTableFilters.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# WorkflowTemplateTableFilters

**Path**: `frontend/src/components/features/workflows/WorkflowTemplateTableFilters.tsx`
**Last Updated**: 2026-08-01

## Purpose
Filter bar for the workflow templates table — search input (name/description/tag), category dropdown, type dropdown, and additive tag chips (select from '+ Tag' dropdown, removable ✕ badges).

## Props Interface
```typescript
interface Props {
  searchQuery: string
  categories: string[]   // normalized strings (see note below)
  types: string[]
  tags: string[]
  filterTags: string[]
  filterCategory: string
  filterType: string
  onSearch: (query: string) => void
  onCategoryFilter: (category: string) => void
  onTypeFilter: (type: string) => void
  onFilterTagsChange: (tags: string[]) => void
  onClear: () => void
  hasActiveFilters: boolean
}
```

## Dependencies
None (pure JSX, controlled component).

## Usage Example
```tsx
<WorkflowTemplateTableFilters searchQuery={q} categories={cats} types={types} tags={tags} filterTags={ft} filterCategory={fc} filterType={fty} onSearch={setQ} onCategoryFilter={setFc} onTypeFilter={setFty} onFilterTagsChange={setFt} onClear={clearAll} hasActiveFilters={active} />
```

## State Used
None — fully controlled.

## Related Components
- features/workflows/WorkflowTemplateTable.tsx — owner table
- services/domains/llm/workflowService.ts — getTemplateCategories() normalizes backend category/tag objects to strings (categories `{id,name,...}` → `name`, tags `{name,count}` → `name`)