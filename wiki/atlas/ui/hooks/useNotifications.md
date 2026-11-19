---
title: useNotifications
type: atlas-hook
path: frontend/src/hooks/useNotifications.ts
confidence: high
updated: 2026-08-01
tags: [type/hook, domain/atlas-ui]
---
# useNotifications

**Path**: `frontend/src/hooks/useNotifications.ts`
**Type**: hook

## Purpose
Toast notification helpers — success/error/warning/info, remove, clear. Thin wrapper over notificationStore.

## Exported API
```typescript
export const useNotifications = () => ({
  notifySuccess, notifyError, notifyWarning, notifyInfo,
  removeNotification, clearNotifications,
})
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| useNotificationStore | stores/notificationStore.ts | Toast state + actions |

## Usage Example
```tsx
const { notifySuccess } = useNotifications()
notifySuccess('Saved!')
```

## State / Data Flow
- Direct store passthrough

## Related
- App.tsx NotificationContainer — renders toasts
- stores/notificationStore.ts