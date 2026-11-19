---
title: offlineSyncQueue
type: atlas-service
path: frontend/src/services/offlineSyncQueue.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# offlineSyncQueue

**Path**: `frontend/src/services/offlineSyncQueue.ts`
**Type**: service (module with start/stop retry processor)

## Purpose
Offline sync queue — queues operations while offline and retries them via a processor (startRetryProcessor/stopRetryProcessor).

## Exported API
```typescript
export function startRetryProcessor(): void
export function stopRetryProcessor(): void
```

## Endpoints
- None direct (queued ops replay to their endpoints)

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| syncQueueStore | stores | Queue state (trace) |

## Usage Example
```tsx
import { startRetryProcessor } from '../services/offlineSyncQueue'
startRetryProcessor()
```

## Data Flow / Notes
- Provider-level lifecycle — started by CognitiveHubProvider

## Related
- providers/CognitiveHubProvider.tsx — consumer (start/stop)
- stores/syncQueueStore.ts — queue state

## Deprecation / Obsolete Notes
Active (1 provider consumer). No deprecation markers.