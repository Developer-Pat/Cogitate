---
title: WorkflowTablePagination
type: atlas-component
path: frontend/src/components/features/workflows/WorkflowTablePagination.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# WorkflowTablePagination

**Path**: `frontend/src/components/features/workflows/WorkflowTablePagination.tsx`
**Last Updated**: 2026-08-01

## Purpose
Pagination controls for the workflow table — page buttons, prev/next, page-size selector, and item-range display.

## Props Interface
```typescript
interface WorkflowTablePaginationProps {
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
<WorkflowTablePagination currentPage={page} pageSize={size} totalItems={total} onPageChange={setPage} onPageSizeChange={setSize} />
```

## State Used
None — controlled.

## Related Components
- features/workflows/WorkflowTable.tsx — owner
- ui/tables/Pagination.tsx — generic pagination alternative