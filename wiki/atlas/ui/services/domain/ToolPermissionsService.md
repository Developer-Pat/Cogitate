---
title: ToolPermissionsService
type: atlas-service
path: frontend/src/services/domain/ToolPermissionsService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# ToolPermissionsService

**Path**: `frontend/src/services/domain/ToolPermissionsService.ts`
**Type**: service (class + singleton)

## Purpose
Tool permission management — get/update permissions, per-collection set/remove, check permission level.

## Exported API
```typescript
export class ToolPermissionsService {
  getToolPermissions(toolId): Promise<...>
  updateToolPermissions(toolId, data): Promise<...>
  setCollectionPermission(toolId, collectionId, level): Promise<...>
  removeCollectionPermission(toolId, collectionId): Promise<...>
  checkPermission(level, required): boolean
}
export const toolPermissionsService = new ToolPermissionsService()
```

## Endpoints
- `/api/v1/tools` (permissions sub-resource)

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| apiClient | services/apiClient.ts | Requests |
| PermissionLevel | types | Level type |

## Usage Example
```tsx
await toolPermissionsService.setCollectionPermission(toolId, collId, 'execute')
```

## Data Flow / Notes
- checkPermission is a pure helper; backend permissions endpoints

## Related
- Tools/ToolPermissionsManager.tsx — consumer
- Tools/CollectionPermissionRow.tsx, AccessDeniedModal.tsx — display

## Deprecation / Obsolete Notes
Active (1 consumer). No deprecation markers.