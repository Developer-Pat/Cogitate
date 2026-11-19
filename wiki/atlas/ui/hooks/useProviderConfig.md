---
title: useProviderConfig
type: atlas-hook
path: frontend/src/hooks/useProviderConfig.ts
confidence: high
updated: 2026-08-01
tags: [type/hook, domain/atlas-ui]
---
# useProviderConfig

**Path**: `frontend/src/hooks/useProviderConfig.ts`
**Type**: hook

## Purpose
Provider configuration CRUD — providers list, create/update/delete, API-key set, and connection testing.

## Exported API
```typescript
export const useProviderConfig = () => ({
  providers, loading, error,
  refreshProviders, createProvider, updateProvider, deleteProvider,
  setApiKey, testProvider,
})
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| providerConfigService | domains/providers/providerConfigService.ts | CRUD + key + test |

## Usage Example
```tsx
const { providers, createProvider, setApiKey, testProvider } = useProviderConfig()
```

## State / Data Flow
- useState for providers/loading/error; refresh after mutations

## Related
- pages/ProviderDashboard.tsx — consumer
- features/providers/ProviderConfigModal.tsx — form consumer