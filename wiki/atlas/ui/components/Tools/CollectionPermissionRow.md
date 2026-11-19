---
title: CollectionPermissionRow
type: atlas-component
path: frontend/src/components/Tools/CollectionPermissionRow.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# CollectionPermissionRow

**Path**: `frontend/src/components/Tools/CollectionPermissionRow.tsx`
**Last Updated**: 2026-08-01

## Purpose
Single collection-permission row — collection name, level selector, remove action.

## Props Interface
```typescript
interface CollectionPermissionRowProps {
  permission: ToolPermissionSummary
  onPermissionChange: (collectionId: string, newLevel: PermissionLevel) => void
  onRemove: (collectionId: string) => void
  isLoading?: boolean
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| ToolPermissionSummary, PermissionLevel | types (permissions) | Data + level type |

## Usage Example
```tsx
<CollectionPermissionRow permission={p} onPermissionChange={setLevel} onRemove={remove} />
```

## State Used
None — controlled.

## Related Components
- Tools/ToolPermissionsManager.tsx — parent manager
- Tools/PermissionBadge.tsx — level badge display