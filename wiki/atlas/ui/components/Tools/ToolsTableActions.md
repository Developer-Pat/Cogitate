---
title: ToolsTableActions
type: atlas-component
path: frontend/src/components/Tools/ToolsTableActions.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# ToolsTableActions

**Path**: `frontend/src/components/Tools/ToolsTableActions.tsx`
**Last Updated**: 2026-08-01

## Purpose
Row action menu for the tools table — duplicate, add-to-collection (opens AddToCollectionModal), permissions manager (opens ToolPermissionsManager).

## Props Interface
```typescript
interface ToolsTableActionsProps {
  tool: Tool
  onDuplicate: () => void
  isLoading: boolean
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| AddToCollectionModal | features/collections | Add-to-collection flow |
| ToolPermissionsManager | Tools/ToolPermissionsManager.tsx | Permissions flow |
| Tool | types/tools | Tool data |

## Usage Example
```tsx
<ToolsTableActions tool={tool} onDuplicate={duplicate} isLoading={busy} />
```

## State Used
- showAddToCollection, showPermissionsManager (local)

## Related Components
- Tools/ToolsTableRow.tsx — hosts these actions
- features/collections/AddToCollectionModal.tsx