---
title: useSystemHealth
type: atlas-hook
path: frontend/src/hooks/useSystemHealth.ts
confidence: high
updated: 2026-08-01
tags: [type/hook, domain/atlas-ui]
---
# useSystemHealth

**Path**: `frontend/src/hooks/useSystemHealth.ts`
**Type**: hook (multi-export)

## Purpose
System health family — health status, per-service status, metrics, uptime, and a manual health-check action. React-Query backed (60s refetch on service status).

## Exported API
```typescript
// useSystemHealth — ['system-health'] query, returns spread query + :
//   systemHealth, isHealthy (status==='healthy'), isDegraded, isUnhealthy

// useServiceStatus — ['service-status'] query, refetchInterval 60s
// useSystemMetrics — ['system-metrics'] query (healthService.getSystemMetrics)
// useUptime — ['uptime'] query (healthService.getSystemStatus)
// useHealthCheck — returns { checkHealth } (healthService.checkHealth, invalidates ['system-health'])
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| @tanstack/react-query | Library | useQuery/useQueryClient |
| healthService | services/index (api.ts) | getSystemHealth/getServiceStatus/getSystemMetrics/getSystemStatus/checkHealth |
| useSystemStore | stores/systemStore.ts | Health state sync |
| useNotificationStore | stores/notificationStore.ts | Health-check notifications |

## Usage Example
```tsx
const { systemHealth, isHealthy, refetch } = useSystemHealth()
const { checkHealth } = useHealthCheck()
```

## State / Data Flow
- React-Query caching with 60s refetch for service status; checkHealth invalidates the system-health key

## Related
- components/dashboard/QuickStats.tsx, SystemHealthCard.tsx — consumers
- components/ui/BackendStatusIndicator.tsx — header status