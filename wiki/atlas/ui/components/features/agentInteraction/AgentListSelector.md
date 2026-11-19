---
title: AgentListSelector
type: atlas-component
path: frontend/src/components/features/agentInteraction/AgentListSelector.tsx
confidence: high
updated: 2026-09-10
tags: [type/component, domain/atlas-ui]
---
# AgentListSelector

**Path**: `frontend/src/components/features/agentInteraction/AgentListSelector.tsx`
**Last Updated**: 2026-09-10

## Purpose
The team (collection) selector on the Agent Chat page — a dropdown
of collections that FILTERS the agent list. Includes the VIRTUAL
**All Agents** option (the `''` sentinel): an agent outside any
collection is directly selectable — no team membership required.
Each team row renders the collection's `icon` emoji **verbatim**
(`{collection.icon}`) beside its name and `item_count`.

## Props Interface
```typescript
interface AgentListSelectorProps {
  selectedListId: string | null
  onSelectList: (listId: string) => void  // '' = All Agents
  userKey?: string
}
```

## Behavior
- Auto-selects the default team on load (or the first team).
- **All Agents** is always the first option — the parent's filter
  treats `''`/null as NO filter (the full pool).
- The button shows the selected team's icon/name/count, or
  "All Agents" when nothing is pinned.

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| `collectionsService` (`../../../services/domain/CollectionsService`) | domain service | `listCollections({ entity_type: 'agent' })` — loads the teams |
| `Collection` (`../../../types/collections`) | type | Team model (`id`, `name`, `icon`, `item_count`) |
| `useNotificationStore` (`../../../stores/notificationStore`) | store | Error toast when the team list fails to load |

## Usage Example
```tsx
<AgentListSelector selectedListId={selectedTeamId} onSelectList={setSelectedTeamId} />
```

## State Used
Local `useState`: `teams`, `loading`, `isOpen`; `useRef`: `dropdownRef` (outside-click detection). The selected list id itself is controlled via the `selectedListId` prop.

## Related Components
- features/agentInteraction/AgentSelector.tsx — dropdown variant
- features/agentInteraction/SessionManager.tsx — side-panel layout sibling