---
title: TitleService
type: atlas-service
path: frontend/src/services/domain/TitleService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# TitleService

**Path**: `frontend/src/services/domain/TitleService.ts`
**Type**: service (class + singleton)

## Purpose
Session title generation in the background — generates titles via LLM endpoint after messages, with store/notification integration.

## Exported API
```typescript
export class TitleService {
  generateTitleInBackground(...): Promise<void>
}
export const titleService = new TitleService()
```

## Endpoints
- `POST /api/v1/chat/generate-title`

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| apiClient | services/apiClient.ts | Requests |
| useCognitiveHubStore | stores/cognitiveHubStore.ts | Agent context |
| useNotificationStore | stores/notificationStore.ts | Notifications |
| currentSessionService | domain/CurrentSessionService.ts | Session context |

## Usage Example
```tsx
await titleService.generateTitleInBackground()
```

## Data Flow / Notes
- Fires in background after conversation activity; updates session title

## Related
- hooks/useAgentInteraction.ts — consumer
- domain/TitleGenerationService.ts — obsolete predecessor

## Deprecation / Obsolete Notes
Active (1 hook consumer). No deprecation markers.