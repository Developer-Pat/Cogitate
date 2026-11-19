---
title: syncQueueStore
type: atlas-store
path: frontend/src/stores/syncQueueStore.ts
confidence: high
updated: 2026-08-01
tags: [type/store, domain/atlas-ui]
---
# syncQueueStore

**Path**: `frontend/src/stores/syncQueueStore.ts`
**Type**: store slice (Zustand StateCreator)

## Purpose
Sync queue slice — offline-queue state + actions, composed INTO cognitiveHubStore.

## State Shape
```typescript
export const createSyncQueueSlice: StateCreator<...> = (set, get, store) => ({
  // queue items + actions
})
```

## Actions
- Enqueue/dequeue/retry (exact signatures from source)

## Selectors / Exports
```typescript
export { createSyncQueueSlice }
export type { SyncQueueSlice }
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| offlineSyncQueue service | services | Retry processor (trace) |

## Usage Example
```tsx
// Used via cognitiveHubStore composition
```

## Data Flow / Notes
- Slice pattern composed into cognitiveHubStore; pairs with offlineSyncQueue service

## Related
- stores/cognitiveHubStore.ts — composite root
- services/offlineSyncQueue.ts — processor

## Deprecation / Obsolete Notes
Active (composed into cognitiveHubStore). No deprecation markers.