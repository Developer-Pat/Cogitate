---
title: WorkflowEditor
type: atlas-component
path: frontend/src/components/features/workflows/WorkflowEditor.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# WorkflowEditor

**Path**: `frontend/src/components/features/workflows/WorkflowEditor.tsx`
**Last Updated**: 2026-08-01

## Purpose

Modal dialog for editing and customizing a workflow template's **metadata** (name, description, category, tags, public visibility, customizability). It renders as a fixed full-screen overlay (`fixed inset-0 z-50`) with a centered modal panel, an overlay backdrop that closes the modal on click, and Cancel / Save Changes actions.

The component does **not** edit workflow steps or configuration — `WorkflowTemplate.steps`, `inputs`, `outputs`, and `metadata` are carried through unchanged (the merge only overlays form fields). On submit it:

1. Merges form data into the template and stamps `updatedAt: new Date().toISOString()`.
2. Calls the `onValidate` prop with the updated template (an async validation hook supplied by the parent).
3. Calls `onSave(updatedTemplate)` only if validation resolves truthy; otherwise renders "Template validation failed" as an error.
4. Catch blocks surface thrown error messages as validation errors; validation warnings state exists but is never populated by this component (no code path sets `validationWarnings`).

**Export note**: the component is a **default export only** (`export default WorkflowEditor;`) — there is no named export. Import it as `import WorkflowEditor from '.../WorkflowEditor'`.

## Props Interface

Exact interface from `frontend/src/types/workflows.ts`:

```typescript
export interface WorkflowEditorProps {
  template: WorkflowTemplate;
  onSave: (template: WorkflowTemplate) => void;
  onCancel: () => void;
  onValidate: (template: WorkflowTemplate) => Promise<boolean>;
  className?: string;
}
```

Form values are typed with `WorkflowTemplateFormData`, inferred from the Zod schema:

```typescript
export type WorkflowTemplateFormData = z.infer<typeof workflowTemplateFormSchema>;
// schema fields: name, description, category, tags?, isPublic, isCustomizable
```

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `react-hook-form` (`useForm`) | Library | Form state, registration, dirty tracking (`isDirty`), `watch`/`setValue` for tags |
| `@hookform/resolvers` (`zodResolver`) | Library | Wires the Zod schema into react-hook-form (wrapped in `@ts-expect-error` due to resolver v3 / RHF v7 type mismatch) |
| `../../../types/workflows` | Types + schema | `WorkflowEditorProps`, `WorkflowTemplateFormData`, `workflowTemplateFormSchema` (Zod validation) |
| `zod` (via schema) | Library | Validation rules: `name` (1–100 chars), `description` (1–500), `category` (required), `tags` (string[], optional), `isPublic` (bool, default false), `isCustomizable` (bool, default true) |
| `React` (`useState`, `KeyboardEvent`) | Library | Local validation state; tag input key handling |

No stores, contexts, or direct API calls are used — persistence and validation are delegated to the parent through the `onSave`/`onValidate` props.

## Usage Example

Used by the Workflow Templates page (`frontend/src/pages/WorkflowTemplates.tsx`):

```tsx
import WorkflowEditor from '../components/features/workflows/WorkflowEditor';

{showEditor && editingTemplate && (
  <WorkflowEditor
    template={editingTemplate}
    onCancel={handleCloseEditor}
    onSave={(template) => {
      if (editingTemplate) {
        updateTemplate(editingTemplate.id, template);
      } else {
        createTemplate(template);
      }
    }}
    onValidate={handleTemplateValidate}
  />
)}
```

## State Used

| State | Source | Purpose |
|---|---|---|
| `isValidating` | `useState<boolean>` | Disables the submit button and shows "Validating..." while `onValidate` runs |
| `validationErrors` | `useState<string[]>` | Rendered in a red error panel; set on validation failure or thrown errors |
| `validationWarnings` | `useState<string[]>` | Rendered in a yellow warning panel; initialized/reset but never populated |
| `errors`, `isDirty` | react-hook-form `formState` | Field-level Zod errors; `isDirty` gates the Save button and triggers the cancel confirmation |
| `watch`, `setValue` | react-hook-form | Reads/updates the `tags` array; `setValue(..., { shouldDirty: true })` marks the form dirty on tag changes |
| `currentTags` | Derived (`watch('tags')`) | Renders removable tag chips |

## Related Components

- `frontend/src/pages/WorkflowTemplates.tsx` — only consumer; renders `<WorkflowEditor>` inside a modal conditional and wires `onSave` to `updateTemplate`/`createTemplate` and `onValidate` to `handleTemplateValidate`.
- `frontend/src/components/features/workflows/WorkflowCard.tsx` — card view that triggers edit/preview/execute actions on a template.
- `frontend/src/components/features/workflows/WorkflowPreview.tsx` — read-only preview modal for the same template data.
- `frontend/src/components/features/workflows/WorkflowImport.tsx` — sibling import modal in the same workflow-templates UI.
- `frontend/src/components/features/workflows/WorkflowTemplateTable*.tsx` — table-based alternative views of workflow templates.
- `frontend/src/types/workflows.ts` — shared types (`WorkflowTemplate`, `WorkflowEditorProps`, `workflowTemplateFormSchema`).
