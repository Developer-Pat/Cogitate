---
title: Tooltip
type: atlas-component
path: frontend/src/components/ui/Tooltip.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# Tooltip

**Path**: `frontend/src/components/ui/Tooltip.tsx`
**Last Updated**: 2026-08-01

## Purpose
A lightweight, dependency-free tooltip primitive. It wraps arbitrary `children` in a relative-positioned container and renders an absolutely positioned tooltip bubble (with a small rotated-square arrow) that appears on hover or focus, after a configurable delay, and disappears on mouse leave or blur. Styled with Tailwind utility classes (DaisyUI theme tokens `base-content` / `base-300`) and exposed to assistive tech via `role="tooltip"`.

## Props Interface
```typescript
interface TooltipProps {
  content: string
  children: React.ReactNode
  position?: 'top' | 'bottom' | 'left' | 'right'
  delay?: number
}
```

Defaults (from the function signature):
- `position = 'top'`
- `delay = 300` (ms)

`content` is rendered as the tooltip text; `children` is the trigger element the tooltip is anchored to. The tooltip bubble has `pointer-events-none` and `z-50`, so it never intercepts pointer events and always floats above surrounding content.

## Dependencies
| Dependency | Type | Purpose |
|---|---|---|
| `React` (`useState`) | library hook | Local state for visibility and the pending show-timeout id |
| `window.setTimeout` / `window.clearTimeout` | browser API | Implements the show `delay`; cancels the pending timer on hide |
| Tailwind CSS + DaisyUI theme tokens | styling | Positioning classes per `position`; `bg-base-300` bubble, `text-base-content` text |

No stores, services, or context are used.

## Usage Example
```tsx
import Tooltip from '../ui/Tooltip'

<Tooltip content="Refresh the dashboard" position="top" delay={500}>
  <button onClick={handleRefresh} className="btn btn-sm">↻</button>
</Tooltip>
```

## State Used
Local component state only (no global/store state):
- `isVisible: boolean` — whether the tooltip bubble is currently rendered. Set `true` by a `setTimeout` callback fired `delay` ms after mouse-enter/focus; set `false` immediately on mouse-leave/blur.
- `timeoutId: number | null` — handle of the pending show timer, so `hideTooltip` can `clearTimeout` it before it fires (prevents the tooltip from appearing after the pointer has already left).

Show triggers: `onMouseEnter` and `onFocus`. Hide triggers: `onMouseLeave` and `onBlur`.

## Related Components
- Consumers (all render `<Tooltip>`):
  - `frontend/src/components/ui/BackendStatusIndicator.tsx`
  - `frontend/src/components/features/agentInteraction/SessionListItem.tsx`
  - `frontend/src/components/features/providers/UsageDashboard.tsx`
  - `frontend/src/components/Tools/PermissionBadge.tsx`
  - `frontend/src/components/Tools/TagBadge.tsx`
  - `frontend/src/components/Tools/ToolsTableFilters.tsx`
  - `frontend/src/components/Tools/ToolsTableRow.tsx`
  - `frontend/src/components/help/HelpButton.tsx`
  - `frontend/src/components/CacheBuster.tsx`
  - `frontend/src/pages/Analytics.tsx`
  - `frontend/src/pages/Dashboard.tsx`
  - `frontend/src/pages/ProviderDashboard.tsx`
- Sibling primitives in the same directory: `frontend/src/components/ui/` (e.g. `BackendStatusIndicator.tsx`)
