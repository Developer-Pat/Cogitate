---
title: useDefaultProvider
type: atlas-hook
path: frontend/src/hooks/useDefaultProvider.ts
confidence: high
updated: 2026-08-01
tags: [type/hook, domain/atlas-ui]
---
# useDefaultProvider

**Path**: `frontend/src/hooks/useDefaultProvider.ts`
**Type**: hook

## Purpose
Default provider management — load, set, and lazily initialize the app's default provider.

## Exported API
```typescript
export const useDefaultProvider = () => ({
  defaultProvider, loading, error,
  refreshDefaultProvider: loadDefaultProvider,
  setDefaultProvider: handleSetDefaultProvider,
  initializeDefaultProvider: handleInitializeDefaultProvider,
})
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| defaultProviderService | domains/providers/defaultProviderService.ts | Get/set/init default |

## Usage Example
```tsx
const { defaultProvider, setDefaultProvider } = useDefaultProvider()
```

## State / Data Flow
- Loads on mount; setDefaultProvider persists choice; initialize lazily creates one if none

## Related
- features/providers/DefaultProviderConfig.tsx — consumer
- features/providers/DefaultProviderBadge.tsx — display