---
title: useSyncSchedule
type: atlas-hook
path: frontend/src/hooks/useSyncSchedule.ts
confidence: high
updated: 2026-08-01
tags: [type/hook, domain/atlas-ui]
---
# useSyncSchedule

**Path**: `frontend/src/hooks/useSyncSchedule.ts`
**Type**: hook

## Purpose
Model-sync scheduling — get/set/disable the sync schedule, trigger manual sync, poll sync status.

## Exported API
```typescript
export const useSyncSchedule = () => ({
  schedule, syncStatus, loading, error,
  setSchedule, disableSchedule, runSync, getSyncStatus,
})
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| schedulerService | domains/providers/schedulerService.ts | Schedule CRUD + sync trigger |

## Usage Example
```tsx
const { schedule, setSchedule, runSync, syncStatus } = useSyncSchedule()
```

## State / Data Flow
- schedule config; runSync triggers a sync; syncStatus reflects running state

## Related
- features/providers/ModelSyncScheduler.tsx — primary consumer