---
title: providerConfigService
type: atlas-service
path: frontend/src/services/domains/providers/providerConfigService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# providerConfigService

**Path**: `frontend/src/services/domains/providers/providerConfigService.ts`
**Type**: service (object singleton)

## Purpose
Provider configuration — CRUD provider configs, API keys, connection tests.

## Exported API
```typescript
export const providerConfigService = {
  getProviders(), createProvider(data), updateProvider(id, data), deleteProvider(id),
  setApiKey(providerId, key), testProvider(providerId),
}
```

## Endpoints
- `/api/v1/providers/config`

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| apiClient | services/apiClient.ts | Requests |

## Usage Example
```tsx
await providerConfigService.setApiKey('openai', key)
```

## Data Flow / Notes
- Backs useProviderConfig hook

## Related
- hooks/useProviderConfig.ts — consumer
- features/providers/ProviderConfigModal.tsx — UI

## Deprecation / Obsolete Notes
Active (1 hook consumer). No deprecation markers.