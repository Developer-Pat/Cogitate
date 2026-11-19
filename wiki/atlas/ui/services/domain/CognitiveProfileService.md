---
title: CognitiveProfileService
type: atlas-service
path: frontend/src/services/domain/CognitiveProfileService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# CognitiveProfileService

**Path**: `frontend/src/services/domain/CognitiveProfileService.ts`
**Type**: service (class + singleton)

## Purpose
Cognitive profile CRUD — the capability-describing profiles (conversational, quick-response, research-std, etc.) attached to agents.

## Exported API
```typescript
export class CognitiveProfileService {
  list(): Promise<CognitiveProfile[]>
  get(profileId): Promise<CognitiveProfile>
  create(data): Promise<CognitiveProfile>
  update(profileId, data): Promise<CognitiveProfile>
  delete(profileId): Promise<void>
}
export const cognitiveProfileService = new CognitiveProfileService()
```

## Endpoints
- `/api/v1/cognitive-profiles` (CRUD)

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| apiClient | services/apiClient.ts | Requests |
| CognitiveProfile types | types | Data shapes |

## Usage Example
```tsx
const profiles = await cognitiveProfileService.list()
```

## Data Flow / Notes
- Profile part codes (ctx-exe-fmt-mem) / badges (CB/EX/MM/RF) defined in types

## Related
- features/cognitive/CognitiveProfileSelector.tsx — consumer (table picker)
- features/cognitive/CognitiveProfilesTab.tsx — consumer
- features/cognitive/PipelineConfigTab.tsx — consumer

## Deprecation / Obsolete Notes
Active service — 3 consumers. No deprecation markers.