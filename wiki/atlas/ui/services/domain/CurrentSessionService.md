---
title: CurrentSessionService
type: atlas-service
path: frontend/src/services/domain/CurrentSessionService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# CurrentSessionService

**Path**: `frontend/src/services/domain/CurrentSessionService.ts`
**Type**: service (class + singleton)

## Purpose
In-memory current-session/agent context holder — getters for session state, first/last messages, subscription for changes. No API endpoints.

## Exported API
```typescript
export class CurrentSessionService {
  getCurrentSession(), getCurrentAgent(),
  getFirstMessage(), getLastAssistantMessage(), getMessages(), getMessageCount(),
  setCurrentSession(session), setCurrentAgent(agent), setContext(ctx),
  subscribe(cb), clearContext(),
}
export const currentSessionService = new CurrentSessionService()
```

## Endpoints
- None (in-memory only)

## Dependencies
None (in-memory state).

## Usage Example
```tsx
currentSessionService.setCurrentSession(session)
const msg = currentSessionService.getLastAssistantMessage()
```

## Data Flow / Notes
- Client-side context store shared between hooks/components

## Related
- hooks/useAgentInteraction.ts — consumer
- features/agentInteraction/SessionManager.tsx — sets session

## Deprecation / Obsolete Notes
Active (1 hook consumer). No deprecation markers.