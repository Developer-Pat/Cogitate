---
title: sessionService (llm)
type: atlas-service
path: frontend/src/services/domains/llm/sessionService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# sessionService (llm)

**Path**: `frontend/src/services/domains/llm/sessionService.ts`
**Type**: service (class + singleton, domain facade)

## Purpose
LLM-domain session service — session CRUD for chat (ISessionService interface). Smallest of the 4 session services.

## Exported API
```typescript
export class SessionService implements ISessionService {
  // session CRUD methods — exact signatures from source
}
export const sessionService = new SessionService()
```

## Endpoints
- `/api/v1/sessions`

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| apiClient | services/apiClient.ts | Requests |

## Usage Example
```tsx
import { ServiceFactory } from '../../services'
const svc = ServiceFactory.getSessionService()
```

## Data Flow / Notes
- Re-exported via ServiceFactory.getSessionService(); no direct non-facade consumers found

## Related
- services/index.ts — DI facade (getSessionService)
- domain/SessionService.ts (432L) — separate class-based variant
- domain/SessionsService.ts (391L) — Sessions-page variant
- sessionSyncService.ts (root) — sync variant

## Deprecation / Obsolete Notes
Wired via ServiceFactory only — no direct consumer imports found. Part of the 4-way session-service overlap (see roadmap note); consolidation candidate, not deprecated.