---
title: ToolsTableHeader
type: atlas-component
path: frontend/src/components/Tools/ToolsTableHeader.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# ToolsTableHeader

**Path**: `frontend/src/components/Tools/ToolsTableHeader.tsx`
**Last Updated**: 2026-08-01

## Purpose
Sortable tools-table header with select-all checkbox.

## Props Interface
```typescript
interface ToolsTableHeaderProps {
  sortColumn: SortColumn
  sortDirection: SortDirection
  allSelected: boolean
  onSort: (column: SortColumn) => void
  onSelectAll: () => void
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| SortColumn, SortDirection | types/tools | Sort state |

## Usage Example
```tsx
<ToolsTableHeader sortColumn={sort} sortDirection={dir} allSelected={all} onSort={setSort} onSelectAll={toggleAll} />
```

## State Used
None — controlled.

## Related Components
- Tools/ToolsTable.tsx — owner
- Tools/ToolsTableRow.tsx — rows