---
title: MessageService
type: atlas-service
path: frontend/src/services/domain/MessageService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# MessageService

**Path**: `frontend/src/services/domain/MessageService.ts`
**Type**: service (class)

## Purpose
Conversation message persistence — add/update/remove messages in sessions (client-side; feeds StreamingService).

## Exported API
```typescript
export class MessageService {
  addMessageToSession(sessionId, message): Promise<...>
  updateMessageInSession(sessionId, messageId, updates): Promise<...>
  removeMessageFromSession(sessionId, messageId): Promise<...>
}
```

## Endpoints
- None direct (in-memory/session store)

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| MetricsService | domain/MetricsService.ts | Stream metrics formatting |
| frontendLoggingService | services | Logging |

## Usage Example
```tsx
const svc = new MessageService()
await svc.addMessageToSession(sessionId, message)
```

## Data Flow / Notes
- Instantiated internally by StreamingService (not a singleton)

## Related
- domain/StreamingService.ts — owns an instance
- hooks/useAgentInteraction.ts — indirect consumer via streaming

## Deprecation / Obsolete Notes
Active (used by StreamingService). No direct UI consumers; instantiated as a class. No deprecation markers.