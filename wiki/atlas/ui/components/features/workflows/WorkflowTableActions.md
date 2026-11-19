---
title: WorkflowTableActions
type: atlas-component
path: frontend/src/components/features/workflows/WorkflowTableActions.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# WorkflowTableActions

**Path**: `frontend/src/components/features/workflows/WorkflowTableActions.tsx`
**Last Updated**: 2026-08-01

## Purpose
Row action buttons for the workflow (list) table — edit (pencil) and delete (trash with native confirm dialog). Disabled while loading.

## Props Interface
```typescript
interface WorkflowTableActionsProps {
  list: WorkflowList        // from types/workflows
  onEdit: () => void
  onDelete: () => Promise<void>
  isLoading: boolean
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| WorkflowList | types/workflows | Row data (name for confirm) |

## Usage Example
```tsx
<WorkflowTableActions list={row} onEdit={() => setEditing(row)} onDelete={() => del(row.id)} isLoading={deleting} />
```

## State Used
None — uses window.confirm for delete confirmation.

## Related Components
- features/workflows/WorkflowTable.tsx — owner table
- features/workflows/WorkflowTableRow.tsx — row hosting these actions