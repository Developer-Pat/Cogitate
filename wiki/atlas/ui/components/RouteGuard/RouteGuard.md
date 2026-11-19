---
title: RouteGuard
type: atlas-component
path: frontend/src/components/RouteGuard/index.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# RouteGuard

**Path**: `frontend/src/components/RouteGuard/index.tsx`
**Last Updated**: 2026-08-01

## Purpose
Route-level access guard: redirects to `/` when the route requires auth and the user is unauthenticated; renders an Access Denied fallback (or custom fallback) when the user lacks required permissions.

## Props Interface
```typescript
interface RouteGuardProps {
  children: React.ReactNode
  route: RouteConfig        // from config/routes — requiresAuth, permissions
  userPermissions?: string[]
  isAuthenticated?: boolean // default true (no auth system yet)
  fallback?: React.ReactNode
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| Navigate, useLocation | react-router-dom | Redirect + location for `state.from` |
| RouteConfig | config/routes | Route auth/permission metadata |

## Usage Example
```tsx
<RouteGuard route={route}>
  <PageComponent />
</RouteGuard>
```

## State Used
None — pure props-driven gate.

## Related Components
- NavigationGuard.tsx — sibling unsaved-changes guard
- useRoutePermissions hook — permission wiring companion