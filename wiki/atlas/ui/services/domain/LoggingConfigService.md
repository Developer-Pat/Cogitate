---
title: LoggingConfigService
type: atlas-service
path: frontend/src/services/domain/LoggingConfigService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# LoggingConfigService

**Path**: `frontend/src/services/domain/LoggingConfigService.ts`
**Type**: service (object singleton, subscriber pattern)

## Purpose
Logging configuration singleton — get/update/reset config; shouldLog/deduplication/backend/tracing flags; subscriber notifications. In-memory (no API).

## Exported API
```typescript
export const loggingConfigService = {
  getConfig(), updateConfig(updates), reset(),
  shouldLog(level, source?), isDeduplicationEnabled(),
  isBackendLoggingEnabled(), isTracingEnabled(),
  // + subscribe mechanism
}
```

## Endpoints
- None (in-memory)

## Dependencies
None (in-memory state).

## Usage Example
```tsx
loggingConfigService.updateConfig({ tracingEnabled: true })
```

## Data Flow / Notes
- Subscriber pattern — panels poll getConfig() (LoggingConfigPanel 1s interval)

## Related
- components/settings/LoggingConfigPanel.tsx — consumer (1s poll)
- features/debugging/TraceControls.tsx — consumer

## Deprecation / Obsolete Notes
Active (2 consumers). No deprecation markers.