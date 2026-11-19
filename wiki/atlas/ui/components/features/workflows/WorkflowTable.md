---
title: WorkflowTable
type: atlas-component
path: frontend/src/components/features/workflows/WorkflowTable.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# WorkflowTable

**Path**: `frontend/src/components/features/workflows/WorkflowTable.tsx`
**Last Updated**: 2026-08-01

## Purpose
Self-contained workflow-lists table — search + tag filter + sort + paginate over passed-in workflow lists. Owns filter/sort/pagination state; renders Filters bar, zebra table, and pagination. Empty states: 'No workflow lists yet' / 'No workflow lists match your filters'.

## Props Interface
```typescript
interface WorkflowTableProps {
  workflowLists: WorkflowList[]
  selectedListId?: string
  onSelectList: (list: WorkflowList) => void
  onEdit: (list: WorkflowList) => void
  onDelete: (list: WorkflowList) => Promise<void>
  isLoading?: boolean
  onViewModeChange?: (mode: string) => void   // currently unused (destructured as _onViewModeChange)
  tags?: string[]
  filterTags?: string[]
  onFilterTagsChange?: (tags: string[]) => void
}

export type SortColumn = 'name' | 'workflow_count' | 'updated_at' | 'tags'
export type SortDirection = 'asc' | 'desc'
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| WorkflowTableFilters | Component (local) | Search + tag bar |
| WorkflowTableHeader | Component (local) | Sortable header |
| WorkflowTableRow | Component (local) | Rows |
| WorkflowTablePagination | Component (local) | Pagination |
| WorkflowList | types/workflows | Data shape |

## Usage Example
```tsx
<WorkflowTable workflowLists={lists} selectedListId={selected?.id} onSelectList={setSelected} onEdit={openEditor} onDelete={del} tags={tagNames} filterTags={ft} onFilterTagsChange={setFt} />
```

## State Used
- WorkflowTableState: sortColumn/sortDirection/searchQuery/currentPage/pageSize (default: name asc, '', 1, 25)
- Derived: filteredAndSortedLists, paginatedLists (useMemo)

## Related Components
- features/workflows/WorkflowTableFilters.tsx / -Header.tsx / -Row.tsx / -Actions.tsx
- features/workflows/WorkflowTablePagination.tsx — shared pagination
- features/workflows/WorkflowTemplateTable.tsx — template variant (different sort columns)