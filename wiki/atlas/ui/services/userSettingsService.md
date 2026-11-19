---
title: userSettingsService
type: atlas-service
path: frontend/src/services/userSettingsService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# userSettingsService

**Path**: `frontend/src/services/userSettingsService.ts`
**Type**: service (object singleton)

## Purpose
User settings synchronization with the backend — save/load user preferences persistence.

## Exported API
```typescript
export const userSettingsService = {
  saveSettings(settings), loadSettings(), updateSettings(updates),
  // exact methods from source
}
```

## Endpoints
- `GET/PUT /api/v1/settings`

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| apiClient | services/apiClient.ts | Enhanced client |
| frontendLoggingService | services | Logging |

## Usage Example
```tsx
await userSettingsService.saveSettings(settings)
```

## Data Flow / Notes
- Backs Settings page persistence; settingsStore may mirror

## Related
- pages/Settings.tsx — consumer
- stores/settingsStore.ts — frontend-side settings state