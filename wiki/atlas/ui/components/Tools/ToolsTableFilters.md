---
title: ToolsTableFilters
type: atlas-component
path: frontend/src/components/Tools/ToolsTableFilters.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# ToolsTableFilters

**Path**: `frontend/src/components/Tools/ToolsTableFilters.tsx`
**Last Updated**: 2026-08-01

## Purpose

Controlled filter bar for the Tools table. Renders four filter controls — a free-text search input, a multi-select Type dropdown, a multi-select Tag dropdown (populated from the canonical `KNOWN_TAGS` list), and a segmented All / Active / Inactive status control — plus a conditional "Clear filters" button and a row of active tag chips. The component is fully controlled: it holds no state of its own, and every user interaction is lifted to the parent via `onSearch` / `onTypeFilter` / `onTagFilter` / `onStatusFilter` callbacks. The parent (`ToolsTable`) owns all filter state and applies the filters in its `filteredAndSortedTools` memo. This component makes no API or network calls.

## Props Interface

Verbatim from source (lines 5–15):

```typescript
interface ToolsTableFiltersProps {
  searchQuery: string
  types: string[]
  typeFilter: string[]
  statusFilter: 'all' | 'active' | 'inactive'
  tagFilter: string[]
  onSearch: (query: string) => void
  onTypeFilter: (types: string[]) => void
  onStatusFilter: (status: 'all' | 'active' | 'inactive') => void
  onTagFilter: (tags: string[]) => void
}
```

| Prop | Type | Meaning |
|---|---|---|
| `searchQuery` | `string` | Current search text bound to the input's `value` |
| `types` | `string[]` | Distinct tool types available in the Type dropdown (derived by the parent; dropdown is hidden when empty) |
| `typeFilter` | `string[]` | Currently selected type filters (checked boxes) |
| `statusFilter` | `'all' \| 'active' \| 'inactive'` | Active segment of the status control |
| `tagFilter` | `string[]` | Currently selected tag filters |
| `onSearch` | `(query: string) => void` | Fired on every input keystroke with `e.target.value` |
| `onTypeFilter` | `(types: string[]) => void` | Fired with the new full array when a type box is toggled (add/remove) |
| `onStatusFilter` | `(status: 'all' \| 'active' \| 'inactive') => void` | Fired when All/Active/Inactive is clicked |
| `onTagFilter` | `(tags: string[]) => void` | Fired with the new full array when a tag box is toggled, a chip's × is clicked, or Clear filters runs |

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `TagBadge` (`frontend/src/components/Tools/TagBadge.tsx`) | child component | Renders each tag in the tag-filter dropdown checklist and in the active-tag chips row (invoked with `size="sm"` and `showTooltip={false}`) |
| `KNOWN_TAGS` (`frontend/src/types/toolTags.ts`) | constant | Canonical tag list (`op:*`, `purpose:*`, `source:*`, complexity, `format:*` tags) that populates the tag-filter dropdown |
| DaisyUI utility classes (`dropdown`, `menu`, `btn-group`, `checkbox`, `badge`, `input`) | CSS framework | Styling for the dropdowns, segmented status control, checkboxes, badges, and search input |

No hooks, stores, services, or state libraries are used — the component is pure presentational/controlled.

## Usage Example

Real usage from the parent `ToolsTable.tsx`:

```tsx
<ToolsTableFilters
  searchQuery={state.searchQuery}
  types={types}
  typeFilter={state.typeFilter}
  tagFilter={state.tagFilter}
  statusFilter={state.statusFilter}
  onSearch={handleSearch}
  onTypeFilter={handleTypeFilter}
  onTagFilter={handleTagFilter}
  onStatusFilter={handleStatusFilter}
/>
```

## State Used

No local state — fully controlled. All filter state lives in the parent's single `useState<ToolsTableState>` in `ToolsTable.tsx` (defaults: `searchQuery: ''`, `typeFilter: []`, `tagFilter: []`, `statusFilter: 'all'`). Internally derived value: `hasFilters` (true when `searchQuery` is non-empty, any filter array is non-empty, or `statusFilter !== 'all'`) — gates whether the "Clear filters" button renders.

## Filter Fields & onChange Contract

- **Search** — text input with placeholder "Search tools by name or description..."; `onChange` calls `onSearch(e.target.value)` on every keystroke (uncontrolled debouncing; parent filters on each render).
- **Type filter** — DaisyUI dropdown of checkboxes over the `types` prop; `handleTypeToggle` either removes the type from `typeFilter` or appends it, then calls `onTypeFilter` with the new array. Shows a count badge when non-empty. Hidden entirely when `types.length === 0`.
- **Tag filter** — dropdown of checkboxes over `KNOWN_TAGS` (with `TagBadge` labels); `handleTagToggle` same add/remove pattern via `onTagFilter`. Active tags are also rendered as removable chips below the bar (clicking a chip's × calls `handleTagToggle`).
- **Status filter** — three-segment button group (All / Active / Inactive) calling `onStatusFilter` with the matching literal.
- **Clear filters** — rendered only when `hasFilters`; calls `onSearch('')`, `onTypeFilter([])`, `onTagFilter([])`, `onStatusFilter('all')`.

Contract: one-way data flow. The component never mutates its props; each callback hands the complete new filter value to the parent, which updates its state and re-renders (parent handlers `handleSearch`, `handleTypeFilter`, `handleTagFilter`, `handleStatusFilter` all reset `currentPage` to 1). Filter *application* (matching against `Tool.name` / `Tool.description`, `Tool.type`, `Tool.tags`, `Tool.is_active`) happens in the parent's `filteredAndSortedTools` memo, not in this component.

## API Endpoints

None. `ToolsTableFilters` makes no direct network calls. Filtering is client-side within the parent `ToolsTable` over the `tools` prop it receives from the page.

## Related Components

- **Parent**: `ToolsTable` (`frontend/src/components/Tools/ToolsTable.tsx`) — owns all filter state and the filtering/sorting/pagination pipeline.
- **Sibling children of ToolsTable**: `ToolsTableHeader` (`frontend/src/components/Tools/ToolsTableHeader.tsx`), `ToolsTableRow` (`frontend/src/components/Tools/ToolsTableRow.tsx`), `ToolsTablePagination` (`frontend/src/components/Tools/ToolsTablePagination.tsx`), `ToolsTableBulkActions` (`frontend/src/components/Tools/ToolsTableBulkActions.tsx`).
- **Child**: `TagBadge` (`frontend/src/components/Tools/TagBadge.tsx`).
- **Barrel**: `frontend/src/components/Tools/index.ts` re-exports this component.
