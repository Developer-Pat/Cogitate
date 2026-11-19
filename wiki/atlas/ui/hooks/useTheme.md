---
title: useTheme
type: atlas-hook
path: frontend/src/hooks/useTheme.ts
confidence: high
updated: 2026-08-01
tags: [type/hook, domain/atlas-ui]
---
# useTheme

**Path**: `frontend/src/hooks/useTheme.ts`
**Type**: hook

## Purpose
Theme management — stored theme (light/dark/system?), resolved theme, set/toggle, isDark/isLight helpers.

## Exported API
```typescript
export const useTheme = () => ({
  theme: storedTheme, resolvedTheme, setTheme, toggleTheme, isDark, isLight,
})
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| useLocalStorage | hooks/useLocalStorage.ts | Theme persistence |

## Usage Example
```tsx
const { theme, setTheme, toggleTheme, isDark } = useTheme()
```

## State / Data Flow
- resolvedTheme resolves 'system' → actual (media query); applies class to document root

## Related
- App.tsx / layout — theme application
- ui/settings/ThemeSelector.tsx — selector UI