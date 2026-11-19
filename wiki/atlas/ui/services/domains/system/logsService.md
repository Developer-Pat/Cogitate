---
title: logsService (system)
type: atlas-service
path: frontend/src/services/domains/system/logsService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# logsService (system)

**Path**: `frontend/src/services/domains/system/logsService.ts`
**Type**: service (object singleton)

## Purpose
System log stats — DB-backed log stats (snake_case fields). The domain variant, distinct from root logsService (file-based).

## Exported API
```typescript
export const logsService = {
  getLogs(filters, page, pageSize), getLogStats(), ...
}
```

## Endpoints
- `/api/v1/system/logs` (+ /stats)

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| apiClient | services/apiClient.ts | Requests |

## Usage Example
```tsx
import { logsService } from '../../services'
const stats = await logsService.getLogStats()
```

## Data Flow / Notes

## Related
- hooks/useLogs.ts, useSystemInfo.ts — consumers
- root services/logsService.ts — file-based sibling (different implementation)

## Deprecation / Obsolete Notes
Active (2 hook consumers). No deprecation markers.