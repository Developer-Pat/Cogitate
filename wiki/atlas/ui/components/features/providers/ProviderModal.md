---
title: ProviderModal
type: atlas-component
path: frontend/src/components/features/providers/ProviderModal.tsx
confidence: high
updated: 2026-09-29
tags: [type/component, domain/atlas-ui]
---
# ProviderModal

**Path**: `frontend/src/components/features/providers/ProviderModal.tsx`

## Purpose

The providers feature's modal shell: a **native `<dialog className="modal">` opened with
`showModal()`**, holding the house PLAIN panel — a `--dialog-width-*` token plus `p-6`. It never uses
DaisyUI's `modal-box`, which the project's modal procedure forbids
([[dev-notes/frontend/modal-dialogs|Modal Dialogs]]).

**Mounted is open.** The parent renders it only while the surface should be up (the house
conditional-render convention), so there is no `open` prop that could disagree with the dialog's own
state. Closing is signalled back through `onClose` — from the panel's own controls, from a backdrop
click, or from the native `close` event that Escape fires.

Why native: `showModal()` is what supplies **Escape-to-close, focus containment, focus return to the
trigger, and the browser's top layer**. A plain overlay `<div>` has to hand-roll all four, and the
surface this shell was written for (the Model Browser) had none of them.

## Props

```typescript
interface ProviderModalProps {
  onClose: () => void          // called when the dialog closes itself
  label: string                // aria-label for the dialog; the panel also carries a visible title
  width?: string               // a --dialog-width-* value; default 'var(--dialog-width-xl)'
  children: React.ReactNode
}
```

Widths live in `frontend/src/styles/tokens.css`: `--dialog-width-sm` 500 · `md` 600 · `lg` 800 ·
`xl` 1000. A data panel takes `xl`, a form `md`.

## Behaviour worth knowing

- **The caret goes to the PANEL, one frame after `showModal()`** (`tabIndex={-1}`, never a Tab stop,
  `focus:outline-none`). The browser's own "focus the first focusable descendant" step cannot be
  relied on here and the first control is the wrong landing anyway: a shell whose first user checks
  on open disables its own first button a moment later, and the browser drops the caret to `body`
  when the focused control is disabled — measured, the caret never entered the open dialog.
- **A click on the backdrop closes it** (`e.target === dialogRef.current`); the panel is a child, so
  no `stopPropagation` is needed.
- **`dialog.modal::backdrop` in `frontend/src/index.css`** supplies the house dim. The browser's own
  default is `rgba(0,0,0,.1)`, too light to separate a data panel from the page behind it.

## Verification

Measure the panel, never eyeball it:
`document.querySelector('dialog.modal[open] > div').getBoundingClientRect().width` — 1000 for `xl`,
600 for `md`. On the live page: Escape closes, focus returns to the trigger, and the page behind dims.

## Used by

- [[atlas/ui/components/features/providers/ProviderHealthModal|ProviderHealthModal]] — the provider
  health report (`md`).
- [[atlas/ui/pages/ProviderDashboard|Provider Dashboard]] — the Model Browser panel (`xl`).

## Related

- [[dev-notes/frontend/modal-dialogs|Modal Dialogs]] — the project's modal procedure this shell
  follows (the plain panel, the token widths, the measure-to-verify step).
- `frontend/src/index.css` — the backdrop rule and the `modal-box` width rescue that this shell
  deliberately does not use.
