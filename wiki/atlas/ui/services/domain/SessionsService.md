---
title: SessionsService
type: atlas-service
path: frontend/src/services/domain/SessionsService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# SessionsService

**Path**: `frontend/src/services/domain/SessionsService.ts`
**Type**: service (class + singleton)

## Purpose
Sessions page data — get sessions list, single session, current session, subscription, backend load. Client-cached.

## Exported API
```typescript
export class SessionsService {
  getSessions(): Promise<Session[]>
  getSession(id): Promise<Session>
  getCurrentSession(),
  subscribe(cb), loadFromBackend(),
}
export const sessionsService = new SessionsService()
```

## Endpoints
- Backend sessions endpoints (trace exact paths; sessionSyncService shares /api/v1/sessions)

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| apiClient | services/apiClient.ts | Requests |
| Session types | types | Data shapes |

## Usage Example
```tsx
const sessions = await sessionsService.getSessions()
```

## Data Flow / Notes
- Loads from backend with cache; subscribe for updates

## Related
- components/sessions/SessionFilters.tsx — consumer
- pages/Sessions.tsx — consumer
- hooks/useAgentInteraction.ts — consumer

## Deprecation / Obsolete Notes
Active (3 consumers). No deprecation markers.