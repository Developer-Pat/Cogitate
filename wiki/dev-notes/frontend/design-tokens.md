---
title: Design Tokens & the House Style
type: dev-note
category: frontend
subtopic: design
order: 1
confidence: high
created: 2026-08-31
updated: 2026-08-31
tags: [domain/dev-notes, domain/frontend]
---

# Design Tokens & the House Style

The app rides **DaisyUI 5 + Tailwind 4** — the THEME TOKENS are the
design system; the literal colors never appear in the components.

## The theme tokens

| Token | Use |
|---|---|
| `base-100` / `base-content` | The card/page surfaces + the text |
| `base-200` / `base-300` | The hover surfaces / the borders |
| `primary` / `primary-content` | The accent — the buttons, the active states, the links |
| `warning` / `error` / `success` | The SEMANTIC states — the classes, the badges, the alerts |
| `opacity-60/70` | The secondary text (never a gray literal) |

**THE SEMANTIC RULE**: a component references the tokens
(`bg-base-100`, `text-primary`, `badge-warning`), never a literal
color — the dark/light themes recolor the app automatically. A
theme change is ONE stylesheet, not a class-hunt.

### The measure tokens (`:root` in `tokens.css`)

`tokens.css` also carries the house's own component-token layer — buttons, cards,
badges, bubbles, dialogs, a few hundred names grouped by component. Among them,
the two that govern MEASURE:

| Token | Value | Use |
|---|---|---|
| `--content-measure` | `28rem` (~65 characters at the body size) | an empty state, an error message, or any other ONE-COLUMN explanation |
| `--content-measure-wide` | `42rem` | a paragraph with a list beside it |

Use them as `style={{ maxWidth: 'var(--content-measure)' }}` (with `w-full`) —
**not `max-w-md`.** `max-w-*` does NOT mean what it says in this project: it
resolves against the spacing namespace (`--spacing-md` = 1rem), so `max-w-md`
is **16px** and a column flex sized by its max-width comes out one word per
line. Measured, and the trap is spelled out in `modal-dialogs.md`; the
`--container-*` root fix is a deliberate app-wide step, not a drive-by.

The point of the token is the CHOICE: a comfortable line length, decided once,
rather than the same number typed into fifteen files.

## The house's design elements

### The pill button (the named class — `frontend/src/index.css`)

```css
.pill-button { @apply rounded-full px-3 py-1 text-xs font-medium transition-all; }
.pill-button--normal  { @apply bg-primary/20 text-primary border border-primary/30 hover:bg-primary/30; }
.pill-button--warning { @apply bg-warning/20 text-warning border border-warning/30 hover:bg-warning/30; }
```

- The base holds the GEOMETRY; the modifiers hold only the
  SEMANTIC color from the theme's tokens (the "red pill" = the
  `--warning` modifier — NOT a literal red).
- THE ONE-DEFINITION rule: new pill uses reference the named
  classes; the inline class-copies are the drift to avoid.
- Used: the Help buttons' peers, the Reset (ExaChat), the ACP pill,
  the Temporary Mute (the warning modifier).

### The cards

`card bg-base-100 shadow-md` + `card-body p-4` — the standard
surface. The card-title `text-sm` + the `text-xs opacity-70`
hint-line under it.

### The tabs

The tab-based pages use `tabs tabs-box` with the `tab tab-active`
buttons (e.g. the Notifications page's Config + Events). The
page's default tab = the most-visited surface (the asset-first:
the Sounds page lands on the Catalog).

### The tooltips

The Daisy `tooltip` + `data-tip` — the labels' replacement:

- **Open DOWN** (`tooltip-bottom`) on the widgets at the page's
  TOP (the banner-line widgets — a top tooltip would clip).
- **Open UP** (`tooltip-top`) on the in-card controls.
- The `aria-label` always accompanies the icon-only controls.

### The banner-line widgets

The PageBanner's `action` slot holds the header widgets (the
Temporary Mute, the Help button) — the top-of-page actions ride
the title's line, not a card below it.

### THE GHOST BUBBLES (2026-09-01 → 2026-09-03, the chat bubbles)

The chat message bubbles (`index.css` ~L136-200) — the user's
clutter-free look:

- **The ghost field** — the bubble fill EQUALS the page
  background (`--color-base-100`); the text reads clean, no boxes.
  Toggle: Settings → Appearance → Ghost Chat Bubbles
  (`chatBubbleGhost`).
- **The all-corner rounding** — every chat bubble (ghost or
  colored) rounds ALL FOUR corners at `--radius-xl` (1rem — the
  modal radius). DaisyUI's chat defaults square the tail corner
  (chat-start → bottom-left, chat-end → bottom-right) and paint a
  tail via the `:before` mask — overridden unlayered (unlayered
  CSS beats the DaisyUI layer); the ghost tail is `display: none`.
- **The hover backlight (NOT a fill change)** — hovering a ghost
  bubble fades in a soft modal-like glow: a 1px ring at ~7%
  content alpha + a contact shadow at 10% + a 24px halo at 18%
  (color-mix on the content token — theme-aware). It fades back
  out on mouse-leave (0.2s). The pre-2026-09-04 hover repainted
  the fill via the `--background-burn/dodge-color` tokens —
  REMOVED (the user's call: the glow alone is the selection cue).
- **The input widget** — the wrapper behind the input is
  transparent; the black band that once used the system-bubble
  message token as a page surface is gone.

## The conventions

- **NO EMOJI** — the SVG icons are the house style (the icon
  form; the label → the tooltip/aria).
- **THE FLYOUTS OPEN UP** — the dropdowns/popovers never drop
  down over the content below.
- **NEW TABS** — the browser tabs are the navigation: the
  message/Exa/wiki buttons always `window.open`; a page's detail
  opens in a NEW TAB, never an in-app modal.
- **THE LABEL→TOOLTIP RULE** — the text labels yield to the
  Daisy tooltips (the icon-form controls + the tooltip).
- **THE TAB TITLE**: every tab = `Page | Cogitate™` via the ONE
  `TITLE_SUFFIX` constant (`frontend/src/config/pageTitles.ts`).
- **THE TABLE LISTS** — the list UIs are tables with the
  selectable rows + the explicit action button (never a bare
  row-click).

## The history

The dated design material (the 2026-02 primer, the token-system
critiques) lives in the gitignored `local/themes/` — this note is
the living current-state.
