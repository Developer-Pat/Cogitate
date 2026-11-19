---
title: defaultProviderService
type: atlas-service
path: frontend/src/services/domains/providers/defaultProviderService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# defaultProviderService

**Path**: `frontend/src/services/domains/providers/defaultProviderService.ts`
**Type**: service (object singleton)

## Purpose
Default provider management — get/set/lazy-init the app default provider.

## Exported API
```typescript
export const defaultProviderService = {
  getDefaultProvider(), setDefaultProvider(providerId), initializeDefaultProvider(),
}
```

## Endpoints
- `/api/v1/providers` (default sub-resource)

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| apiClient | services/apiClient.ts | Requests |

## Usage Example
```tsx
await defaultProviderService.setDefaultProvider('ollama')
```

## Data Flow / Notes
- Backs useDefaultProvider hook

## Related
- hooks/useDefaultProvider.ts — consumer
- features/providers/DefaultProviderConfig.tsx — UI

## Deprecation / Obsolete Notes
Active (1 hook consumer). No deprecation markers.