---
title: logStoreInstance
type: atlas-service
path: frontend/src/services/logStoreInstance.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# logStoreInstance

**Path**: `frontend/src/services/logStoreInstance.ts`
**Type**: service (bootstrap store instance)

## Purpose
Global log store instance (globalLogStore) — bootstrap singleton shared between logsService and frontendLoggingService. Comment notes it exists because frontendLoggingService depends on logStoreInstance (circular-dep avoidance).

## Exported API
```typescript
export { globalLogStore }
```

## Endpoints
- None (in-memory store)

## Dependencies
None (bootstrap).

## Usage Example
```tsx
import { globalLogStore } from './logStoreInstance'
```

## Data Flow / Notes
- Bootstrapped early; both logging services read/write the same store

## Related
- services/logsService.ts — consumer (imports globalLogStore)
- services/frontendLoggingService.ts — consumer

## Deprecation / Obsolete Notes
Active (2 consumers) — core bootstrap wiring. No deprecation markers.