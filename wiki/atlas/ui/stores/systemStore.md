---
title: systemStore
type: atlas-store
path: frontend/src/stores/systemStore.ts
confidence: high
updated: 2026-08-01
tags: [type/store, domain/atlas-ui]
---
# systemStore

**Path**: `frontend/src/stores/systemStore.ts`
**Type**: store (Zustand, multi-export)

## Purpose
System state — health, active sessions, agent configurations + system actions.

## State Shape
```typescript
interface SystemState {
  health, activeSessions, agentConfigurations,
  // + actions
}
```

## Actions
- System actions (refresh health, sessions, configs) — exact from source

## Selectors / Exports
```typescript
export const useSystemStore = create<SystemState>(...)
export const useSystemHealth = () => useSystemStore(s => s.health)
export const useActiveSessions = () => useSystemStore(s => s.activeSessions)
export const useAgentConfigurations = () => useSystemStore(s => s.agentConfigurations)
export const useSystemActions = () => useSystemStore(s => s.actions)
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| healthService | services | Health data (trace) |

## Usage Example
```tsx
const health = useSystemHealth()
```

## Data Flow / Notes
- useSystemHealth hook + useAgents hook consume

## Related
- hooks/useSystemHealth.ts, useAgents.ts — consumers

## Deprecation / Obsolete Notes
Active (2 hook consumers). No deprecation markers.