---
title: SessionListItem
type: atlas-component
path: frontend/src/components/features/agentInteraction/SessionListItem.tsx
confidence: high
updated: 2026-09-15
tags: [type/component, domain/atlas-ui]
---
# SessionListItem

**Path**: `frontend/src/components/features/agentInteraction/SessionListItem.tsx`
**Last Updated**: 2026-09-15

## Purpose
Single session row in the session list — active highlight, inline rename input, delete (with optional confirm), bulk-select checkbox, loading state.

## Props Interface
```typescript
interface SessionListItemProps {
  session: ConversationSession
  isActive: boolean
  isRenaming: boolean
  renameValue: string
  onSelect: () => void
  onDelete: () => void
  onRenameStart: () => void
  onRenameSave: () => void
  onRenameCancel: () => void
  onRenameChange: (value: string) => void
  requireDeleteConfirm?: boolean
  isLoading?: boolean
  isBulkDeleteMode?: boolean
  isSelected?: boolean
  onToggleSelect?: (id: string) => void
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| getTruncatedSessionTitle | utils/agentNameUtils | Title truncation — the display stays 28 chars |
| PortalTooltip | components/ui/PortalTooltip | The full title on hover. See the note below. |
| useNotificationStore | Store | Toasts |
| ConversationSession | types/agentInteraction | Data shape |

## Usage Example
```tsx
<SessionListItem session={s} isActive={s.id === current.id} isRenaming={renaming} renameValue={rv} onSelect={sel} onDelete={del} onRenameStart={rs} onRenameSave={rv} onRenameCancel={rc} onRenameChange={rc2} />
```

## State Used
- Renaming state controlled by parent (isRenaming/renameValue props)

## Related Components
- features/agentInteraction/SessionList.tsx — parent list
- features/agentInteraction/SessionActions.tsx — actions hosted on rows
## Notes

**The title tooltip is PortalTooltip, not a DaisyUI `data-tip`.** The panel's scroll
containers clip a DaisyUI `::before`, so the tip renders through a portal instead. The
display stays `getTruncatedSessionTitle` at 28 chars. Full reasoning:
[[dev-notes/frontend/tooltip-clipping|Tooltip clipping in scroll containers]].

**Deselect lives in the panel header**, not here and not in the composer's row — see
[[atlas/ui/components/features/agentInteraction/SessionManager]].

**The eye button's toast** shows the session's working title, agent, message count and
`updatedAt`, plus a link to the Sessions page. The count reads the API's `message_count`
(see [[atlas/ui/services/domain/SessionsService]]) — the `messages` array cannot serve it,
being empty by design in the titles-only list payload.
