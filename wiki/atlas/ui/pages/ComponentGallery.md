---
title: ComponentGallery
type: atlas-page
path: frontend/src/pages/ComponentGallery.tsx
confidence: high
updated: 2026-10-07
tags: [type/page, domain/atlas-ui]
---

# ComponentGallery

**Component**: `frontend/src/pages/ComponentGallery.tsx`
**Route**: `/components` (protected, `requiresAuth: true`, icon `layers`, breadcrumb `Gallery`) —
registered in `frontend/src/config/routes.ts`; the sidebar's **Development** section in `App.tsx`
(nav label "Gallery").

## Purpose

The live control and text **vocabulary**, one page: every sample renders the REAL class, so switching
the active theme re-samples the whole gallery. Each entry is the sample beside its role name and the
class/token it uses today — the point being to SEE what exists (including the gray tiers) before
deciding what deserves a token.

It is a render of the theme, not of any data: the page calls no service and reads no store, so it is
also the fastest way to see whether a palette change landed.

## The four tabs

| tab | what it holds |
|---|---|
| **Controls** | the button tiers and the form controls — primary CTA (the one solid), the semantic outlines (second tier), the two custom semantics, the gray escape, the uniform on-state, checkbox, toggle, input, spinner |
| **Badges** | the status chips — the hue outlines, the access pair, the muted tier, the ghost, the count bubble |
| **Text** | the text roles, the chat bubbles, and the gray-tier ladder |
| **Palette** | the active theme's named colors, read live from the CSS variables |

**The button ladder is the page's real content**, because the tiers are a rule rather than a style:
`btn-primary` is the ONE solid (the page's primary action), the semantic hues are outlines, and
`btn-neutral` is the gray escape — the deliberate destination for stop/cancel, where a semantic colour
would read as a meaning the action does not have. `btn-caution` and `btn-transfer` are the two
custom semantics (`--caution-bg`, `--transfer-bg`).

**The on-state is uniform**: `btn-active btn-selected` is rendered once, as the single way a control
reads as selected.

**The gray-tier ladder** walks `text-base-content/<tier>` from `/20` to `/90` with a sample line at
each tier — the visual answer to which dimming is "metadata" and which is "disabled". The named text
roles are the tokens that ladder is meant to be replaced by: `.text-body`, `.text-label`,
`.text-readout`, `.text-disabled` (the dimmest), `.text-muted`.

**The chat bubbles** carry the ghost treatment and the hover halo — the backlight glow that is the
only selection cue (`bubble-ghost:hover`), shown at rest and lit.

## Palette (live)

The 20 named theme colors (`primary`…`error-contact`, each with its `-content` pair) are sampled with
`getComputedStyle(document.documentElement).getPropertyValue('--color-<name>')`, so the swatch and the
hex shown are the ACTIVE theme's own values. A `MutationObserver` watching `data-theme` on
`<html>` re-renders the tab, which is what makes "switch the theme in Settings and watch this
re-sample" true rather than aspirational.

## State management

Local `useState` only — the active tab, plus a re-render counter the observer bumps. No store, no
service call, no props. Each sample is wrapped by the local `Sample` component (sample, role name,
token string in mono).

## Related pages

- [[atlas/ui/pages/Settings|Settings]] — where the active theme is switched
