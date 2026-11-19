---
title: TraceService
type: atlas-service
path: frontend/src/services/domain/TraceService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# TraceService

**Path**: `frontend/src/services/domain/TraceService.ts`
**Type**: service (object singleton)

## Purpose
Client-side tracing — record trace events (in-memory buffer) and reset; feeds debugging trace analysis.

## Exported API
```typescript
export const traceService = {
  trace(event: TraceEvent): void
  reset(): void
}
```

## Endpoints
- None (in-memory buffer)

## Dependencies
None (in-memory).

## Usage Example
```tsx
traceService.trace({ type: 'agent', action: 'selected', data: { agentId } })
```

## Data Flow / Notes
- Lightweight event buffer; TraceAnalysis reads it

## Related
- features/debugging/TraceAnalysis.tsx, DatabaseTools.tsx — consumers
- features/agentInteraction/SessionList.tsx — consumer
- hooks/useAgentInteraction.ts, useSessionManagement.ts, useAgentSelection.ts — consumers

## Deprecation / Obsolete Notes
Active (6 consumers). No deprecation markers. NOTE: many trace() calls are commented out in useAgentSelection (source shows commented traceService.trace blocks) — trace coverage may be partially disabled.