---
title: HelpButton
type: atlas-component
path: frontend/src/components/help/HelpButton.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# HelpButton

**Path**: `frontend/src/components/help/HelpButton.tsx`
**Last Updated**: 2026-08-01

## Purpose
Context-aware help button — dispatches an `open-help-modal` CustomEvent that the HelpModal right-drawer listens for. The `context` prop maps to `wiki/help/` pages (matched by frontmatter category). Renders a HelpCircle icon + 'Help' label.

## Props Interface
```typescript
export interface HelpButtonProps {
  context?: string      // wiki help context id; default 'help_page'
  className?: string
  tooltipPosition?: 'top' | 'bottom' | 'left' | 'right'
  size?: 'sm' | 'md' | 'lg'   // default 'md'
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| HelpCircle | lucide-react | Button icon |
| window.dispatchEvent | DOM | `open-help-modal` CustomEvent (detail: { context, documentTitle, timestamp }) |

## Usage Example
```tsx
<HelpButton context="agent-profiles" size="sm" />
```

## State Used
None — fires an event, no local state.

## Related Components
- help/HelpModal.tsx — listens for `open-help-modal`, renders wiki help in right drawer