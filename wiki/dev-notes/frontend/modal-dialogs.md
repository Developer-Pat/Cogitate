---
title: Modal Dialogs
type: atlas-devnote
category: frontend
order: 4
confidence: high
updated: 2026-08-25
tags: [type/dev-notes, domain/frontend]
---

# Modal Dialogs — THE PROCEDURE

> **THE 4TH/5TH RECURRENCE (2026-08-25, the PackageTab modals).**
> This note leads with the ONE working procedure. When you build a
> modal, COPY the template below verbatim — do not improvise, do
> not reach for `modal-box`. The history of how we learned this is
> at the bottom.

## The ONLY working pattern (copy verbatim)

```tsx
<div
  className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/50"
  onClick={() => onClose()}
>
  <div
    className="bg-base-100 rounded-lg shadow-xl max-h-[90vh] overflow-y-auto p-6"
    style={{ width: 'min(var(--dialog-width-md), 95vw)' }}
    onClick={(e) => e.stopPropagation()}
  >
    {/* the content — the title, the body, the actions */}
  </div>
</div>
```

## The rules (each one was learned the hard way)

1. **NEVER use the DaisyUI `modal-box` class.** In this Tailwind v4
   setup it renders at **48px wide** — and the `max-w-*` classes used to
   "fix" it are broken too (see the section below: `max-w-md` is 16px,
   `max-w-lg` is 24px, `max-w-xl` is `none`). The only safe forms are a
   `.modal.modal-open` wrapper or a native `<dialog>.showModal()` — and
   even those are NOT the house style.
2. **The width var AND `p-6` — BOTH required.** The var without
   padding clips the content at the edges ("the display clipped").
   The vars live in `styles/tokens.css`: `--dialog-width-sm` 500 /
   `md` 600 / `lg` 800 / `xl` 1000 / `full` 95vw. Pick by content:
   md for the confirmations + the simple forms, lg/xl for the
   data-heavy.
3. **The overlay clicks close** (`onClick` on the fixed overlay);
   the panel stops the propagation (`onClick={(e) => e.stopPropagation()}`).
4. **The props contract**: `onClose: () => void` always + the action
   callbacks (`onCreate`, `onSave`, ...). The open state is the
   parent's (the conditional render).

## VERIFY (the step everyone skips — the reason it recurs)

After building: open the modal and measure.

```js
document.querySelector('.modal-open, [class*="rounded-lg"]')?.getBoundingClientRect().width
```

md = 600, lg = 800. If it says **48 — you used modal-box** (or the
width var's missing). Fix it before the user sees it.

---

## THE SAME TRAP, WIDER: `max-w-*` is NOT what it says (measured, live page)

**Any `max-w-sm|md|lg` in this setup resolves against the project's SPACING
namespace, not Tailwind's container scale** — the `--container-*` tokens are not
defined anywhere (`tokens.css` defines `--spacing-md: 1rem`, `--spacing-lg:
1.5rem`, and the numbers come out exactly those). Measured by probing classes on
the running app:

| class | resolves to | meant |
|---|---|---|
| `max-w-md` | **16px** | 28rem |
| `max-w-lg` | **24px** | 32rem |
| `max-w-xl` | **none** | 36rem |

**What it looks like:** a block child of an `items-center` column flex is sized by
its max-width, so the text comes out **one word per line** in a 16px column —
a hair different from the modal symptom, and the same cause. This is how the
user-testing page's Live-tab empty state read before it was caught:
*"Start / one / from / Runnable, / Conditional…"*.

**`w-full` does NOT rescue it.** `width: 100%` is still capped by the broken
max-width; the box stays 16px.

**THE RULE: never size a content box with `max-w-*`.** Use the house token for a
one-column explanation — `style={{ maxWidth: 'var(--content-measure)' }}` (see
`design-tokens.md`) — or `min(var(--dialog-width-md), 95vw)` as this template does.

**THE SILENT VARIANT, found 2026-09-28** (the cloud-providers arc, Phase 6): the Model Browser
panel in `ProviderDashboard.tsx` sized itself with `max-w-5xl`, which in this setup resolves to
**`none`** — so the panel was as wide as its `w-full` parent happened to make it (**measured: the
overlay 1280px, the panel ~1248px inside the `p-4`**) and `computedStyle.maxWidth` read `none`.
Nothing looked broken, which is the point: the tiny values below ANNOUNCE themselves, and `none`
does not. The panel was wide by luck, and a change to its parent would have silently taken that
away. Fixed to `min(var(--dialog-width-xl), 95vw)` — the token for a data-heavy panel — and the
same VERIFY step proves it: **1000px, the token, no viewport overflow.** Prefer the token:

```
style={{ width: 'min(var(--dialog-width-lg), 95vw)' }}
```

**17 class-name usages across 15 files** of `max-w-sm|md|lg` sit in
`frontend/src` (empty states, error boundaries, several modals that pair it with
`modal-box`). The ROOT FIX is one thing — define
`--container-sm/md/lg/xl/2xl/3xl` in the `@theme` block of `tokens.css` — and it
repairs every one of them at once. It is also an app-wide layout change, so it is
a deliberate step rather than a drive-by.

---

## The history (the recurrences)

- **2026-09-15** — LifecycleCard (the shutdown confirm, Dashboard): `dialog.modal`
  + `modal-box max-w-sm` → **8px wide, one character per line.** The note was not
  read first; the template was not copied. Fixed by copying the verbatim template
  and using `--dialog-width-sm`. The VERIFY step (`getBoundingClientRect`) caught
  it — 8 → 500 after the fix. **This recurrence is the argument for the note
  leading with "copy verbatim": knowing about the trap is not the same as
  following the procedure.**

- **2026-08-11** — ProfileImagePicker: `modal-box` + `z-[100]` →
  the dark overlay with no visible box. Fixed with the plain
  container.
- **2026-08-14** — WorkflowProducts report viewer + the Clear
  confirm: the same mask-without-box. Fixed the same way.
- **2026-08-18** — the Scheduler modal + the products delete modal:
  `modal-box` renders **48px wide** — the width classes do nothing.
  Fixed with the width var + `p-6`. (The SchedulerModal is the
  canonical working example.)
- **2026-08-25** — the PackageTab detail + confirm modals: the
  `modal-box` again → 48px again. Fixed by copying the Scheduler
  pattern verbatim. **The user: "this is the 4th or 5th time" — the
  recurrence stops here: this note leads with the procedure.**
