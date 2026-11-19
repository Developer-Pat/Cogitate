---
title: AgentTable
type: atlas-component
path: frontend/src/components/AgentProfiles/AgentTable.tsx
confidence: high
updated: 2026-09-10
tags: [type/component, domain/atlas-ui]
---
# AgentTable

**Path**: `frontend/src/components/AgentProfiles/AgentTable.tsx`
**Last Updated**: 2026-09-10

## Purpose

`AgentTable` is the table view of the agent-profiles sidebar on the AgentProfiles page (the alternative list view is `ProfileList`; a view toggle in the header switches between the two). It renders the `profiles` it receives as a sortable, filterable, paginated data table with per-row checkbox selection, a bulk-actions bar, a team filter dropdown, and hover-revealed per-row actions (duplicate, manage tools, add to collection). The component occupies a fixed-width right sidebar (`w-[600px]`) in the page's master-detail layout.

All data processing is **client-side**: the component receives the full `profiles` array and derives the provider list, the filtered/sorted rows, and the current page via `useMemo`. It makes no direct API calls — every mutation (`onSelectProfile`, `onDuplicate`, `onDelete`, `onManageTools`) is delegated to the parent page, and the team filter is parent-owned (`onTeamChange`). `AgentTable` is exported from the `components/AgentProfiles` barrel (`index.ts`) and rendered by `pages/AgentProfiles.tsx` when `viewMode === 'table'`.

> Note: the `Profile` type carries a `cognitive_profile_id` field, but the table does **not** display a cognitive-profile column — the six columns are checkbox, Name, Provider, Model, Status, Actions.

## Props Interface

```typescript
interface AgentTableProps {
  profiles: Profile[]
  selectedProfileId?: string
  onSelectProfile: (profile: Profile) => void
  onDuplicate: (profile: Profile) => void
  onDelete: (profileId: string) => Promise<Record<string, unknown> | null>
  isLoading?: boolean
  onViewModeChange?: (mode: 'list' | 'table') => void
  onManageTools?: (agentId: string) => void
  // Team filtering props
  teams?: Collection[]
  selectedTeamId?: string | 'all'
  onTeamChange?: (teamId: string | 'all') => void
  loadingTeams?: boolean
  totalProfiles?: number
}

export type SortColumn = 'name' | 'provider' | 'model' | 'status'
export type SortDirection = 'asc' | 'desc'
```

Defaults applied on destructure: `isLoading = false`, `teams = []`, `selectedTeamId = 'all'`, `loadingTeams = false`, `totalProfiles = 0`. `SortColumn` / `SortDirection` are exported from this module and re-imported by the sibling `AgentTableHeader` (`import type { SortColumn, SortDirection } from './AgentTable'`).

Prop-driven behavior:

- `onViewModeChange` — when provided, the header renders the list/table toggle; the table (active) button is `disabled`. Calling it with `'list'` switches the sidebar to `ProfileList`.
- `onTeamChange` — when provided, the "Filter by Team" select is rendered; the select is disabled while `loadingTeams`.
- `onManageTools` — passed down to the row actions; the "Manage Tools" menu item renders only when it is defined.
- `selectedProfileId` — drives row highlighting (`bg-primary/10` via `isRowSelected`); distinct from checkbox selection.

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `Profile` (from `services/domain/ProfileService.ts`) | type | Row data model — `name`, `description`, `provider`, `model`, `image_url` |
| `Collection` (from `types/collections.ts`) | type | Team-filter option model — `id`, `name`, `items[]` |
| `AgentTableHeader` (`./AgentTableHeader`) | child | Sortable column headers + select-all checkbox |
| `AgentTableRow` (`./AgentTableRow`) | child | One row: checkbox, name + description, provider badge, model, status badge, actions |
| `AgentTableFilters` (`./AgentTableFilters`) | child | Search input, provider multi-select, status toggle group, clear filters |
| `AgentTablePagination` (`./AgentTablePagination`) | child | Page-size select, windowed page numbers, prev/next |
| `AgentTableBulkActions` (`./AgentTableBulkActions`) | child | "N agents selected" bar with bulk delete (native `confirm()`) |
| `AgentTableActions` (`./AgentTableActions`, rendered by `AgentTableRow`) | grandchild | Per-row dropdown: Add to Collection, Manage Tools, Duplicate, Delete |
| `pages/AgentProfiles.tsx` | parent | Supplies all props; owns stores and services (see API Endpoints) |
| `stores/agentProfilesStore.ts` (Zustand) | store, via parent | Backs `viewMode`, `selectedTeamId`, `selectedProfileId` props |
| React `useState` / `useMemo` | framework | Local table state + derived rows |

The component imports no service and no store directly — it is fully controlled via props. The page feeds it `profiles` from `profileService.loadFromBackend()` + `subscribe(setProfiles)` (60-second background sync) and teams from `teamToolService.listTeams()`.

## Usage Example

Verbatim from `pages/AgentProfiles.tsx` (rendered when `viewMode === 'table'`):

```tsx
<AgentTable
  profiles={filteredProfiles}
  selectedProfileId={selectedProfile?.id}
  onSelectProfile={handleSelectProfile}
  onDuplicate={handleDuplicateProfile}
  onDelete={handleDeleteProfile}
  isLoading={loading || isSaving}
  onViewModeChange={setViewMode}
  onManageTools={handleManageTools}
  teams={teams}
  selectedTeamId={selectedTeamId}
  onTeamChange={setSelectedTeamId}
  loadingTeams={loadingTeams}
  totalProfiles={profiles.length}
/>
```

## State Used

Single local state object (`useState<AgentTableState>`, initialized from `DEFAULT_STATE`):

```typescript
interface AgentTableState {
  sortColumn: SortColumn        // default 'name'
  sortDirection: SortDirection  // default 'asc'
  searchQuery: string           // default ''
  providerFilter: string[]      // default []
  statusFilter: 'all' | 'active' | 'inactive'  // default 'all'
  currentPage: number           // default 1
  pageSize: number              // default 25
  selectedAgentIds: Set<string> // default empty Set
}
```

Memoized derivations (`useMemo`):

- `providers` — unique, sorted provider names for the filter dropdown.
- `filteredAndSortedProfiles` — pipeline: search (case-insensitive substring on name/description) → provider filter → status filter → sort. Search, provider, and status changes all reset `currentPage` to 1.
- `paginatedProfiles` — slice of the filtered/sorted array for the current page.

External state: none read directly — `viewMode`, `selectedTeamId`, `selectedProfileId` arrive as props but live in the Zustand `agentProfilesStore` at the parent.

## Data Flow — Filtering, Sorting, Pagination, Selection

1. **Filtering** — `AgentTableFilters` reports changes via `onSearch` / `onProviderFilter` / `onStatusFilter`; each handler updates state and resets `currentPage` to 1. The status filter is partial: `'active'` is a no-op (every profile is treated as active), `'inactive'` yields an empty list — the `Profile` type has no status field, so this is future wiring, not live data.
2. **Sorting** — `AgentTableHeader` calls `onSort(column)`; `handleSort` toggles asc → desc when the same column is re-clicked. Sorting compares lowercased `name` / `provider` / `model`; the `status` column is sortable but compares `'active'` vs `'active'` (a no-op, per source comment).
3. **Pagination** — `AgentTablePagination` renders nothing when `totalItems === 0`; otherwise a page-size select (10/25/50/100), a max-5 window of page numbers with `...` ellipses, prev/next buttons, and a "Showing X to Y" readout. Page-size changes reset to page 1.
4. **Selection** — row checkboxes toggle ids in `selectedAgentIds`. Select-all (`handleSelectAll`) selects only the **current page**'s rows, or deselects everything when all are already selected. When the set is non-empty, `AgentTableBulkActions` appears; bulk delete maps `onDelete` over every selected id with `Promise.all` (parallel deletes) after a native `confirm()`, then clears the selection. Two selection concepts coexist: checkbox `isSelected` (bulk ops) vs `isRowSelected` (`selectedProfileId` — highlights the row and opens the detail pane via `onSelectProfile`).
5. **Team filter** — parent-owned: `onTeamChange` writes `selectedTeamId` to the store; the parent pre-filters `filteredProfiles` by `team.items[].entity_id` before passing them in. The dropdown label shows per-team agent counts (`team.items?.length`) and an "All Agents (totalProfiles)" option.

Empty states: "No agents yet" when `profiles` is empty, otherwise "No agents match your filters" (rendered in a `colSpan={6}` row matching the six columns).

> ⚠️ **Dead control found while documenting**: the row-level "Delete" item in `AgentTableActions` has no `onClick` handler (it does not receive an `onDelete` prop at all) — only the bulk-delete path actually deletes. Backlog candidate: wire it to `onDelete(profile.id)` or remove it.

## API Endpoints

`AgentTable` makes **no direct network calls**; it is presentational with delegated mutations. Its callbacks resolve through the parent page into `ProfileService` (`basePath '/api/v1/agents'`, 60-second background sync):

- `onDelete(id)` → `handleDeleteProfile` → `profileService.deleteProfile(profileId)`
- `onDuplicate(profile)` → `handleDuplicateProfile` → `profileService.duplicateAgent(profile.id)`
- `onSelectProfile(profile)` → `handleSelectProfile` → `selectProfile(profile.id, 'edit')` (store only, no network)
- `onManageTools(agentId)` → opens the `AgentToolManager` modal (parent local state)
- Team options → parent's `teamToolService.listTeams()`; profiles → parent's `profileService.loadFromBackend()` + `subscribe(setProfiles)`

## Related Components

- Parent: `frontend/src/pages/AgentProfiles.tsx` (renders `AgentTable` when `viewMode === 'table'`)
- List-view sibling: `frontend/src/components/AgentProfiles/ProfileList.tsx`
- Children: `frontend/src/components/AgentProfiles/AgentTableHeader.tsx`, `AgentTableRow.tsx`, `AgentTableFilters.tsx`, `AgentTablePagination.tsx`, `AgentTableBulkActions.tsx`
- Grandchild: `frontend/src/components/AgentProfiles/AgentTableActions.tsx` (rendered by `AgentTableRow`)
- Store: `frontend/src/stores/agentProfilesStore.ts` (via parent props)
- Service: `frontend/src/services/domain/ProfileService.ts` (via parent)
