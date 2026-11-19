---
title: Tooltip clipping in scroll containers
type: dev-note
category: frontend
subtopic: ui
confidence: high
created: 2026-09-15
updated: 2026-09-17
tags: [type/dev-notes, domain/frontend, domain/ui]
---

# Tooltip clipping in scroll containers

## The symptom, and why it hides so well

A tooltip with **correct** content that never appears. The markup is right, the
`data-tip` is right, and inspecting the element shows the text is there:

```
beforeContent:     "Local Weather 10-Day Forecast"   ← the right text
clippingAncestors: 5                                 ← and you never see it
```

**A missing tooltip and a clipped tooltip look identical to the user**, which is why
this reads as "nobody added a tooltip" rather than "the tooltip is being cut off".

## The cause

DaisyUI's `.tooltip` renders its text in an **absolutely-positioned `::before`**. Any
ancestor with `overflow: auto | hidden` clips it.

`overflow-y: auto` alone is enough: when one axis is non-`visible`, the browser computes
the other as `auto` too, so the clipping applies horizontally as well. The sessions panel
had five such ancestors — two scroll regions, the panel itself, and an
`overflow-hidden` root.

**No CSS tweak fixes this.** `overflow: visible` cannot be set on a scroll container
without breaking scrolling, and `position: fixed` on the `::before` cannot be positioned
per element from CSS alone.

## The fix

Render the tip **outside the clipping tree**: a portal to `document.body` with
`position: fixed` coordinates taken from `getBoundingClientRect()`.

**`components/ui/PortalTooltip.tsx`** does this, and it is deliberately **opt-in** —
nothing that already works goes through it.

## When a clipper does NOT clip: test the tip's rectangle

**A clipping ancestor is not the same as a clipped tip.** `overflow` cuts only what extends
beyond the clipper's own BOX, so **where the tip LANDS** decides it — not how many ancestors
there are.

Measured on the chat header's badges, which genuinely sit under three clipping ancestors
(two `overflow-hidden` containers and a full-height `overflow-y-auto` scroller):

```
badge:              y 28            the tip opens DOWNWARD from it
tip rectangle:      y 44 -> 68
clipping ancestors: 3, every one ending at y 577
verdict:            escapes NONE of them -> the tip is fully visible
```

The same page's side panel is the opposite case: a **long** tip whose anchor sits against
the panel's right edge runs past the boundary and is cut.

**So the test is two numbers, not a count:**

1. Take the anchor's `getBoundingClientRect()` and the tip's expected rectangle for the
   direction you are using.
2. Walk the ancestors; for each one whose overflow is not `visible`, ask whether the tip
   rectangle crosses **that ancestor's box**.

**Measure the tip's width from its real text — never assume one.** Rendering the string
off-screen at the tip's font size settles it in a line:

```js
const probe = document.createElement('span')
probe.textContent = tipText
probe.style.cssText =
  'position:absolute;visibility:hidden;white-space:nowrap;font-size:0.75rem'
document.body.appendChild(probe)
const width = Math.ceil(probe.getBoundingClientRect().width)
probe.remove()
```

An assumed width is how a working tip gets "fixed": a guess of 140px reported a clip that
the real text (100px) did not have, while a genuinely wide tip (307px) *would* have been cut
at the panel edge.

## Scope

`components/ui/Tooltip.tsx` stays the bare DaisyUI wrapper — the right component for a
tip in unclipped space, and the one most tips should use. Use `PortalTooltip` **only**
where something clips.

**If a tip is invisible in a panel, suspect the container before the markup.** Moving a
tip to a different trigger hides the class of bug without fixing it; the next tip in the
same panel fails the same way.

## What to do when a tooltip "isn't there"

In one evaluation:

```js
const tip = document.querySelector('[data-tip="your expected text"]');
getComputedStyle(tip, '::before').content         // is the text present?
// then walk up and list anything that clips:
let el = tip; const clippers = [];
while (el && el !== document.body) {
  const s = getComputedStyle(el);
  if (s.overflow !== 'visible' || s.overflowX !== 'visible' || s.overflowY !== 'visible')
    clippers.push(el.className);
  el = el.parentElement;
}
```

Text present + clippers found = clipped, not missing.

## Related

- [[atlas/ui/components/ui/PortalTooltip]] — the component
- [[dev-notes/message-center|Message Center]] — a neighbouring surface with the same panel shape
