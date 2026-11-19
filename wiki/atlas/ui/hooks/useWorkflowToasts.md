---
title: useWorkflowToasts
type: atlas-hook
path: frontend/src/hooks/useWorkflowToasts.ts
confidence: high
updated: 2026-08-10
tags: [type/hook, domain/atlas-ui]
---

# useWorkflowToasts

**Hook**: `frontend/src/hooks/useWorkflowToasts.ts`
**Mounted in**: `frontend/src/App.tsx` (the app shell — toasts appear on every page)

## Purpose

Drains the ToastDistributor queue. Polls
`GET /api/v1/workflows/toasts?since=<cursor>` and shows each new
workflow product as an **app-wide in-app toast** (notificationStore
`addInfo`) — the toast channel of the workflow product
distribution layer.

## Behavior

- Polls every 15s (configurable via `intervalMs`)
- **Cursor dedup**: the newest `created_at` seen is stored in
  `localStorage` (`workflow_toast_cursor`) — after a toast fires
  once, refreshes don't re-toast it
- Newest-first queue; toasts play in chronological order
- Silent failures — polling never spams errors (console.warn only)

## Related

- [[dev-notes/workflows/product-distribution|Workflow Product Distribution]] — the toast channel
- [[atlas/api/routers/workflows|Workflows API]] — the toasts endpoint
- [[atlas/ui/pages/WorkflowProducts|Workflow Products]] — the display channel sibling
