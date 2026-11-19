/**
 * TrashModal — the trash feature's modal shell.
 *
 * A NATIVE `<dialog className="modal">` opened with `showModal()`, containing the house PLAIN
 * panel (a `--dialog-width-*` token + `p-6`). NEVER DaisyUI's `modal-box`.
 *
 * WHY NATIVE: `showModal()` is what gives Escape-to-close, focus containment, focus RETURN to the
 * trigger and the browser's top layer. The plain overlay-div template has to hand-roll all four.
 *
 * WHY NOT `modal-box`: the project's procedure (`wiki/dev-notes/frontend/modal-dialogs.md`) forbids
 * it after five recurrences. The plain panel here keeps the token widths that procedure prescribes.
 *
 * COPIED FROM `components/features/providers/ProviderModal.tsx` — the working instance the dev note
 * points at — rather than re-derived. The recipe is carried whole: the mounted-is-open rule (no
 * `open` prop, so nothing can disagree with the DOM), the panel-focus caret rule, the `close`-event
 * state sync, and the backdrop click. Promoting this into `components/ui/` and converting the other
 * hand-rolled overlays is a separate, user-called move — not a drive-by.
 *
 * THE BACKDROP comes from `dialog.modal::backdrop` in `styles/index.css` — the browser default is
 * `rgba(0,0,0,.1)`, too light to separate a confirm from the page behind it.
 *
 * VERIFY a new instance by MEASURING the panel, never by looking:
 * `document.querySelector('dialog.modal[open] > div').getBoundingClientRect().width` — 600 for
 * `--dialog-width-md`.
 */
import React, { useEffect, useRef } from 'react'

interface TrashModalProps {
  /** Called when the dialog closes itself (Escape, backdrop click, or a control's own action). */
  onClose: () => void
  /** Accessible name for the dialog (`aria-label`); the panel also carries a visible title. */
  label: string
  /** A `--dialog-width-*` value: `md` (600px) for confirmations, `lg` (800) for the data-heavy. */
  width?: string
  children: React.ReactNode
}

/**
 * MOUNTED IS OPEN — the parent renders this only while the surface should be up, the house's
 * conditional-render convention, so there is no `open` prop to disagree with the dialog's own state.
 */
const TrashModal: React.FC<TrashModalProps> = ({
  onClose,
  label,
  width = 'var(--dialog-width-md)',
  children,
}) => {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = dialogRef.current
    if (!el || el.open) return
    el.showModal()
    // THE CARET — the browser's own "focus the first focusable descendant" step cannot be relied on
    // here, and the first control is the wrong landing anyway: the typed gate's input is what the
    // person came to use, but the browser's step lands on a button that then disables itself, which
    // drops the caret to `body`. So the PANEL takes the caret one frame after `showModal()` —
    // `tabIndex={-1}` keeps it out of the Tab order, and Tab from there walks into the controls.
    requestAnimationFrame(() => {
      panelRef.current?.focus()
    })
  }, [])

  // THE STATE SYNC: Escape (or anything else) can close the dialog ITSELF, and the `close` event is
  // the only place that knows it went away for a reason we did not ask for. Without this the
  // parent's state stays true and the next render would put the dialog straight back up.
  useEffect(() => {
    const el = dialogRef.current
    if (!el) return
    const handleClose = () => onClose()
    el.addEventListener('close', handleClose)
    return () => el.removeEventListener('close', handleClose)
  }, [onClose])

  // A native dialog does NOT close on a backdrop click; the house template does, so keep it. The
  // panel is a child element, so a click inside it never has the dialog as its target — no
  // `stopPropagation` needed.
  const handleClick = (e: React.MouseEvent<HTMLDialogElement>) => {
    if (e.target === dialogRef.current) onClose()
  }

  return (
    <dialog ref={dialogRef} className="modal" aria-label={label} onClick={handleClick}>
      <div
        ref={panelRef}
        tabIndex={-1}
        className="bg-base-100 rounded-lg shadow-xl max-h-[90vh] overflow-y-auto p-6 focus:outline-none"
        style={{ width: `min(${width}, 95vw)` }}
      >
        {children}
      </div>
    </dialog>
  )
}

export default TrashModal
