---
title: WorkflowTemplateTableRow
type: atlas-component
path: frontend/src/components/features/workflows/WorkflowTemplateTableRow.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# WorkflowTemplateTableRow

**Path**: `frontend/src/components/features/workflows/WorkflowTemplateTableRow.tsx`
**Last Updated**: 2026-08-01

## Purpose
Single workflow-template row — selection, name, category, type badge (multi_agent→secondary, advanced→accent, file-clerk→warning, others→ghost), version, tag chips, updated date, and edit/execute/delete actions.

## Props Interface
```typescript
interface Props {
  template: WorkflowTemplate
  isSelected: boolean
  onSelect: () => void
  onEdit: () => void
  onExecute: () => void
  onDelete?: () => void
  isLoading: boolean
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| WorkflowTemplate | types/workflows | Template row data |

## Usage Example
```tsx
<WorkflowTemplateTableRow template={t} isSelected={sel} onSelect={...} onEdit={...} onExecute={...} onDelete={...} isLoading={false} />
```

## State Used
- Hover/action state (local)

## Related Components
- features/workflows/WorkflowTemplateTable.tsx — owner table
- features/workflows/WorkflowTemplateTableFilters.tsx — sibling filter bar