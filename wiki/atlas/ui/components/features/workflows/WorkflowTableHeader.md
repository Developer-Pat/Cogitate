---
title: WorkflowTableHeader
type: atlas-component
path: frontend/src/components/features/workflows/WorkflowTableHeader.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# WorkflowTableHeader

**Path**: `frontend/src/components/features/workflows/WorkflowTableHeader.tsx`
**Last Updated**: 2026-08-01

## Purpose
Sortable column header row for the workflow table — click to sort, sort icon appears on the active column (faded on hover for others).

## Props Interface
```typescript
interface WorkflowTableHeaderProps {
  sortColumn: SortColumn
  sortDirection: SortDirection
  onSort: (column: SortColumn) => void
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| SortColumn, SortDirection | types/workflows | Sort state |

## Usage Example
```tsx
<WorkflowTableHeader sortColumn={sort} sortDirection={dir} onSort={setSort} />
```

## State Used
None — controlled.

## Related Components
- features/workflows/WorkflowTable.tsx — owner
- features/workflows/WorkflowTemplateTableHeader.tsx — template variant