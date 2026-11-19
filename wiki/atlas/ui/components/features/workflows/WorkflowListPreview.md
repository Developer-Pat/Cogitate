---
title: WorkflowListPreview
type: atlas-component
path: frontend/src/components/features/workflows/WorkflowListPreview.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# WorkflowListPreview

**Path**: `frontend/src/components/features/workflows/WorkflowListPreview.tsx`
**Last Updated**: 2026-08-01

## Purpose
Modal preview of a workflow list — shows list info + its member workflows with add/remove actions (async, optional) and an Edit entry point.

## Props Interface
```typescript
interface WorkflowListPreviewProps {
  isOpen: boolean
  list: WorkflowList
  workflows: WorkflowInList[]
  onClose: () => void
  onEdit: (list: WorkflowList) => void
  onAddWorkflows?: (workflowIds: string[]) => Promise<void>
  onRemoveWorkflow?: (workflowId: string) => Promise<void>
  className?: string
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| WorkflowList, WorkflowInList | types/workflows | Data shapes |

## Usage Example
```tsx
<WorkflowListPreview isOpen={previewOpen} list={selected} workflows={members} onClose={close} onEdit={openEditor} onAddWorkflows={addIds} onRemoveWorkflow={removeOne} />
```

## State Used
- Controlled by isOpen prop; add/remove are async callbacks

## Related Components
- features/workflows/WorkflowSelectionModal.tsx — add-workflows picker
- features/workflows/WorkflowListCard.tsx — opens this preview