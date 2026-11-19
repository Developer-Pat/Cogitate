---
title: WorkflowListCard
type: atlas-component
path: frontend/src/components/features/workflows/WorkflowListCard.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# WorkflowListCard

**Path**: `frontend/src/components/features/workflows/WorkflowListCard.tsx`
**Last Updated**: 2026-08-01

## Purpose
Card view of a workflow list — name with Default badge + workflow-count badge, description (2-line clamp), tag chips (max 5 + '+N more'), stats grid (workflows count / updated date), Edit/Delete buttons (stopPropagation), and created/updated footer.

## Props Interface
```typescript
interface WorkflowListCardProps {
  list: WorkflowList
  onSelect: (list: WorkflowList) => void
  onEdit: (list: WorkflowList) => void
  onDelete: (list: WorkflowList) => void
  isSelected?: boolean   // ring highlight when selected
  className?: string
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| WorkflowList | types/workflows | Data shape |

## Usage Example
```tsx
<WorkflowListCard list={l} onSelect={setSelected} onEdit={openEditor} onDelete={del} isSelected={l.id === selected?.id} />
```

## State Used
None — stateless.

## Related Components
- features/workflows/WorkflowTable.tsx — table view of same data
- features/workflows/WorkflowListEditor.tsx — edit action target