---
title: Pagination (logs)
type: atlas-component
path: frontend/src/components/logs/Pagination.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# Pagination (logs)

**Path**: `frontend/src/components/logs/Pagination.tsx`
**Last Updated**: 2026-08-01

## Purpose
Log-table pagination — Prev/Next buttons, page-number buttons with ellipsis collapsing (max 5 visible: first, current±1, last), and an item-range display ('Showing X-Y of N logs'). Returns null when totalPages is 0.

## Props Interface
```typescript
interface PaginationProps {
  currentPage: number
  totalPages: number
  totalItems: number
  pageSize: number
  hasPrevPage: boolean
  hasNextPage: boolean
  onPrevPage: () => void
  onNextPage: () => void
  onPageChange: (page: number) => void
}
```

## Dependencies
None (pure JSX).

## Usage Example
```tsx
<Pagination
  currentPage={page}
  totalPages={totalPages}
  totalItems={total}
  pageSize={pageSize}
  hasPrevPage={page > 1}
  hasNextPage={page < totalPages}
  onPrevPage={() => setPage(p => p - 1)}
  onNextPage={() => setPage(p => p + 1)}
  onPageChange={setPage}
/>
```

## State Used
None — fully controlled via props.

## Related Components
- logs/LogsTable.tsx — table this paginates
- ui/tables/Pagination.tsx — generic table pagination variant