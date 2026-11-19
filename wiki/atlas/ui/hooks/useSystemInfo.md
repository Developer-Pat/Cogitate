---
title: useSystemInfo
type: atlas-hook
path: frontend/src/hooks/useSystemInfo.ts
confidence: high
updated: 2026-08-01
tags: [type/hook, domain/atlas-ui]
---
# useSystemInfo

**Path**: `frontend/src/hooks/useSystemInfo.ts`
**Type**: hook (multi-export)

## Purpose
System info family — status (30s refetch), system info (5min refetch), recent events (10s refetch). React-Query backed.

## Exported API
```typescript
export function useSystemStatus()  // ['system-status'], 30s — healthService.getSystemStatus
export function useSystemInfo()    // ['system-info'], 5min — healthService.getSystemInfo
export function useRecentEvents()  // ['recent-events'], 10s — logsService.getLogs({}, 1, 10) → .logs ?? []
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| @tanstack/react-query | Library | useQuery |
| healthService | services (api.ts) | getSystemStatus/getSystemInfo |
| logsService | services (root logsService.ts) | getLogs for recent events |

## Usage Example
```tsx
const { data: status } = useSystemStatus()
const { data: info } = useSystemInfo()
```

## State / Data Flow
- React-Query cache with per-query refetch intervals (30s/5min/10s)

## Related
- pages/SystemInfo.tsx — primary consumer (Overview/Metrics tabs)
- pages/SystemHistory.tsx — recent events