---
title: AddToolboxesModal
type: atlas-component
path: frontend/src/components/Teams/AddToolboxesModal.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# AddToolboxesModal

**Path**: `frontend/src/components/Teams/AddToolboxesModal.tsx`
**Last Updated**: 2026-08-01

## Purpose

Modal dialog for selecting and assigning toolboxes to a team. On mount it fetches the available toolbox collections (`entity_type: 'tool'`) via `collectionsService.listCollections`, filters out toolboxes already assigned to the team, and renders a searchable, checkbox-driven list. The user selects one or more toolboxes, optionally sets a priority (higher = precedence), and confirms — the modal then calls `onAssign(toolboxId, priority)` for each selected toolbox before closing itself.

## Props Interface

```typescript
interface AddToolboxesModalProps {
  team: Team
  onClose: () => void
  onAssign: (toolboxId: string, priority: number) => Promise<void>
}
```

- `team` — the team receiving toolboxes; `team.tools` is used to filter out already-assigned toolboxes (`source_type === 'toolbox'`).
- `onClose` — callback invoked when the user cancels, when the modal backdrop is clicked, or after a successful assign.
- `onAssign` — async callback invoked once per selected toolbox with its id and the chosen priority.

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `collectionsService` (`../../services/domain/CollectionsService`) | Domain service | Fetches the toolbox list via `listCollections({ entity_type: 'tool' })` |
| `Team` (`../../types/team_tools`) | Type | Prop type; `team.tools` drives the already-assigned filter |
| `Collection` (`../../types/collections`) | Type | Shape of each toolbox entry (`id`, `name`, `description`, `icon`, `item_count`) |
| `useState` / `useEffect` (`react`) | Hooks | Local UI state and toolbox list loading |

## Usage Example

```tsx
import { AddToolboxesModal } from '@/components/Teams/AddToolboxesModal'

const [showAddToolboxesModal, setShowAddToolboxesModal] = useState(false)

const handleAssignToolbox = async (toolboxId: string, priority: number) => {
  if (!team) return
  await teamToolService.assignToolboxToTeam(team.id, { toolbox_id: toolboxId, priority })
  await loadTeam()
  setShowAddToolboxesModal(false)
}

{showAddToolboxesModal && (
  <AddToolboxesModal
    team={team}
    onClose={() => setShowAddToolboxesModal(false)}
    onAssign={handleAssignToolbox}
  />
)}
```

## State Used

| State | Type | Purpose |
|---|---|---|
| `availableToolboxes` | `Collection[]` | Toolboxes fetched from the API, minus ones already on the team |
| `selectedToolboxes` | `Set<string>` | Ids of toolboxes checked by the user |
| `priority` | `number` | Priority applied to all selected toolboxes on assign |
| `searchQuery` | `string` | Text filter against toolbox `name` / `description` |
| `isLoading` | `boolean` | True while the toolbox list is being fetched (spinner shown) |
| `isAssigning` | `boolean` | True while assignments are in flight (disables the Assign button) |

Loading effect re-runs when `team.tools` changes, re-filtering the available list. Assign is a sequential loop over `selectedToolboxes`; the modal only closes after all assignments succeed.

## Related Components

- `frontend/src/pages/TeamDetail.tsx` — sole consumer; owns the `showAddToolboxesModal` flag and provides `onClose` / `onAssign` (wired to `teamToolService.assignToolboxToTeam`).
- `frontend/src/components/Teams/AddToolsModal.tsx` — sibling modal for directly assigning individual tools to a team.
- `frontend/src/services/domain/CollectionsService.ts` — service providing `listCollections`, used to load the toolbox list.
- `frontend/src/types/team_tools.ts` — defines `Team`, `TeamTool`, and `ToolboxAssignCreate` (the payload `assignToolboxToTeam` expects).
