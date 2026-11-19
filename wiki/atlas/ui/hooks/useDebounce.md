---
title: useDebounce
type: atlas-hook
path: frontend/src/hooks/useDebounce.ts
confidence: high
updated: 2026-08-01
tags: [type/hook, domain/atlas-ui]
---
# useDebounce

**Path**: `frontend/src/hooks/useDebounce.ts`
**Type**: hook

## Purpose
Debounce hook — delays value updates to prevent excessive API calls (e.g. search-as-you-type).

## Exported API
```typescript
export function useDebounce<T>(value: T, delay?: number): T  // delay default 300ms
```

## Dependencies
None (React useState/useEffect only).

## Usage Example
```tsx
const debouncedQuery = useDebounce(searchQuery, 300)
useEffect(() => { search(debouncedQuery) }, [debouncedQuery])
```

## State / Data Flow
- Returns the input value after it has been stable for `delay` ms (trailing-edge debounce)
- Timer cleared on value/delay change or unmount

## Related
- useFiltering.ts, useGlobalSearch.ts — typical consumers