---
title: providerHealthStore
type: atlas-store
path: frontend/src/stores/providerHealthStore.ts
confidence: high
updated: 2026-08-01
tags: [type/store, domain/atlas-ui]
---
# providerHealthStore

**Path**: `frontend/src/stores/providerHealthStore.ts`
**Type**: store slice (Zustand StateCreator)

## Purpose
Provider health slice — health state + actions, composed INTO cognitiveHubStore (not standalone).

## State Shape
```typescript
export const createProviderHealthSlice: StateCreator<...> = (set, get, store) => ({
  // provider health state + actions
})
```

## Actions
- Health refresh, set/get (exact signatures from source)

## Selectors / Exports
```typescript
export { createProviderHealthSlice }
export type { ProviderHealthSlice }
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| providerService | domains/providers | Health data source (trace) |

## Usage Example
```tsx
// Used via cognitiveHubStore composition
```

## Data Flow / Notes
- Slice pattern: cognitiveHubStore spreads createProviderHealthSlice(set, get, store)

## Related
- stores/cognitiveHubStore.ts — composite root (imports this slice)

## Deprecation / Obsolete Notes
Active (composed into cognitiveHubStore). No deprecation markers.