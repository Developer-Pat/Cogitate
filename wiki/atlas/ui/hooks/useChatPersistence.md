---
title: useChatPersistence
type: atlas-hook
path: frontend/src/hooks/useChatPersistence.ts
confidence: high
updated: 2026-08-01
tags: [type/hook, domain/atlas-ui]
---
# useChatPersistence

**Path**: `frontend/src/hooks/useChatPersistence.ts`
**Type**: hook

## Purpose
Chat state persistence to sessionStorage — restores the last selected agent + current session on mount; saves on change; can save/clear explicitly.

## Exported API
```typescript
interface UseChatPersistenceOptions {
  selectedAgentId: string | null
  currentSessionId: string | null
}

interface UseChatPersistenceReturn {
  isRestored: boolean
  restoredState: { selectedAgentId: string | null; currentSessionId: string | null }
  saveState: () => void
  clearState: () => void
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| restoreChatState, saveChatState | utils/chatStateStorage | sessionStorage read/write |
| clearChatState (dynamic import) | utils/chatStateStorage | Clears stored state (lazy import avoids circular dep) |

## Usage Example
```tsx
const { isRestored, restoredState } = useChatPersistence({ selectedAgentId, currentSessionId })
```

## State / Data Flow
- Restored once at mount (useState initializer); isRestored flips true after mount
- Auto-saves whenever either ID is non-null and changes
- clearState uses dynamic import to break a potential circular dependency

## Related
- useAgentInteraction.ts — consumer
- utils/chatStateStorage.ts — backing storage module