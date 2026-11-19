---
title: useModeMacros
type: atlas-hook
path: frontend/src/hooks/useModeMacros.ts
confidence: high
updated: 2026-08-01
tags: [type/hook, domain/atlas-ui]
---
# useModeMacros

**Path**: `frontend/src/hooks/useModeMacros.ts`
**Type**: hook (multi-export)

## Purpose
Macro-set loading for the Macros page — loads macro sets (system + mode macros), error handling, plus F-key lookup helpers.

## Exported API
```typescript
export const useModeMacros = () => ({
  macros, isLoading, error, loadAllMacros, clearErrors, clearData,
})

export function useMacroByKey(key: string)  // searches across loaded macros by F-button key (F1-F5)
export function useMacroKeys()  // available macro keys
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| useSystemMacrosStore | stores/macroSetsStore.ts | Macro set state |
| frontendLoggingService | services | Logging |

## Usage Example
```tsx
const { macros, loadAllMacros } = useModeMacros()
const f1 = useMacroByKey('F1')
```

## State / Data Flow
- loadAllMacros fetches all sets into store; useMacroByKey looks up F1–F5 across them

## Related
- pages/Macros.tsx — primary consumer
- stores/macroSetsStore.ts