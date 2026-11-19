---
title: settingsStore
type: atlas-store
path: frontend/src/stores/settingsStore.ts
confidence: high
updated: 2026-08-01
tags: [type/store, domain/atlas-ui]
---
# settingsStore

**Path**: `frontend/src/stores/settingsStore.ts`
**Type**: store (Zustand)

## Purpose
App settings state — user settings + update actions (persisted).

## State Shape
```typescript
interface SettingsState {
  settings: AppSettings;
  updateSettings(updates: Partial<AppSettings>): void;
  resetSettings(): void;
}
```

## Actions
- updateSettings, resetSettings

## Selectors / Exports
```typescript
export const useSettingsStore = create<SettingsState>(...)
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| userSettingsService | services | Backend sync (trace) |

## Usage Example
```tsx
useSettingsStore.getState().updateSettings({ showMacroIds: false })
```

## Data Flow / Notes
- NewUserTips `showNewUserTips` setting lived here — REMOVED 2026-08-02

## Related
- App.tsx, ResponseStream.tsx, PipelineConfigTab.tsx — consumers
- hooks/useUIStateBridge.ts — sync

## Deprecation / Obsolete Notes
Active (5 consumers). No deprecation markers.