---
title: AgentTableHeader
type: atlas-component
path: frontend/src/components/AgentProfiles/AgentTableHeader.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# AgentTableHeader

**Path**: `frontend/src/components/AgentProfiles/AgentTableHeader.tsx`
**Last Updated**: 2026-08-01

## Purpose
Sortable agents-table header with select-all checkbox.

## Props Interface
```typescript
interface AgentTableHeaderProps {
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
| SortColumn, SortDirection | types | Sort state |

## Usage Example
```tsx
<AgentTableHeader sortColumn={sort} sortDirection={dir} allSelected={all} onSort={setSort} onSelectAll={toggleAll} />
```

## State Used
None — controlled.

## Related Components
- AgentProfiles/AgentTable.tsx — owner
- Tools/ToolsTableHeader.tsx — parallel pattern