---
title: AgentTableActions
type: atlas-component
path: frontend/src/components/AgentProfiles/AgentTableActions.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# AgentTableActions

**Path**: `frontend/src/components/AgentProfiles/AgentTableActions.tsx`
**Last Updated**: 2026-08-01

## Purpose
Renders the per-row actions dropdown (kebab menu) for an agent profile row in the agent table. The menu exposes "Add to Collection", "Manage Tools" (rendered only when the `onManageTools` prop is provided), "Duplicate", and "Delete" items. "Add to Collection" opens the shared AddToCollectionModal; "Duplicate" fires the row-level duplicate handler and is disabled while `isLoading`. Note: there is no "edit" action, and the "Delete" item is a static button with no `onClick` handler wired up. This component contains no confirm dialogs.

## Props Interface
```typescript
interface AgentTableActionsProps {
  profile: Profile
  onDuplicate: () => void
  isLoading: boolean
  onManageTools?: (agentId: string) => void
}
```
`Profile` is imported from `../../services/domain/ProfileService` (has `id`, `name`, `description`, `provider`, `model`, `system_prompt`, `tools`, `memory`, etc.).

## Dependencies
| Dependency | Type | Purpose |
| --- | --- | --- |
| `useState` (react) | Hook | Tracks dropdown hover state and `showAddToCollection` modal visibility |
| `Profile` (`../../services/domain/ProfileService`) | Type | Shape of the agent profile passed in; `profile.id` / `profile.name` feed the AddToCollectionModal |
| `useNotificationStore` (`../../stores/notificationStore`) | Store hook | `addNotification` fires a success toast ("Added to Collection") after a successful add |
| `AddToCollectionModal` (`../features/collections/AddToCollectionModal`) | Component | Modal rendered when `showAddToCollection` is true; receives `entityId`, `entityName`, `entityType="agent"`, `onClose`, `onAdded` |

## Usage Example
Rendered by AgentTableRow (see `frontend/src/components/AgentProfiles/AgentTableRow.tsx`):
```tsx
import AgentTableActions from './AgentTableActions'

<AgentTableActions
  profile={profile}
  onDuplicate={onDuplicate}
  isLoading={isLoading}
  onManageTools={onManageTools}
/>
```

## State Used
- `showActions` (local `useState(false)`) — hover state for the dropdown; only the setter is used (`const [, setShowActions] = useState(false)`), the value is discarded because the DaisyUI `dropdown`/`dropdown-content` CSS classes handle visibility.
- `showAddToCollection` (local `useState(false)`) — controls rendering of the AddToCollectionModal; set to `true` by the "Add to Collection" item, back to `false` by `onClose` or `handleAddedToCollections`.
- No global store state is read for rendering; the notification store's `addNotification` is only called in `handleAddedToCollections`.

## Related Components
- `frontend/src/components/AgentProfiles/AgentTableRow.tsx` — parent that renders AgentTableActions in the row's actions cell and supplies all props.
- `frontend/src/components/features/collections/AddToCollectionModal.tsx` — modal opened by the "Add to Collection" action (`entityType="agent"`); AgentTableActions is a confirmed consumer.
- `frontend/src/components/AgentProfiles/index.ts` — barrel export (`export { default as AgentTableActions } from './AgentTableActions'`).
