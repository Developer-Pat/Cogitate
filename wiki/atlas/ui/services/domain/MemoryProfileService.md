---
title: MemoryProfileService
type: atlas-service
path: frontend/src/services/domain/MemoryProfileService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# MemoryProfileService

**Path**: `frontend/src/services/domain/MemoryProfileService.ts`
**Type**: service (class + singleton)

## Purpose
Memory profile CRUD — the memory-profiles dimension of cognitive profiles.

## Exported API
```typescript
export class MemoryProfileService {
  list(), get(profileId), create(data), update(profileId, data), delete(profileId),
}
export const memoryProfileService = new MemoryProfileService()
```

## Endpoints
- `/api/v1/memory-profiles` (CRUD)

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| apiClient | services/apiClient.ts | Requests |

## Usage Example
```tsx
const profiles = await memoryProfileService.list()
```

## Data Flow / Notes
- Parallel to CognitiveProfileService (memory dimension of profiles)

## Related
- features/cognitive/CognitiveProfilesTab.tsx — consumer
- features/cognitive/MemoryProfilesTab.tsx — consumer

## Deprecation / Obsolete Notes
Active (2 consumers). No deprecation markers.