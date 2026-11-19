---
title: WorkflowPreview
type: atlas-component
path: frontend/src/components/features/workflows/WorkflowPreview.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# WorkflowPreview

**Path**: `frontend/src/components/features/workflows/WorkflowPreview.tsx`
**Last Updated**: 2026-08-01

## Purpose

Read-only modal dialog that previews a workflow template's full details and structure — template metadata (category, version, author, public/private status, complexity), tags, the ordered workflow steps with type badges, expected inputs, outputs, and execution history (counts and success rates) — before the user decides to edit or execute it. It is the "view" counterpart to WorkflowEditor: it renders the template exactly as stored (no editing controls) and delegates mutations to its parent via `onEdit` (open the editor) and `onExecute` (run the workflow). The Execute button is always enabled; the Edit button is disabled for templates where `isCustomizable` is false.

## Props Interface

```typescript
export interface WorkflowPreviewProps {
  template: WorkflowTemplate;
  onClose: () => void;
  onExecute: (templateId: string, inputs?: Record<string, unknown>) => void;
  onEdit: (template: WorkflowTemplate) => void;
  className?: string;
}
```

Note: `className` is destructured as `className: _className = ''` but is not used in the rendered output.

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `react` | package | JSX rendering; component is `React.FC<WorkflowPreviewProps>` |
| `../../../types/workflows` | type module | `WorkflowPreviewProps` plus the `WorkflowTemplate`, `WorkflowStep`, `WorkflowInput`, `WorkflowOutput`, and `WorkflowMetadata` shapes it renders |

No hooks, stores, services, or API calls — purely presentational.

## Usage Example

```tsx
import WorkflowPreview from '../components/features/workflows/WorkflowPreview';

// From WorkflowTemplates.tsx (page-level state)
{showPreview && selectedTemplate && (
  <WorkflowPreview
    template={selectedTemplate}
    onClose={handleClosePreview}
    onExecute={handleTemplateExecute}
    onEdit={handleTemplateEdit}
  />
)}
```

## State Used

None — the component is stateless (no `useState`, `useEffect`, or `useMemo`). All derived values (complexity badge color, step-type badge color, public/private badge color, formatted estimated duration) are computed inline via local helpers `getComplexityColor`, `getStepTypeColor`, and `getStatusColor`. Modal visibility and the selected template are owned by the parent page.

## Related Components

- `frontend/src/pages/WorkflowTemplates.tsx` — parent page; owns the `showPreview` / `selectedTemplate` state and renders the modal.
- `frontend/src/components/features/workflows/WorkflowEditor.tsx` — editing counterpart, opened via `onEdit`; takes `onSave`, `onCancel`, and `onValidate`. Preview is a read-only view; the editor is a mutable form.
- `frontend/src/components/features/workflows/WorkflowImport.tsx` — sibling modal on the same page (template import).
- `frontend/src/components/features/workflows/WorkflowCard.tsx` / `WorkflowListCard.tsx` / `WorkflowTemplateTable.tsx` — list views whose actions surface this preview.
