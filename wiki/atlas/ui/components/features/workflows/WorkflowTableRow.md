---
title: WorkflowTableRow
type: atlas-component
path: frontend/src/components/features/workflows/WorkflowTableRow.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# WorkflowTableRow

**Path**: `frontend/src/components/features/workflows/WorkflowTableRow.tsx`
**Last Updated**: 2026-08-01

## Purpose
Single workflow-list row — selection checkbox, name (formatted date), hover-revealed action buttons (edit/delete via WorkflowTableActions).

## Props Interface
```typescript
interface WorkflowTableRowProps {
  list: WorkflowList
  isSelected: boolean
  onSelect: () => void
  onEdit: () => void
  onDelete: () => Promise<void>
  isLoading: boolean
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| WorkflowTableActions | Component (local) | Edit/delete buttons |
| WorkflowList | types/workflows | Row data |

## Usage Example
```tsx
<WorkflowTableRow list={row} isSelected={sel.has(row.id)} onSelect={...} onEdit={...} onDelete={...} isLoading={loading} />
```

## State Used
- showActions (hover state, local useState)

## Related Components
- features/workflows/WorkflowTable.tsx — owner
- features/workflows/WorkflowTableActions.tsx — action buttons