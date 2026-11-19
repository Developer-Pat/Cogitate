---
title: The Control System
type: devnote
path: wiki/dev-notes/design/control-system.md
confidence: high
updated: 2026-09-06
tags: [type/dev-notes, domain/design]
---

# The Control System

How Cogitate's buttons, badges, filters, and tooltips carry meaning —
the rules distilled from the UI-loudness work. These are the house
rules for every page: apply them to the next page, not just the last.

## The three layers

1. **Theme semantics** — DaisyUI's own `btn-*` / `badge-*` classes read
   the active theme's CSS variables (`--color-primary`, `--color-error`,
   …). Nothing is hardcoded; every custom semantic is a `color-mix` over
   the active theme's vars, so everything re-derives when the theme
   flips.
2. **Custom semantics** — caution (warning+error blend), transfer
   (secondary+primary → the violet band; import/export crossings).
3. **The machinery** — fill-strength tokens, the quiet-mode layer, the
   neutral-control default, the selected-state hook.

## The meaning of hues

- **Blue** (`--color-primary`) — the default control color. Ambiguous
  buttons join the action-blue family; hierarchy comes from FILL
  WEIGHT, not hue.
- **Red** (`error`) — the extreme tier: delete, Clear ALL, hard
  destruction. One per view at most.
- **Amber** (`warning`) — regular caution: resets, per-file clears.
- **Violet** (`transfer`) — moving a bundle across a boundary
  (import/export).
- **Cyan** (`info`) — informational/diagnostic (test generators).
- **Gray** (`neutral-content`, not the neutral fill) — the stop/exit
  voice: Cancel/close.

## The rules

- **One solid fill per view** = the CTA. Everything else demotes down
  the ladder: solid → semantic outline (`btn-<semantic> btn-outline`)
  → ghost (icon-only buttons only).
- **Checkboxes check in action-blue** (2026-09-06): every checkbox
  carries `checkbox-primary` (`-sm` for compact rows — `xs` is
  retired, `sm` is the size floor). The checked state is an
  affirmation — the same semantic as the one-solid CTA — so the
  plain DaisyUI checkbox (its checked fill defaults to a faint 20%
  base-content mix) reads as broken/atypical and is banned.
  `checkbox-error` is the one override (validation state). Single
  on/off settings use the DaisyUI `toggle` instead; checkboxes own
  selections, table rows, and inline option toggles in action rows.
- **Labeled ghosts read as unthemed** — a labeled action needs chrome
  (border). Ghost is for icon buttons.
- **Badges mirror buttons**: decorative filled badges → semantic
  outlines (`badge-primary` → `badge-primary badge-outline`); the ONE
  real status per context keeps its fill as the focal point.
- **The muted tier (2026-09-07 — the vocabulary expansion)**: the
  genuinely-neutral statuses (completed/skipped/ignored, the
  status-map defaults) use `badge badge-muted badge-outline` — the
  `--color-muted` token (tokens.css), a theme-keyed gray between
  the surface and the content (dark themes ~57% luminance, light
  ~46%). NOT for readouts that carry a hue semantic: the depth
  chip (deep/shallow/balanced) is `badge-info badge-outline` — the
  label text carries the value, the chip stays one consistent blue
  (corrected 2026-09-07 after the user's catch: nobody had decided
  the chip should be gray; it was always an info-blue readout).
  NEVER `badge-neutral badge-outline`: the neutral token is the
  near-black FILL (the dark pills + the gray escapes) and its
  outline is dark-on-dark on dark themes. The base-content outline
  is the loud readout tier (counts/readouts), not a status chip.
- **Icons XOR text** — a control carries one visual language: an icon
  or text, never both. Extends to tooltips and page headers (no emoji
  in banner titles).
- **The selected state = `.btn-selected`** (`--btn-color: var(
  --color-primary)`). DaisyUI's `btn-active` alone fills with the dark
  base (white-on-black, fades into dark cards) and `btn-active
  btn-secondary` fills pink. One uniform action-blue fill marks the
  chosen control in every filter/toggle group. It is deliberately NOT
  demoted by Quiet Mode — a selection is state, not noise; the one
  filled button per group keeps the choice legible.
- **Tooltips on everything that needs one** — DaisyUI tooltips only
  (native `title=` banned): SHORT, wrap disabled controls in the
  tooltip span so the hint still fires, page-top controls open DOWN
  (bottom) — an up-opening tip on a control near the top of a
  page/panel gets cut off at the container edge (the depth-chip
  catch, 2026-09-07); the same rule applies to the first rows of a
  page under its header (Macros). Mid-page/table tooltips open up
  by default. Icon-only controls always get one, self-labeled
  clusters (page numbers) use `aria-label` instead of hover noise.
- **Collapse arrows own the summary's pseudo-elements** — a tooltip
  can't sit on a DaisyUI collapse summary; wrap the whole `<details>`
  in the tooltip div.
- **Dense filter/control cards collapse behind a labeled bar** — a
  badge + an active-state count, closed by default. Page-level actions
  (Refresh) live OUT of the collapse, in the page header.
- **One line per concern, wrap whole groups** — merge related controls
  onto shared lines (left/right justified) with `flex-wrap` and
  `shrink-0` on each group: flex items SHRINK before the row wraps,
  and a squeezed `btn-group` collapses into a vertical column.
- **Page-top dropdowns open DOWN** (`dropdown-end` not
  `dropdown-top`) — an up-opening menu at the top of a page renders
  off-screen.
- **The cascade law** — index.css is unlayered, so it beats DaisyUI's
  `@layer`'d classes at any specificity. Blanket rules that touch
  `--btn-color`/`--btn-bg` must exclude the semantics with
  `:not(:where(.btn-primary, …))` — and legacy blanket overrides
  (e.g. an old `.dropdown .btn` background hack) silently override
  every semantic: when a control refuses its color, hunt the blanket
  rule before adding hacks.
- **The alias rule (2026-09-07)** — semantic names over palette
  values: where two semantics share a value, ONE declaration owns
  the value and the other is an alias (`--severity-high:
  var(--caution-bg)`) with a comment saying why. NEVER two literals
  of the same color, never a raw palette value inline in a
  component. One token backstops another, so retuning the source
  token retunes every alias.
- **The quiet-hover rule (2026-09-07, the user — hovers read VERY
  bright on the dark)** — hovers never jump to a SOLID fill.
  DaisyUI's outline/dash buttons drop their outline var-set while
  hovered and fall back to the base solid fill (its intended
  invert); the ghost paints the base-content directly. The app
  overrides that (index.css, unlayered, app-wide):
  - outline/dash hover = a soft tint of the hue
    (`color-mix(--btn-color 14%, transparent)`) with the body text
  - ghost hover = a 6% whisper
  - the quiet-mode demoted semantics hover the same 14% tint
    (their var-set pins --btn-bg: transparent through the hover,
    which gave them no feedback)
  Do NOT restore the solid-invert hover; if a button's hover reads
  wrong, tune the tint strengths (one place, two numbers) or
  promote them to a named token.
- **The text-role rule (2026-09-07, the grays work)** — text
  carries a ROLE, not a bare tier. The roles (tokens.css:
  `--text-*`, classes in index.css: `.text-*`):
  - `.text-body` — the primary text (`--text-body` = base-content).
  - `.text-label` — the field labels; an ALIAS of the body — the
    weight (font-medium) and the size do the label's work, never a
    dimmer color (labels must read as strongly as the body).
  - `.text-readout` — metadata / readouts (dates, counts,
    descriptions) — the old text-base-content/60 tier, named.
  - `.text-disabled` — the GRAY'S HOME (the user's doctrine):
    disabled / inactive text, the dimmest tier — dimmer than the
    readout so the hierarchy survives.
  - `.text-muted` — the quietest tone, the badge-muted family's
    text side (theme-keyed).
  NEVER write a bare `text-base-content/NN` tier in a component —
  pick the role class (one-knob per role; retuning a role retunes
  every use). The /NN ladder survives only as the Gallery's
  reference display.

## Quiet Mode

`appearance.loudness` (`Settings > Appearance > Quiet Mode`) demotes
every solid semantic fill (buttons + badges) to its outline var-set
app-wide — zero per-button classes. Semantic hues survive; only the
loud fills go. `btn-selected` and `btn-active` are exempt so selected
state stays legible.
