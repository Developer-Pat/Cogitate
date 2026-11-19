---
title: healthService (system)
type: atlas-service
path: frontend/src/services/domains/system/healthService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# healthService (system)

**Path**: `frontend/src/services/domains/system/healthService.ts`
**Type**: service (object singleton)

## Purpose
System health + info endpoints — system status, info, metrics, health check.

## Exported API
```typescript
export const healthService = {
  getSystemHealth(), getServiceStatus(), getSystemMetrics(),
  getSystemStatus(), getSystemInfo(), checkHealth(),
}
```

## Endpoints
- `/api/v1/health`, `/api/v1/system` (+ sub-resources)

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| apiClient | services/apiClient.ts | Requests |

## Usage Example
```tsx
const status = await healthService.getSystemStatus()
```

## Data Flow / Notes
- Backs useSystemHealth + useSystemInfo hooks

## Related
- hooks/useSystemHealth.ts, useSystemInfo.ts — consumers
- Dashboard/SystemInfo pages — indirect

## Deprecation / Obsolete Notes
Active (2 hook consumers). No deprecation markers.