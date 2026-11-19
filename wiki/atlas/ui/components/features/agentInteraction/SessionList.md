---
title: SessionList
type: atlas-component
path: frontend/src/components/features/agentInteraction/SessionList.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# SessionList

**Path**: `frontend/src/components/features/agentInteraction/SessionList.tsx`
**Last Updated**: 2026-08-01

## Purpose
Side-panel session list — renders SessionListItem rows, supports bulk-delete mode with checkbox selection.

## Props Interface
```typescript
interface SessionListProps {
  sessions: ConversationSession[]
  currentSession: ConversationSession | null
  onSessionSelect: (session: ConversationSession) => Promise<void>
  onSessionDelete: (sessionId: string) => void
  onSessionRename?: (sessionId: string, newTitle: string) => void
  requireDeleteConfirm?: boolean
  isBulkDeleteMode?: boolean
  selectedSessions?: Set<string>
  onSessionToggleSelect?: (sessionId: string) => void
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| SessionListItem | Component (local) | Row rendering |
| ConversationSession | types/agentInteraction | Data shape |

## Usage Example
```tsx
<SessionList sessions={sessions} currentSession={current} onSessionSelect={select} onSessionDelete={del} />
```

## State Used
None — controlled via props.

## Related Components
- features/agentInteraction/SessionListItem.tsx — row component
- features/agentInteraction/SessionManager.tsx — owner panel