---
title: WorkflowTemplateTableHeader
type: atlas-component
path: frontend/src/components/features/workflows/WorkflowTemplateTableHeader.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# WorkflowTemplateTableHeader

**Path**: `frontend/src/components/features/workflows/WorkflowTemplateTableHeader.tsx`
**Last Updated**: 2026-08-01

## Purpose
Sortable column header for the workflow templates table — columns: Name, Category, Type, Version, Tags, Updated At (+ selection column).

## Props Interface
```typescript
interface Props {
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
<WorkflowTemplateTableHeader sortColumn={sort} sortDirection={dir} onSort={setSort} />
```

## State Used
None — controlled.

## Related Components
- features/workflows/WorkflowTemplateTable.tsx — owner
- features/workflows/WorkflowTableHeader.tsx — non-template variant