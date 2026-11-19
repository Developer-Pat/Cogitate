---
title: MetricsService
type: atlas-service
path: frontend/src/services/domain/MetricsService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# MetricsService

**Path**: `frontend/src/services/domain/MetricsService.ts`
**Type**: service (class)

## Purpose
Streaming metrics calculation — tokens/sec, stream metrics, formatting. Pure client-side math.

## Exported API
```typescript
export class MetricsService {
  calculateTokensPerSecond(tokens, elapsedMs): number
  calculateStreamMetrics(...): ...
  formatMetrics(...): ...
}
```

## Endpoints
- None (pure computation)

## Dependencies
None.

## Usage Example
```tsx
const metrics = new MetricsService().calculateTokensPerSecond(120, 8000)
```

## Data Flow / Notes
- Pure calculation helpers

## Related
- domain/StreamingService.ts — owns an instance
- domain/MessageService.ts — owns an instance

## Deprecation / Obsolete Notes
Active (used by StreamingService + MessageService). No deprecation markers.