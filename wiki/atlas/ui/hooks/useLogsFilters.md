---
title: useLogsFilters
type: atlas-hook
path: frontend/src/hooks/useLogsFilters.ts
confidence: high
updated: 2026-08-01
tags: [type/hook, domain/atlas-ui]
---
# useLogsFilters

**Path**: `frontend/src/hooks/useLogsFilters.ts`
**Type**: hook

## Purpose
Client-side log filtering — level, search term, and source-type filters over a log list with memoized filtered output.

## Exported API
```typescript
export const useLogsFilters = (logs: LogEntry[]) => ({
  filters,
  filteredLogs,
  setSelectedLevel,
  setSearchTerm,
  setSourceType,
})
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| LogEntry | types | Log data shape |
| frontendLoggingService | services | Logging |

## Usage Example
```tsx
const { filteredLogs, setSelectedLevel, setSearchTerm } = useLogsFilters(allLogs)
```

## State / Data Flow
- useState for filters; useMemo for filteredLogs (level match, search includes, source type)

## Related
- pages/Logs.tsx — primary consumer
- components/logs/LogFilters.tsx — UI binding