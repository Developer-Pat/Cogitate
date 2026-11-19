---
title: Pagination
type: atlas-component
path: frontend/src/components/ui/tables/Pagination.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# Pagination

**Path**: `frontend/src/components/ui/tables/Pagination.tsx`
**Last Updated**: 2026-08-01

## Purpose

`Pagination` is a controlled pagination control bar for data tables. It renders a page-size selector, an item-count summary ("Showing X to Y of Z items"), Previous/Next buttons, numbered page buttons with ellipsis collapsing for large page counts, and an optional "Go to" quick-jumper input. It is fully controlled — the parent supplies `currentPage`, `totalPages`, and change callbacks — and is styled with DaisyUI/Tailwind tokens (light/dark aware).

The file also exports the `usePagination` hook, a small stateful helper for **server-side pagination**. It tracks `currentPage` and `pageSize` in local state, derives `totalPages` from an optional `totalItems` prop, and returns change handlers plus a `getOffset()` helper for computing server query offsets (`(page - 1) * pageSize`). Changing the page size resets the page to 1.

## Props Interface

```typescript
export interface PaginationProps {
  currentPage: number;
  totalPages: number;
  totalItems?: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange?: (size: number) => void;
  className?: string;
  showPageSizeOptions?: boolean;
  pageSizeOptions?: number[];
  showTotalItems?: boolean;
  showQuickJumper?: boolean;
}

// Server-side pagination hook
export interface UsePaginationProps {
  initialPage?: number;
  initialPageSize?: number;
  totalItems?: number;
}
```

Default prop values: `className = ''`, `showPageSizeOptions = true`, `pageSizeOptions = [10, 25, 50, 100]`, `showTotalItems = true`, `showQuickJumper = false`; hook defaults: `initialPage = 1`, `initialPageSize = 10`.

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `React` | import | JSX rendering; `useState` in `usePagination`; `React.ChangeEvent<HTMLSelectElement>` typing |

No external libraries, stores, or services are used — the component is self-contained.

## Usage Example

```tsx
import { Pagination, usePagination } from '../../../components/ui/tables/Pagination';

function ServerPaginatedTable() {
  const { currentPage, pageSize, totalPages, onPageChange, onPageSizeChange, getOffset } =
    usePagination({ initialPage: 1, initialPageSize: 25, totalItems: 247 });

  // Pass getOffset() to the server query, e.g. fetchItems({ offset: getOffset(), limit: pageSize })

  return (
    <Pagination
      currentPage={currentPage}
      totalPages={totalPages}
      totalItems={247}
      pageSize={pageSize}
      onPageChange={onPageChange}
      onPageSizeChange={onPageSizeChange}
      showQuickJumper
    />
  );
}
```

## State Used

All table state is **controlled** from the parent via props (`currentPage`, `pageSize`, `totalPages`, callbacks) — the `Pagination` component itself holds no state.

The `usePagination` hook owns two pieces of local state:

- `currentPage` — initialized from `initialPage` (default `1`)
- `pageSize` — initialized from `initialPageSize` (default `10`)

Derived values: `totalPages = totalItems ? Math.ceil(totalItems / pageSize) : 0`, and `getOffset() = (currentPage - 1) * pageSize`. `handlePageSizeChange` resets `currentPage` to 1 when the page size changes.

## Related Components

- `frontend/src/components/ui/tables/DataTable.tsx` — sibling table primitives directory; intended host for this control
- `frontend/src/components/ui/tables/TableActions.tsx` — sibling table action cell component
- `frontend/src/components/ui/tables/TableFilters.tsx` — sibling filter bar component
- `frontend/src/components/ui/tables/SortableHeader.tsx` — sibling sortable column header component
- `frontend/src/components/features/providers/ModelBrowser/ModelTable.tsx` — current consumer of the `Pagination` component (`import { Pagination } from '../../../ui/tables/Pagination'`)

> Note: `usePagination` currently has no consumers in the codebase — it is available for server-side pagination use cases.
