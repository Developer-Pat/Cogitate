---
title: DeleteRunModal
type: atlas-component
path: frontend/src/components/features/testing/DeleteRunModal.tsx
confidence: high
updated: 2026-09-20
tags: [type/component, domain/atlas-ui]
---

# DeleteRunModal

**Path**: `frontend/src/components/features/testing/DeleteRunModal.tsx`

## Purpose

The confirmation for retiring ONE run. Dumb by design: the page owns the request, the
pending state and the error — this renders what the action needs to say and nothing
more.

It names three things:

- **which run** (`name`), because a table row is not a name;
- **what happens** — the folder moves to `trash/test-runs/<name>` with its three
  artifacts, so the action is recoverable rather than final, and the page never deletes
  a run on its own;
- **the refusal, when there is one** — a run in progress is refused by the backend with
  the LOCK's own sentence, shown here rather than as a generic error.

Markup follows the modal-dialog procedure verbatim (see
[[dev-notes/frontend/modal-dialogs|Modal dialogs]]): the fixed overlay, the width var
(`--dialog-width-md` = 600) and `p-6`. DaisyUI's `modal-box` renders 48px wide in this
Tailwind v4 setup and is never used.

## Props Interface

```typescript
interface DeleteRunModalProps {
  run: RunSummary
  pending: boolean
  error: string | null
  onClose: () => void
  onConfirm: () => void
}
```

## Related

- [[atlas/ui/components/features/testing/ReportsTable|ReportsTable]] — where Delete lives
- [[atlas/ui/pages/TestingDashboard|Testing Dashboard]] — the page that owns the call
