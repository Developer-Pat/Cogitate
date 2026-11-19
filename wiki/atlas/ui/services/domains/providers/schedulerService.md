---
title: schedulerService
type: atlas-service
path: frontend/src/services/domains/providers/schedulerService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# schedulerService

**Path**: `frontend/src/services/domains/providers/schedulerService.ts`
**Type**: service (object singleton)

## Purpose
Model-sync scheduler — schedule CRUD, manual sync trigger, sync status.

## Exported API
```typescript
export const schedulerService = {
  getSchedule(), setSchedule(schedule), disableSchedule(),
  runSync(), getSyncStatus(),
}
```

## Endpoints
- `/api/v1/providers/sync-schedule`

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| apiClient | services/apiClient.ts | Requests |

## Usage Example
```tsx
await schedulerService.runSync()
```

## Data Flow / Notes
- Backs useSyncSchedule hook

## Related
- hooks/useSyncSchedule.ts — consumer
- features/providers/ModelSyncScheduler.tsx — UI

## Deprecation / Obsolete Notes
Active (1 hook consumer). No deprecation markers.