---
title: PermissionBadge
type: atlas-component
path: frontend/src/components/Tools/PermissionBadge.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# PermissionBadge

**Path**: `frontend/src/components/Tools/PermissionBadge.tsx`
**Last Updated**: 2026-08-01

## Purpose
Badge showing a permission level with color coding, optional label/tooltip, sized sm/md/lg.

## Props Interface
```typescript
interface PermissionBadgeProps {
  level: PermissionLevel
  showLabel?: boolean   // default true
  showTooltip?: boolean // default true
  size?: 'sm' | 'md' | 'lg'  // default 'sm'
  className?: string
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| PermissionLevel | types (permissions) | Level type |

## Usage Example
```tsx
<PermissionBadge level="admin" size="md" />
```

## State Used
None — stateless.

## Related Components
- Tools/ToolPermissionsManager.tsx — primary consumer
- Tools/CollectionPermissionRow.tsx — row display