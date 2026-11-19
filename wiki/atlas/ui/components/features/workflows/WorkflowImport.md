---
title: WorkflowImport
type: atlas-component
path: frontend/src/components/features/workflows/WorkflowImport.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---

# WorkflowImport

**Path**: `frontend/src/components/features/workflows/WorkflowImport.tsx`
**Last Updated**: 2026-08-01

## Purpose

Modal dialog for importing workflow templates from files. The user clicks a dashed dropzone (or selects a file) to load a JSON template file, reviews a parsed preview (name, description, category, step count, author), chooses import options (overwrite existing template, include execution history), and submits. On submit the component validates the form via react-hook-form + Zod, builds a `WorkflowImportData` payload, and delegates the actual import to the `onImport` callback prop (the component itself makes no direct API call). Import source is **file upload only** — there is no JSON-paste textarea.

## Props Interface

```typescript
export interface WorkflowImportProps {
  onImport: (data: WorkflowImportData) => Promise<void>;
  onCancel: () => void;
  className?: string;
}
```

Supporting types (from `frontend/src/types/workflows.ts`):

```typescript
export interface WorkflowImportData {
  template: WorkflowTemplate;
  includeExecutions?: boolean;
  overwriteExisting?: boolean;
}

export interface WorkflowImportResponse {
  importedTemplate: WorkflowTemplate;
  message: string;
  warnings?: string[];
}
```

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `react` (`useState`, `useRef`) | Hook | Local state for `isImporting`, `importError`, `importedTemplate`; `fileInputRef` for the hidden file input |
| `react-hook-form` (`useForm`) | Library | Form state + submission for the import options checkboxes (`overwriteExisting`, `includeExecutions`) |
| `@hookform/resolvers/zod` (`zodResolver`) | Library | Bridges the Zod schema to react-hook-form; note the `@ts-expect-error` for v3/v7 type incompatibility |
| `workflowImportFormSchema` (from `frontend/src/types/workflows.ts`) | Zod schema | Validates form fields: `file: z.any()`, `overwriteExisting: z.boolean().default(false)`, `includeExecutions: z.boolean().default(false)` |
| `WorkflowImportProps`, `WorkflowImportFormData`, `WorkflowImportData`, `WorkflowTemplate` (from `frontend/src/types/workflows.ts`) | Types | Props / form / payload / template typings |
| `workflowService.importTemplate()` (in `frontend/src/services/domains/llm/workflowService.ts`) | Service (indirect) | Backend import endpoint: `POST /api/v1/workflows/templates/import` via `apiClient` — expected to be invoked by the `onImport` prop owner |

## Usage Example

```tsx
// Parent usage (see frontend/src/pages/WorkflowTemplates.tsx)
const [showImport, setShowImport] = useState(false);

{showImport && (
  <WorkflowImport
    onCancel={() => setShowImport(false)}
    onImport={async (_data) => {
      await refreshTemplates();
      setShowImport(false);
    }}
  />
)}
```

## State Used

| State | Type | Purpose |
|---|---|---|
| `isImporting` | `boolean` | Disables the submit button and shows "Importing..." while `onImport` is pending |
| `importError` | `string \| null` | User-facing error message (file type, parse, structure, or import failure) |
| `importedTemplate` | `ParsedTemplate \| null` | Parsed file preview (`name`, `description?`, `category?`, `steps?`, `author?`); drives the preview panel and gates submission |
| `fileInputRef` | `useRef<HTMLInputElement>` | Programmatically clicks the hidden `<input type="file">` from the dropzone |

## Import Flow & Validation

1. **File selection** — hidden `<input type="file" accept=".json,.yaml,.yml">`; extension checked client-side (`endsWith('.json' | '.yaml' | '.yml')`), else error "Please select a JSON or YAML file".
2. **Parsing** — `FileReader.readAsText` then `JSON.parse` for `.json`. YAML files are rejected with "YAML import is not yet supported. Please use JSON format." (no YAML parser is wired up yet). Parse errors surface as "Failed to parse file. Please check the file format."
3. **Structure check** — requires `name` and an array `steps`, else "Invalid workflow template format. Missing required fields."
4. **Submission** — `onSubmit` builds `WorkflowImportData` (`template`, `overwriteExisting`, `includeExecutions`) and awaits `onImport(importData)`; errors are captured into `importError`; `isImporting` reset in `finally`.

## Related Components

- `frontend/src/pages/WorkflowTemplates.tsx` — parent page that renders the modal and owns the `onImport`/`onCancel` handlers
- `frontend/src/components/features/workflows/WorkflowEditor.tsx` — sibling editor for create/edit of templates
- `frontend/src/components/features/workflows/WorkflowPreview.tsx` — sibling preview modal for a selected template
- `frontend/src/services/domains/llm/workflowService.ts` — `importTemplate()` service implementing the backend import call
- `frontend/src/types/workflows.ts` — shared workflow types, Zod schemas, and props interfaces
- `frontend/src/hooks/useWorkflowTemplates.ts` — hook (used by the parent) providing `refreshTemplates()` and template CRUD
