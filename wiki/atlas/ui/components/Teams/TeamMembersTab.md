---
title: TeamMembersTab
type: atlas-component
path: frontend/src/components/Teams/TeamMembersTab.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---

# TeamMembersTab

**Path**: `frontend/src/components/Teams/TeamMembersTab.tsx`
**Last Updated**: 2026-08-01

## Purpose

Tab panel that displays the members (agents) of a team and manages membership. It renders a zebra-striped table of current members with their `entity_name` and the date they were added, plus a "Remove" action per row. An "Add Member" button opens a modal that loads all available agents (via `AgentService.getAgents()`), filters out agents already in the team, lets the user search and select one, then calls `onAddMember`. When the team has no members, it renders an empty state with a large 👥 icon and an "Add Members" CTA button. Actual membership mutations are delegated to the `onAddMember` / `onRemoveMember` callbacks supplied by the parent (`TeamDetail`); the component itself only fetches the candidate agent list. All load/add failures surface as error notifications via the notification store and are logged through `frontendLoggingService`.

## Props Interface

```typescript
interface TeamMembersTabProps {
  team: Team
  onAddMember: (agentId: string, agentName: string) => Promise<void>
  onRemoveMember: (memberId: string) => Promise<void>
}
```

- `team` — the team being edited; `team.members` is a `CollectionItem[]` (from `types/collections.ts`) whose items expose `id`, `entity_id`, `entity_name`, and `added_at` (used at lines 40, 136–140).
- `onAddMember` — async callback invoked with the selected agent's id and name when the user confirms adding a member; the component resets the modal state only after it resolves.
- `onRemoveMember` — async callback invoked with the member's `id` when the user clicks "Remove" on a table row.

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `React` / `useState` | hook | Local UI state: modal visibility (`isAddingMember`), agent list loading (`isLoadingAgents`), fetched candidates (`availableAgents`), selection (`selectedAgentId`), search filter (`searchQuery`). |
| `Team` (from `../../types/team_tools`) | type | Prop type; `Team extends Collection` and carries `members: CollectionItem[]`. |
| `Agent` (from `../../types/agentInteraction`) | type | Shape of candidate agents loaded from `AgentService` (`id`, `name`, `description`, `provider`, `model`, etc.). |
| `AgentService` (from `../../services/domain/AgentService`) | service class | `new AgentService().getAgents()` fetches all available agents (backend profiles via `ProfileService.loadFromBackend()`, cached per instance); results are filtered to exclude agents already in `team.members`. |
| `useNotificationStore` (from `../../stores/notificationStore`) | zustand store hook | `addNotification({ type, title, message, duration })` surfaces "Failed to Load Agents" / "Failed to Add Member" error toasts. |
| `frontendLoggingService` (from `../../services/frontendLoggingService`) | service | Logs `info` on successful agent load and `error` on load/add failures. |

## Usage Example

```tsx
import { TeamMembersTab } from '@/components/Teams/TeamMembersTab'
import type { Team } from '@/types/team_tools'

// Inside TeamDetail.tsx (activeTab === 'members')
<TeamMembersTab
  team={team}
  onAddMember={async (agentId, agentName) => {
    await teamService.addMember(team.id, agentId) // parent-owned mutation
  }}
  onRemoveMember={async (memberId) => {
    await teamService.removeMember(team.id, memberId) // parent-owned mutation
  }}
/>
```

## State Used

All state is local (`useState`); the component holds no global store state beyond reading the notification store:

- `isAddingMember` (`boolean`) — toggles the "Add Team Member" modal; reset to `false` on cancel, backdrop click, successful add, or agent-load failure.
- `isLoadingAgents` (`boolean`) — shows a spinner in the modal while `getAgents()` is in flight.
- `availableAgents` (`Agent[]`) — candidate agents fetched on modal open, minus agents already in `team.members` (compared via `member.entity_id` vs `String(a.id)`).
- `selectedAgentId` (`string`) — the agent selected in the dropdown; cleared when the search query changes, on cancel, or after a successful add. The confirm button is `disabled` while empty.
- `searchQuery` (`string`) — filters `availableAgents` by name (case-insensitive `includes`); the label shows a "({filtered} of {total})" count and a "No agents match" hint appears when the filter yields nothing.

## API Calls

- `AgentService.getAgents()` — the only call the component makes directly; happens inside `handleShowAddMember` when the modal opens. It loads agent profiles from the backend (through `ProfileService.loadFromBackend()`), returns cached results on repeat calls within the same service instance, and is wrapped in try/catch/finally that resets loading state.
- `onAddMember(agentId, agentName)` / `onRemoveMember(memberId)` — membership mutations are delegated to these props; the parent (`TeamDetail.tsx`) performs the actual backend calls (e.g. team membership add/remove endpoints). Errors thrown by `onAddMember` are caught and surfaced as notifications.

## Related Components

- `frontend/src/pages/TeamDetail.tsx` — parent page that owns `team` state and provides `onAddMember` / `onRemoveMember`; renders `TeamMembersTab` when the "Members" tab is active.
- `frontend/src/components/Teams/TeamToolsTab.tsx` — sibling tab in `TeamDetail` managing team tool/toolbox assignments.
- `frontend/src/components/Teams/TeamsTable.tsx` — team list table that navigates to `TeamDetail`.
- `frontend/src/services/domain/AgentService.ts` — service that supplies the candidate agent list.
- `frontend/src/types/team_tools.ts` / `frontend/src/types/collections.ts` — `Team`, `TeamTool`, `Collection`, and `CollectionItem` types.
