---
title: Tools Table
type: atlas-component
path: frontend/src/components/Tools/ToolsTable.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# Tools Table

**Path**: `frontend/src/components/Tools/ToolsTable.tsx`
**Last Updated**: 2026-08-01

## Purpose

`ToolsTable` is the main data table for the Tool Management page. It renders the list of tools as a sortable, filterable, paginated table with row-level selection, bulk actions, and per-row duplicate/delete actions. It is a **default export** and is **fully controlled from the outside for selection state** (selected IDs live in the parent via `selectedToolIds` / `onSelectionChange`), while all filter/sort/pagination UI state is managed internally with `useState`.

Composition pipeline inside the component (all memoized with `useMemo`):

1. **Filter + sort** — `filteredAndSortedTools` applies search query (name/description), type filter, tag filter (AND semantics), status filter (`all`/`active`/`inactive`), then sorts by `name`/`type`/`status` in `asc`/`desc` order.
2. **Paginate** — `paginatedTools` slices the filtered/sorted result by `currentPage` and `pageSize` (default 25).

Selection semantics:

- Row checkbox toggles a single tool ID in the parent-owned `Set`.
- Header checkbox selects/deselects all rows on the **current page** (select-all only spans `paginatedTools`).
- When any rows are selected, a `ToolsTableBulkActions` bar appears with a bulk delete (fires `onDelete` per selected ID via `Promise.all`, then clears selection) and a clear-selection button.
- Row actions (duplicate/delete) are delegated through `onDuplicate(tool)` and `onDelete(toolId)` props and rendered by the per-row `ToolsTableActions` component.

## Props Interface

```typescript
interface ToolsTableProps {
  tools: Tool[]
  selectedToolIds?: Set<string>
  onSelectionChange?: (selectedIds: Set<string>) => void
  onDuplicate: (tool: Tool) => void
  onDelete: (toolId: string) => Promise<void>
  isLoading?: boolean
}

export type SortColumn = 'name' | 'type' | 'status'
export type SortDirection = 'asc' | 'desc'
```

- `tools` — full list of tools to display (filtering/sorting/pagination happen client-side).
- `selectedToolIds` — **controlled** selection set; defaults to `new Set()`. Mutations are always reported back up via `onSelectionChange`, never held internally.
- `onSelectionChange` — optional; called with a new `Set<string>` on any selection change (row toggle, select-all, bulk delete, clear).
- `onDuplicate` — required; invoked with the tool object when a row's duplicate action is clicked.
- `onDelete` — required; async per-tool deletion. Used both by row-level delete and by bulk delete (`Promise.all` over all selected IDs).
- `isLoading` — optional; forwarded to `ToolsTableRow` (disables row actions while true). Defaults to `false`.

`SortColumn` and `SortDirection` are exported (and re-exported from `components/Tools/index.ts`) and consumed by `ToolsTableHeader` and `ToolsTableRow`.

The `Tool` type comes from `frontend/src/types/tools.ts` (fields used by this table: `id`, `name`, `description`, `type`, `tags: string[] | null`, `is_active`).

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `useState` (react) | Hook | Holds the internal `ToolsTableState` (sort, filters, pagination) |
| `useMemo` (react) | Hook | Derives unique `types` for the filter dropdown, `filteredAndSortedTools`, and `paginatedTools` |
| `Tool` (`../../types/tools`) | Type import | Row data shape from `frontend/src/types/tools.ts` |
| `ToolsTableFilters` (`./ToolsTableFilters`) | Child component | Search input + type/tag/status filter controls |
| `ToolsTableHeader` (`./ToolsTableHeader`) | Child component | Select-all checkbox + sortable Name/Type/Status column headers |
| `ToolsTableRow` (`./ToolsTableRow`) | Child component | One row per tool: checkbox, name/desc/tags, type, status, permissions, actions |
| `ToolsTablePagination` (`./ToolsTablePagination`) | Child component | Page navigation + page-size selector |
| `ToolsTableBulkActions` (`./ToolsTableBulkActions`) | Child component | Bulk-delete bar rendered only when `selectedToolIds.size > 0` |

## Usage Example

Modeled on the real consumer `frontend/src/pages/ToolManagement.tsx`:

```tsx
import { useState } from 'react'
import ToolsTable from '../components/Tools/ToolsTable'
import type { Tool } from '../types/tools'

function ToolManagement() {
  const [tools, setTools] = useState<Tool[]>([])
  const [selectedToolIds, setSelectedToolIds] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(false)

  const handleDuplicate = async (tool: Tool) => {
    // POST /tools/{id}/duplicate ...
  }

  const handleDelete = async (toolId: string) => {
    // DELETE /tools/{toolId} ...
  }

  return (
    <ToolsTable
      tools={tools}
      selectedToolIds={selectedToolIds}
      onSelectionChange={setSelectedToolIds}
      onDuplicate={handleDuplicate}
      onDelete={handleDelete}
      isLoading={loading}
    />
  )
}
```

## State Used

Internal (via `useState<ToolsTableState>`, initialized from `DEFAULT_STATE`):

```typescript
interface ToolsTableState {
  sortColumn: SortColumn        // 'name' (default) | 'type' | 'status'
  sortDirection: SortDirection  // 'asc' (default) | 'desc'
  searchQuery: string           // '' — matches name or description (case-insensitive)
  typeFilter: string[]          // [] — multi-select, OR semantics
  tagFilter: string[]           // [] — multi-select, AND semantics (every tag must match)
  statusFilter: 'all' | 'active' | 'inactive'  // 'all' (default); active ⇔ is_active
  currentPage: number           // 1 (default)
  pageSize: number              // 25 (default)
}
```

Notes:

- Any change to search/filters resets `currentPage` to 1; sorting and page-size changes also reset to page 1.
- **Selection is NOT local state** — it is controlled by the `selectedToolIds` prop and lifted to the parent via `onSelectionChange`. The internal state object only covers sort/filter/pagination.
- `ToolsTableRow` maintains its own tiny local state (`showActions` hover flag) — not part of this component's state.
- Empty states: "No tools yet" when `tools` is empty, "No tools match your filters" when filtering produces zero rows (empty row uses `colSpan={5}`).

## Related Components

| Component | Path |
|---|---|
| `ToolsTableFilters` | `frontend/src/components/Tools/ToolsTableFilters.tsx` |
| `ToolsTableHeader` | `frontend/src/components/Tools/ToolsTableHeader.tsx` |
| `ToolsTableRow` | `frontend/src/components/Tools/ToolsTableRow.tsx` |
| `ToolsTablePagination` | `frontend/src/components/Tools/ToolsTablePagination.tsx` |
| `ToolsTableBulkActions` | `frontend/src/components/Tools/ToolsTableBulkActions.tsx` |
| `ToolsTableActions` (row duplicate/delete menu) | `frontend/src/components/Tools/ToolsTableActions.tsx` |
| `PermissionBadge` / `TagBadge` (rendered inside rows) | `frontend/src/components/Tools/PermissionBadge.tsx`, `frontend/src/components/Tools/TagBadge.tsx` |
| `Tool` / `ToolResponse` types | `frontend/src/types/tools.ts` |
| Barrel re-exports (`ToolsTable`, `SortColumn`, `SortDirection`) | `frontend/src/components/Tools/index.ts` |
| Consumer: Tool Management page | `frontend/src/pages/ToolManagement.tsx` |
