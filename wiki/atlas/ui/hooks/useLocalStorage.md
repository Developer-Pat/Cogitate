---
title: useLocalStorage
type: atlas-hook
path: frontend/src/hooks/useLocalStorage.ts
confidence: high
updated: 2026-08-01
tags: [type/hook, domain/atlas-ui]
---
# useLocalStorage

**Path**: `frontend/src/hooks/useLocalStorage.ts`
**Type**: hook

## Purpose
Generic localStorage state hook — value + setter + remove with JSON serialization and loading flag.

## Exported API
```typescript
export const useLocalStorage = <T>(key: string, initialValue?: T): UseLocalStorageReturn<T> => ({
  value, setValue: setStoredValue, removeValue: removeStoredValue, loading,
})
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| UseLocalStorageReturn | types/settings | Return type |
| frontendLoggingService | services | Parse/error logging |

## Usage Example
```tsx
const { value, setValue } = useLocalStorage<Theme>('theme', 'light')
```

## State / Data Flow
- Lazy init from storage (JSON.parse); writes on change; removeValue deletes key

## Related
- useSettings.ts, useTheme.ts, useConfiguration.ts — consumers