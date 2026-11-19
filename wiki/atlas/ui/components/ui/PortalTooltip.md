---
title: PortalTooltip
type: atlas-component
path: frontend/src/components/ui/PortalTooltip.tsx
confidence: high
updated: 2026-09-15
tags: [type/component, domain/atlas-ui]
---
# PortalTooltip

**Path**: `frontend/src/components/ui/PortalTooltip.tsx`
**Last Updated**: 2026-09-15

## Purpose

A tooltip that **escapes scroll containers**. Opt-in, and only for tips that live inside
a clipping ancestor.

DaisyUI's `.tooltip` renders its text in an absolutely-positioned `::before`, which is
**clipped by any ancestor with `overflow: auto | hidden`**. The sessions panel has five
such ancestors, so the session-name tip carried the correct text and never appeared:

```
beforeContent:     "Local Weather 10-Day Forecast"   ← correct
clippingAncestors: 5                                 ← never seen
```

This is not a styling bug and no CSS tweak fixes it — `overflow: visible` cannot be set
on a scroll container without breaking scrolling. The only way out is to render the tip
**outside** the clipping tree, hence a portal to `document.body` with `position: fixed`
coordinates.

## Why it is separate from ui/Tooltip

`components/ui/Tooltip.tsx` is a bare DaisyUI wrapper — the right component for a tip
in unclipped space. **This is the narrow exception for the ones that are clipped**, and
it is opt-in: nothing that lives in unclipped space goes through it.

## Props Interface

```typescript
interface PortalTooltipProps {
  content: string
  children: React.ReactNode
  side?: 'top' | 'bottom'   // a preference; flips when there is no room
  maxWidth?: number         // default 420
  disabled?: boolean
}
```

## Behaviour

| Concern | How it is handled |
|---|---|
| Clipping | `createPortal(…, document.body)` + `position: fixed` |
| Side | `MIN_ROOM` (64px) check against the viewport; `side` is only a preference |
| Horizontal | Centred on the anchor, then clamped inside the viewport (`maxWidth` capped at `vw - 16`) |
| Vertical | Placed by its top edge; above the anchor uses `translateY(-100%)` |
| Width | `maxWidth` clamped to the viewport so long text wraps rather than overflows |
| Stale tips | Hides on any scroll (`capture: true`, so panel-internal scrollers count) and on resize |
| Long text | `whiteSpace: pre-wrap`, `wordBreak: break-word`, `maxHeight: 40vh` |

## Usage Example

```tsx
<PortalTooltip content={session.title} side="bottom">
  <h3 className="truncate">{getTruncatedSessionTitle(session.title, 28)}</h3>
</PortalTooltip>
```

## Consumers

- [[atlas/ui/components/features/agentInteraction/SessionListItem]] — the full session
  title on hover; the display itself stays truncated
- [[atlas/ui/components/features/agentInteraction/PromptHistoryList]] — the longer cut of
  a past prompt (see that doc's three-tier rule)

## Related

- [[atlas/ui/components/ui/Tooltip]] — the DaisyUI wrapper, for unclipped contexts
- [[dev-notes/frontend/tooltip-clipping|Tooltip clipping]] — the finding, and why no CSS fix exists
