---
title: TrashModal
type: atlas-component
path: frontend/src/components/features/trash/TrashModal.tsx
confidence: high
updated: 2026-10-06
tags: [type/component, domain/atlas-ui]
---

# TrashModal

**Path**: `frontend/src/components/features/trash/TrashModal.tsx`

## Purpose

The trash feature's modal SHELL — a native `<dialog className="modal">` opened with
`showModal()`, containing the house PLAIN panel (a `--dialog-width-*` token + `p-6`).
Never DaisyUI's `modal-box`.

**Why native:** `showModal()` is what gives Escape-to-close, focus containment,
focus RETURN to the trigger, and the browser's top layer. The plain overlay-div
template has to hand-roll all four. **Why not `modal-box`:** the project's
procedure ([[dev-notes/frontend/modal-dialogs|Modal dialogs]]) forbids it after five
recurrences — the size classes resolve against the spacing namespace and squeeze the
panel.

**Copied from `components/features/providers/ProviderModal.tsx`** — the working
instance the dev note points at — rather than re-derived. The recipe is carried
whole:

- **mounted is open** — no `open` prop, so nothing can disagree with the DOM;
- the **panel takes the caret** one frame after `showModal()` (`tabIndex={-1}` +
  `focus:outline-none`), because the browser's own focus step is undone when the
  modal's first control disables itself;
- the **`close` event syncs the parent's state** — Escape can close the dialog
  itself, and without this the next render would put it straight back up;
- the **backdrop click** closes (a native dialog does not do this on its own), and
  the backdrop dim comes from `dialog.modal::backdrop` in `styles/index.css`.

Promoting this into `components/ui/` and converting the other hand-rolled overlays
is a separate, user-called move — not a drive-by.

## Props Interface

```typescript
interface TrashModalProps {
  /** Called when the dialog closes itself (Escape, backdrop click, or a control's action). */
  onClose: () => void
  /** Accessible name for the dialog; the panel also carries a visible title. */
  label: string
  /** A `--dialog-width-*` value: `md` (600px) by default. */
  width?: string
  children: React.ReactNode
}
```

## Related

- [[dev-notes/frontend/modal-dialogs|Modal dialogs]] — the procedure this follows
- [[atlas/ui/components/features/trash/PurgeEntryModal|PurgeEntryModal]] · [[atlas/ui/components/features/trash/EmptyShelfModal|EmptyShelfModal]] — its two users
