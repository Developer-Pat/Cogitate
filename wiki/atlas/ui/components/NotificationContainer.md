---
title: NotificationContainer
type: atlas-component
path: frontend/src/components/NotificationContainer.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# NotificationContainer

**Path**: `frontend/src/components/NotificationContainer.tsx`
**Last Updated**: 2026-08-01

## Purpose

Renders the application's toast/notification stack in the bottom-right corner of the viewport. It reads the `notifications` array from the Zustand `notificationStore`, renders each notification as a DaisyUI `alert` card (with a type-specific icon, title, message, and dismiss button), and returns `null` when there are no notifications. Notifications are auto-removed by the store after their `duration` (default 5000 ms); the container itself only surfaces the store state and dispatches `removeNotification` on manual dismissal.

## Props Interface

The component accepts **no props** — there is no props interface to copy. It is a self-contained view that pulls all of its data from the `useNotificationStore` hook:

```typescript
export function NotificationContainer() {
  // no props
}
```

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `useNotificationStore` (from `../stores/notificationStore`) | Zustand store hook | Provides the `notifications` array (rendered as toasts) and the `removeNotification(id)` action (dismiss button handler) |

## Usage Example

The component is mounted once at the app root and rendered conditionally alongside the main layout; notifications are created imperatively from anywhere via the store's action helpers:

```tsx
// App.tsx
import { NotificationContainer } from './components/NotificationContainer'
import { useNotificationStore } from './stores/notificationStore'

function App() {
  return (
    <>
      {/* ...app layout... */}
      <NotificationContainer />
    </>
  )
}

// Anywhere in the app — create a toast:
const addSuccess = useNotificationStore((s) => s.addSuccess)
addSuccess('Saved', 'Your changes were persisted.')
```

## State Used

- `notifications: Notification[]` — from `useNotificationStore()` (destructured selector). Each item is a `Notification` with `id`, `type: 'success' | 'error' | 'warning' | 'info'`, `title`, `message`, `timestamp`, optional `duration`, and optional `action`.
- `removeNotification(id: string)` — store action called by each toast's dismiss button (`onClick`); removes the notification by id.

The component holds no local state. When `notifications.length === 0` it renders `null`. Each toast maps `type` to a DaisyUI alert class (`alert-success` / `alert-error` / `alert-warning` / `alert-info`, defaulting to `alert-info`) and to an inline SVG icon (`success`/`error`/`warning`/`info`; `null` for unknown types). The toast container uses `toast toast-bottom toast-end` with `z-50`, `max-w-[33vw]`, `min-w-[280px]`, and an `animate-in slide-in-from-right` entrance animation on each alert.

## Related Components

- `frontend/src/stores/notificationStore.ts` — the Zustand store this component consumes; defines `Notification`, `addNotification`, `removeNotification`, `clearNotifications`, and the `addSuccess` / `addError` / `addWarning` / `addInfo` helpers (auto-removal timer lives here).
- `frontend/src/App.tsx` — mounts `<NotificationContainer />` at the app root (line ~430).
- `frontend/src/components/__tests__/NotificationContainer.test.tsx` — unit tests rendering the container against a mocked/populated store.
