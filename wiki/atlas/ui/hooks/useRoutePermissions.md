---
title: useRoutePermissions
type: atlas-hook
path: frontend/src/hooks/useRoutePermissions.ts
confidence: high
updated: 2026-08-01
tags: [type/hook, domain/atlas-ui]
---
# useRoutePermissions

**Path**: `frontend/src/hooks/useRoutePermissions.ts`
**Type**: hook

## Purpose
Route permission helpers — accessible routes, navigation routes, per-route access checks. Wraps config/routes.

## Exported API
```typescript
export const useRoutePermissions = () => ({
  accessibleRoutes, navigationRoutes, canAccessRoute, hasRoutePermission,
})
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| routes, getRouteByPath, hasRoutePermission | config/routes | Route config + permission checks |

## Usage Example
```tsx
const { canAccessRoute } = useRoutePermissions()
canAccessRoute('/agents') ? <NavLink .../> : null
```

## State / Data Flow
- useMemo over route config; canAccessRoute(path) checks permission

## Related
- components/layout/Sidebar.tsx — navigation filtering
- config/routes.ts — route/permission config