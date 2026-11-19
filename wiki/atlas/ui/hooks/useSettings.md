---
title: useSettings
type: atlas-hook
path: frontend/src/hooks/useSettings.ts
confidence: high
updated: 2026-08-01
tags: [type/hook, domain/atlas-ui]
---
# useSettings

**Path**: `frontend/src/hooks/useSettings.ts`
**Type**: hook

## Purpose
User settings management with localStorage persistence and Zod validation — update, reset, export/import (parallel to useConfiguration).

## Exported API
```typescript
export const useSettings = (): UseSettingsReturn => ({
  settings, updateSettings, resetSettings, exportSettings, importSettings,
  loading: storageLoading, error,
})
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| useLocalStorage | hooks/useLocalStorage.ts | Persistence |
| z (zod) | Library | Settings schema validation |
| frontendLoggingService | services | Logging |

## Usage Example
```tsx
const { settings, updateSettings, exportSettings } = useSettings()
```

## State / Data Flow
- localStorage-backed; import validates before applying; export produces JSON string

## Related
- pages/Settings.tsx — primary consumer
- types/settings.ts — Settings schema (NewUserTips setting removed 2026-08-02)