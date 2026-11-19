---
title: ToolsTablePagination
type: atlas-component
path: frontend/src/components/Tools/ToolsTablePagination.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# ToolsTablePagination

**Path**: `frontend/src/components/Tools/ToolsTablePagination.tsx`
**Last Updated**: 2026-08-01

## Purpose
Tools-table pagination — page buttons, prev/next, page-size selector, item-range display.

## Props Interface
```typescript
interface ToolsTablePaginationProps {
  currentPage: number
  pageSize: number
  totalItems: number
  onPageChange: (page: number) => void
  onPageSizeChange: (pageSize: number) => void
}
```

## Dependencies
None (pure JSX).

## Usage Example
```tsx
<ToolsTablePagination currentPage={page} pageSize={size} totalItems={total} onPageChange={setPage} onPageSizeChange={setSize} />
```

## State Used
None — controlled.

## Related Components
- Tools/ToolsTable.tsx — owner
- features/workflows/WorkflowTablePagination.tsx — similar variant