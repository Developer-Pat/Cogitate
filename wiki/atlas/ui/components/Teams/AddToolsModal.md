---
title: AddToolsModal
type: atlas-component
path: frontend/src/components/Teams/AddToolsModal.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# AddToolsModal

**Path**: `frontend/src/components/Teams/AddToolsModal.tsx`
**Last Updated**: 2026-08-01

## Purpose

DaisyUI modal for selecting and assigning tools to a team. Rendered conditionally by the Team detail page, it fetches the catalog of active tools via `ToolService.listTools`, filters out tools already assigned to the team, and lets the user search, multi-select (with Select All / Deselect All), set a shared priority for the batch, and assign every selected tool through the parent-supplied `onAssign` callback. The modal owns only local selection UI state — fetching the catalog and persisting assignments are delegated to the parent chain.

## Props Interface

```typescript
interface AddToolsModalProps {
  team: Team
  onClose: () => void
  onAssign: (toolId: string, priority: number) => Promise<void>
}
```

- `team` — the team being edited. `team.tools` (existing `TeamTool[]` assignments) drives both the already-assigned exclusion filter and the `useEffect` refetch dependency.
- `onClose` — called by Cancel, by a backdrop click, and after a successful assignment loop.
- `onAssign(toolId, priority)` — invoked once per selected tool, sequentially; the parent owns persistence (see Tool Assignment Flow).

Type notes: `Team` is declared in `frontend/src/types/team_tools.ts` as `interface Team extends Collection { members: CollectionItem[]; tools: TeamTool[] }` (with `TeamTool` in the same file), and `Tool` / `ToolListResponse` come from `frontend/src/types/tools.ts`.

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `ToolService` (`frontend/src/services/domain/ToolService.ts`) | domain service | `listTools({ is_active: true })` → `GET /api/v1/tools?is_active=true` (basePath `/api/v1/tools`), called on mount. The `is_active` filter bypasses the service's 5-minute tools cache. A fresh instance is constructed per effect run (`new ToolService()`). |
| `Team`, `TeamTool` (`frontend/src/types/team_tools.ts`) | types | Props typing; `team.tools[].tool_id` used to exclude already-assigned tools from the picker. |
| `Tool`, `ToolListResponse` (`frontend/src/types/tools.ts`) | types | Typed fetch result; `Tool.name` / `Tool.description` drive the search filter and `Tool.icon` renders when present. |
| `onAssign` → `TeamToolService.assignToolToTeam` (`frontend/src/services/domain/TeamToolService.ts`) | callback → parent service | Not called in this file — the parent `frontend/src/pages/TeamDetail.tsx` wires it to `POST /api/v1/teams/{teamId}/tools` with `{ tool_id, source_type: 'direct', priority, is_active: true, config: {} }`, then refreshes the team. |

## Usage Example

From the parent `frontend/src/pages/TeamDetail.tsx` (mounted conditionally on `showAddToolsModal`):

```tsx
{showAddToolsModal && (
  <AddToolsModal
    team={team}
    onClose={() => setShowAddToolsModal(false)}
    onAssign={handleAssignTool}
  />
)}
```

with the parent's persistence handler:

```tsx
const handleAssignTool = async (toolId: string, priority: number) => {
  if (!team) return
  try {
    await teamToolService.assignToolToTeam(team.id, {
      tool_id: toolId,
      source_type: 'direct',
      priority,
      is_active: true,
      config: {},
    })
    await loadTeam()
    setShowAddToolsModal(false)
  } catch (err) {
    console.error('Failed to assign tool:', err)
  }
}
```

## State Used

All local `useState` — no external store is consulted:

- `availableTools: Tool[]` — fetched catalog minus tools whose ids are already in `team.tools`.
- `selectedTools: Set<string>` — checked tool ids; toggled per-row or in bulk by Select All / Deselect All.
- `priority: number` — shared priority for every assignment (`parseInt(e.target.value) || 0`, `min={0}`).
- `searchQuery: string` — client-side filter on `tool.name` / `tool.description` (`toLowerCase().includes`).
- `isLoading: boolean` — spinner shown while the tool list is being fetched.
- `isAssigning: boolean` — disables the Assign button and shows an inline spinner during the assignment loop.

## Tool Assignment Flow

1. On mount (and whenever `team.tools` changes) `loadTools()` runs: `new ToolService().listTools({ is_active: true })`, then `setAvailableTools` drops ids already present in `team.tools`. Fetch failures are `console.error`'d and the list renders its "No tools available" empty state.
2. The user toggles checkboxes or Select All, sets Priority, and clicks "Assign N Tools" (disabled while 0 tools are selected or while assigning).
3. `handleAssign` iterates `selectedTools` and `await`s `onAssign(toolId, priority)` per tool (sequential), then calls `onClose()`. The parent's `handleAssignTool` persists via `assignToolToTeam` and also closes the modal on success; an assignment failure logs and leaves the modal open.
4. Cancel or backdrop click → `onClose()`.

## Related Components

- Parent: `frontend/src/pages/TeamDetail.tsx` — owns `showAddToolsModal` state and the `handleAssignTool` persistence callback.
- Sibling: `frontend/src/components/Teams/AddToolboxesModal.tsx` — the same modal pattern for assigning toolboxes, rendered alongside by TeamDetail.
- Related services: `frontend/src/services/domain/ToolService.ts` (tool catalog fetch) and `frontend/src/services/domain/TeamToolService.ts` (assignment persistence, invoked by the parent).
