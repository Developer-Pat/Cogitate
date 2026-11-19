---
title: notificationStore
type: atlas-store
path: frontend/src/stores/notificationStore.ts
confidence: high
updated: 2026-08-01
tags: [type/store, domain/atlas-ui]
---
# notificationStore

**Path**: `frontend/src/stores/notificationStore.ts`
**Type**: store (Zustand)

## Purpose
Toast notification state — notifications list, add/remove/clear (success/error/warning/info).

## State Shape
```typescript
interface NotificationState {
  notifications: Notification[];
  addNotification(n: Notification): void;
  removeNotification(id: string): void;
  clearNotifications(): void;
  notifySuccess(msg): void; notifyError(msg): void;
  notifyWarning(msg): void; notifyInfo(msg): void;
}
```

## Actions
- addNotification, removeNotification, clearNotifications + typed notifiers

## Selectors / Exports
```typescript
export const useNotificationStore = create<NotificationState>(...)
```

## Dependencies
None (state only).

## Usage Example
```tsx
useNotificationStore.getState().addNotification({ id, type: 'success', message })
```

## Data Flow / Notes
- App-wide toasts; rendered by NotificationContainer

## Related
- components/NotificationContainer.tsx — renders toasts
- hooks/useNotifications.ts — wrapper
- Many components (BackendStatusIndicator, AddToCollectionModal, ...)

## Deprecation / Obsolete Notes
Active (many consumers). No deprecation markers.