---
title: WorkflowTemplateTable
type: atlas-component
path: frontend/src/components/features/workflows/WorkflowTemplateTable.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# WorkflowTemplateTable

**Path**: `frontend/src/components/features/workflows/WorkflowTemplateTable.tsx`
**Last Updated**: 2026-08-01

## Purpose
Self-contained workflow-templates table — search/filter/sort/paginate over a passed-in template list. Owns its filter/sort/pagination state; renders Filters bar, zebra table (header + rows), and pagination. Empty states: 'No templates yet' vs 'No templates match your filters'.

## Props Interface
```typescript
interface WorkflowTemplateTableProps {
  templates: WorkflowTemplate[]
  selectedTemplateId?: string
  onSelect: (template: WorkflowTemplate) => void
  onEdit: (template: WorkflowTemplate) => void
  onExecute: (templateId: string) => void
  onDelete?: (template: WorkflowTemplate) => Promise<void>
  isLoading?: boolean
  tags?: string[]              // normalized tag names (see note)
  filterTags?: string[]
  onFilterTagsChange?: (tags: string[]) => void
}

export type SortColumn = 'name' | 'category' | 'workflow_type' | 'version' | 'updated_at' | 'tags'
export type SortDirection = 'asc' | 'desc'
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| WorkflowTemplateTableFilters | Component (local) | Filter bar |
| WorkflowTemplateTableHeader | Component (local) | Sortable header |
| WorkflowTemplateTableRow | Component (local) | Rows |
| WorkflowTablePagination | Component (local) | Pagination |
| WorkflowTemplate | types/workflows | Data shape |

## Usage Example
```tsx
<WorkflowTemplateTable templates={templates} selectedTemplateId={selected?.id} onSelect={setSelected} onEdit={openEditor} onExecute={run} onDelete={del} tags={tagNames} filterTags={ft} onFilterTagsChange={setFt} />
```

## State Used
- Single `State` object: sortColumn/sortDirection/searchQuery/filterCategory/filterType/currentPage/pageSize (default: name asc, '', '', '', 1, 25)
- Derived: categories (unique sorted), types (unique sorted), filteredAndSorted, paginated (useMemo)

## Related Components
- features/workflows/WorkflowTemplateTableFilters.tsx / -Header.tsx / -Row.tsx
- features/workflows/WorkflowTablePagination.tsx — shared pagination
- pages/WorkflowTemplates.tsx — page wiring (tags come from getTemplateCategories(); backend returns objects, normalized to strings)