---
title: BadgeButton
type: atlas-component
path: frontend/src/components/ui/BadgeButton.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---

# BadgeButton

**Path**: `frontend/src/components/ui/BadgeButton.tsx`
**Last Updated**: 2026-08-01

## Purpose

Compact pill-style button used for secondary actions like Help, Create, Sessions, and Tools. Styled entirely from design tokens defined in `tokens.css` (`--badge-btn-*` variables) so it themes consistently across all DaisyUI themes. Renders a native `<button>` element with rounded corners, medium font weight, border, and hover/disabled states. Uncontrolled wrapper — all behavior (onClick, disabled, type) is delegated straight to the underlying button.

## Props Interface

```typescript
export interface BadgeButtonProps {
  children: React.ReactNode
  onClick?: () => void
  disabled?: boolean
  size?: 'sm' | 'md'
  className?: string
  title?: string
  'aria-label'?: string
  type?: 'button' | 'submit' | 'reset'
}
```

Defaults: `disabled = false`, `size = 'md'`, `className = ''`, `type = 'button'`. The `sm` size uses `--badge-btn-sm-*` tokens for padding and font size; `md` uses `--badge-btn-*` tokens.

## Dependencies

| Dependency | Type | Purpose |
|------------|------|---------|
| `react` | npm package | `React.ReactNode` type for `children`; JSX rendering |
| `tokens.css` design tokens | CSS variables (`--badge-btn-bg`, `--badge-btn-text`, `--badge-btn-border`, `--badge-btn-hover-bg`, `--badge-btn-radius`, `--badge-btn-padding-x/y`, `--badge-btn-font-size`, `--badge-btn-sm-*`, `--badge-btn-disabled-opacity`) | All visual styling — no component-level styles, no Tailwind theme coupling |

No hooks, stores, services, or context are used — the component is fully presentational.

## Usage Example

```tsx
import { BadgeButton } from '../../components/ui/BadgeButton'

<BadgeButton onClick={() => setShowHelp(true)}>Help</BadgeButton>

<BadgeButton size="sm" onClick={scrollBack} aria-label="Scroll back">‹</BadgeButton>

<BadgeButton disabled>Tools</BadgeButton>

<BadgeButton type="submit" className="mr-2">Create</BadgeButton>
```

## State Used

None. BadgeButton is stateless — it does not call `useState`, `useReducer`, or any other hooks. All state lives in the parent via the `onClick` callback.

## Related Components

- `frontend/src/components/features/agentInteraction/ChatInterface.tsx` — uses BadgeButton for in-chat actions
- `frontend/src/components/features/agentInteraction/SessionActions.tsx` — uses BadgeButton for session action buttons
- `frontend/src/components/features/agentInteraction/SessionManager.tsx` — uses BadgeButton for session management controls
- `frontend/src/pages/AgentInteraction.tsx` — page-level usage (Help/Create/Sessions/Tools buttons)
- `frontend/src/components/ui/` — sibling UI primitives sharing the same design-token styling conventions
