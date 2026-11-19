---
title: WorkflowListEditor
type: atlas-component
path: frontend/src/components/features/workflows/WorkflowListEditor.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# WorkflowListEditor

**Path**: `frontend/src/components/features/workflows/WorkflowListEditor.tsx`
**Last Updated**: 2026-08-01

## Purpose

Modal dialog for creating or editing a workflow list. In create mode (`list === null`) it collects a name, description, and tag selection; in edit mode it additionally manages the list's member workflows — adding workflows through the `WorkflowSelectionModal` and removing them (with a `confirm()` prompt). The component is fully controlled via callbacks: it performs no API calls itself. All persistence is delegated to the parent through `onSave`, `onAddWorkflows`, and `onRemoveWorkflow`. Renders `null` when `isOpen` is `false`. Default export.

## Props Interface

```typescript
interface WorkflowListEditorProps {
  isOpen: boolean;
  list: WorkflowList | null;
  workflows: WorkflowInList[];
  availableTags: string[];
  onClose: () => void;
  onSave: (data: { name: string; description?: string; tags?: string[] }) => void;
  onAddWorkflows?: (workflowIds: string[]) => Promise<void>;
  onRemoveWorkflow?: (workflowId: string) => Promise<void>;
}
```

## Dependencies

| Dependency | Type | Purpose |
| --- | --- | --- |
| `useState` | React hook | Tracks `selectedTags` and `showAddModal` local state |
| `WorkflowList`, `WorkflowInList` | Types (`frontend/src/types/workflows.ts`) | Props typing for the list being edited and the workflows shown as members |
| `WorkflowSelectionModal` | Component (`frontend/src/components/features/workflows/WorkflowSelectionModal.tsx`) | Rendered in edit mode to pick workflows to add to the list |
| `onSave` / `onAddWorkflows` / `onRemoveWorkflow` | Callbacks (props) | All API side effects (create/update list, add/remove members) are delegated to the parent; the component makes no direct API calls |

## Usage Example

```tsx
import { useState } from 'react';
import WorkflowListEditor from '../features/workflows/WorkflowListEditor';
import type { WorkflowList, WorkflowInList } from '../../types/workflows';

function WorkflowListsPage() {
  const [editingList, setEditingList] = useState<WorkflowList | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [listWorkflows, setListWorkflows] = useState<WorkflowInList[]>([]);

  return (
    <WorkflowListEditor
      isOpen={editorOpen}
      list={editingList}
      workflows={listWorkflows}
      availableTags={['favorite', 'automation']}
      onClose={() => setEditorOpen(false)}
      onSave={(data) => {
        // e.g. POST /workflow-lists or PUT /workflow-lists/{id}
        console.log('Saved list data:', data);
        setEditorOpen(false);
      }}
      onAddWorkflows={async (workflowIds) => {
        // e.g. POST /workflow-lists/{id}/workflows
        console.log('Added workflows:', workflowIds);
      }}
      onRemoveWorkflow={async (workflowId) => {
        // e.g. DELETE /workflow-lists/{id}/workflows/{workflowId}
        console.log('Removed workflow:', workflowId);
      }}
    />
  );
}
```

## State Used

| State | Type | Initial value | Purpose |
| --- | --- | --- | --- |
| `selectedTags` | `string[]` | `list?.tags || []` | Currently toggled tags; sent with the save payload |
| `showAddModal` | `boolean` | `false` | Controls visibility of the `WorkflowSelectionModal` (edit mode only) |

Local state only — no global stores, context, or router state are used.

## Related Components

- `WorkflowSelectionModal` — `frontend/src/components/features/workflows/WorkflowSelectionModal.tsx` (child; workflow picker opened via the "Add Workflow" button, receives `listId`, `listName`, `existingWorkflowIds`, `onClose`, `onWorkflowsAdded`)
- `WorkflowListCard` — `frontend/src/components/features/workflows/WorkflowListCard.tsx` (sibling; card display of a workflow list, likely the launcher for this editor)
- `WorkflowListPreview` — `frontend/src/components/features/workflows/WorkflowListPreview.tsx` (sibling; read-only preview of a list)
- `WorkflowCard` — `frontend/src/components/features/workflows/WorkflowCard.tsx` (sibling; displays workflow template summaries)

## Save Behavior Notes

- Form fields (`name`, `description`) are **uncontrolled** inputs seeded via `defaultValue` from `list`; values are read at submit time from `FormData`, not from state.
- `name` is required; `description` is optional (empty string is coerced to `undefined`).
- `tags` come from `selectedTags` state, toggled by pill buttons; hidden when `availableTags` is empty ("No tags available").
- Submit calls `onSave({ name, description, tags })` and then `onClose()`. Button label switches between "Create List" (`list === null`) and "Save Changes".
- Removing a workflow requires `list` and `onRemoveWorkflow`; the user confirms via the native `confirm()` dialog before `onRemoveWorkflow(workflowId)` is awaited.
- Adding workflows requires `list` and `onAddWorkflows`; the selection modal closes only after the awaited callback resolves.
