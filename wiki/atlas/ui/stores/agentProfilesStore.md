---
title: agentProfilesStore
type: atlas-store
path: frontend/src/stores/agentProfilesStore.ts
confidence: high
updated: 2026-08-01
tags: [type/store, domain/atlas-ui]
---
# agentProfilesStore

**Path**: `frontend/src/stores/agentProfilesStore.ts`
**Type**: store (Zustand)

## Purpose
Agent profiles list state for the AgentProfiles page — profiles, loading, error.

## State Shape
```typescript
interface AgentProfilesState {
  profiles: Profile[];
  loading: boolean;
  error: string | null;
}
```

## Actions
- Load profiles, refresh, clear (exact signatures from source)

## Selectors / Exports
```typescript
export const useAgentProfilesStore = create<AgentProfilesState>(...)
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| Profile types | types | Data shape |

## Usage Example
```tsx
const profiles = useAgentProfilesStore(s => s.profiles)
```

## Data Flow / Notes
- Page-scoped store

## Related
- pages/AgentProfiles.tsx — sole consumer

## Deprecation / Obsolete Notes
Active (1 page consumer). No deprecation markers.