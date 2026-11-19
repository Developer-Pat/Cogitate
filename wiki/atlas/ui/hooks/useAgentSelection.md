---
title: useAgentSelection
type: atlas-hook
path: frontend/src/hooks/useAgentSelection.ts
confidence: high
updated: 2026-08-01
tags: [type/hook, domain/atlas-ui]
---
# useAgentSelection

**Path**: `frontend/src/hooks/useAgentSelection.ts`
**Type**: hook

## Purpose
Agent loading + selection with persistence restore — fetches agents from backend, manages the selected agent (via cognitiveHubStore as single source of truth), restores prior selection from localStorage/cache, and refreshes the selected agent's model from backend in the background.

## Exported API
```typescript
interface UseAgentSelectionReturn {
  agents: Agent[]
  isLoadingAgents: boolean
  selectedAgent: Agent | null
  error: string | null
  selectAgent: (agent: Agent) => void
  reloadAgents: () => Promise<void>
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| AgentService | domain/AgentService.ts | getAgents/getAgent/clearCache/getSelectedAgent (useRef singleton) |
| useCognitiveHubStore | stores/cognitiveHubStore.ts | Shared agent state (agents, activeAgent, loading, error) |
| frontendLoggingService | services/frontendLoggingService.ts | Logging |

## Usage Example
```tsx
const { agents, selectedAgent, selectAgent, reloadAgents } = useAgentSelection()
```

## State / Data Flow
- Loads agents on mount; restore logic (one-time via initialSetupDoneRef):
  1. activeAgent already in store (validated against agents list) — keep
  2. persisted activeAgentId — restore if still exists
  3. AgentService.getSelectedAgent persistence — restore
  4. fallback — auto-select first agent
- selectAgent sets immediately for responsive UI, then background-refreshes from backend to avoid stale localStorage model (graceful fallback to cached)

## Related
- useAgentInteraction.ts — consumer
- stores/cognitiveHubStore.ts — shared state
- features/agentInteraction/AgentSelector.tsx / AgentListSelector.tsx — UI consumers