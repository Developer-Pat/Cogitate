---
title: IdService
type: atlas-service
path: frontend/src/services/domain/IdService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# IdService

**Path**: `frontend/src/services/domain/IdService.ts`
**Type**: service (class, util)

## Purpose
ID generation/parsing utilities for the app's identifier conventions.

## Exported API
```typescript
export class IdService {
  // id generation/parsing helpers — see source for exact signatures
}
```

## Endpoints
- None

## Dependencies
None.

## Usage Example
```tsx
const id = IdService.generate()
```

## Data Flow / Notes
- Pure utility class

## Related
- features/agentInteraction/SessionManager.tsx — consumer
- hooks/useAgentInteraction.ts / useSessionManagement.ts — consumers
- providers/CognitiveHubProvider.tsx — consumer

## Deprecation / Obsolete Notes
Active (4 consumers). No deprecation markers.