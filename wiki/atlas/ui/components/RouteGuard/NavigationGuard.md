---
title: NavigationGuard
type: atlas-component
path: frontend/src/components/RouteGuard/NavigationGuard.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# NavigationGuard

**Path**: `frontend/src/components/RouteGuard/NavigationGuard.tsx`
**Last Updated**: 2026-08-01

## Purpose
Wraps children and blocks navigation while `when` is true — intercepts browser back/forward (popstate, with confirm dialog) and beforeunload (unsaved-changes prompt). Renders children unchanged.

## Props Interface
```typescript
interface NavigationGuardProps {
  children: React.ReactNode
  when?: boolean    // default false — guards active when true
  message?: string // default 'You have unsaved changes. Are you sure you want to leave?'
}
```

## Dependencies
None (window event listeners).

## Usage Example
```tsx
<NavigationGuard when={hasUnsavedChanges}>
  <MyForm />
</NavigationGuard>
```

## State Used
None — effects only.

## Related Components
- RouteGuard/index.tsx — sibling route-permission guard