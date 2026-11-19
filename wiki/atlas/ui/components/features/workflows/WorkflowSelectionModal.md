---
title: Workflow Selection Modal
type: atlas-component
path: frontend/src/components/features/workflows/WorkflowSelectionModal.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# Workflow Selection Modal

**Path**: `frontend/src/components/features/workflows/WorkflowSelectionModal.tsx`
**Last Updated**: 2026-08-01

## Purpose

Modal dialog for selecting workflows to add to a workflow list (a user-curated
collection of workflow templates). It loads all available workflow templates,
lets the user search and filter them, multi-select with checkboxes, and reports
the chosen IDs back to the caller via a callback. The modal itself performs no
list-mutation API calls — the caller owns persistence.

Per its source docstring: "Modal dialog for selecting workflows to add to a
workflow list. Supports search, filtering, and multi-select."

## Props Interface

```typescript
interface WorkflowSelectionModalProps {
  listId: string
  listName: string
  existingWorkflowIds: string[]
  onClose: () => void
  onWorkflowsAdded: (workflowIds: string[]) => void
}
```

Notes:

- `listId` is destructured as `_listId` and never used — the modal makes no
  direct API calls against the workflow-list endpoints; the caller performs the
  actual "add to list" call after receiving `onWorkflowsAdded`.
- `existingWorkflowIds` — IDs already in the target list; matching templates are
  excluded from the picker and counted in the "already in list" display.
- `onWorkflowsAdded` — invoked with the selected workflow IDs on save.

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `workflowService` (`../../../services/domains/llm/workflowService`) | Service singleton | `getTemplates()` loads all workflow templates on mount |
| `useNotificationStore` (`../../../stores/notificationStore`) | Zustand store selector | `addNotification` for error/warning/success toasts |
| `WorkflowTemplate` (`../../../types/workflows`) | Type | Shape of each row in the picker list |
| React `useState` / `useEffect` / `useMemo` | Hooks | Local state, mount-time load, filtered derivation |

### Data Source — `workflowService.getTemplates()`

The modal calls only `getTemplates()`, which internally fetches two endpoints in
parallel and merges/dedupes the results by `id`:

- `GET /api/v1/workflows/templates` — simple templates (response wrapped as
  `{ templates: [...] }`)
- `GET /api/v1/multi-agent/templates` — multi-agent templates (bare array,
  normalized to `WorkflowTemplate` with `category: 'Multi-Agent'`,
  `version: '1.0.0'`, `author: 'System'`, and `workflowType` defaulting to
  `'multi_agent'`)

Deduplication exists because multi-agent templates appear in both endpoints.
The merged list is returned as `ApiResponse<WorkflowTemplate[]>`.

## Usage Example

The modal is composed by both `WorkflowListEditor` and `WorkflowListPreview`
(siblings in `components/features/workflows/`). Real usage from
`WorkflowListEditor.tsx`:

```tsx
{list && showAddModal && (
  <WorkflowSelectionModal
    listId={list.id}
    listName={list.name}
    existingWorkflowIds={existingWorkflowIds}
    onClose={() => setShowAddModal(false)}
    onWorkflowsAdded={handleAddWorkflows}
  />
)}
```

The parent's `handleAddWorkflows` performs the actual API call that persists the
selected workflow IDs to the list — the modal only notifies.

## State Used

Local `useState`:

| State | Type | Purpose |
|---|---|---|
| `workflows` | `WorkflowTemplate[]` | All templates loaded from `getTemplates()` |
| `isLoading` | `boolean` | Mount-time load flag; renders a spinner backdrop while true |
| `searchQuery` | `string` | Free-text search box value |
| `categoryFilter` | `string` | Category dropdown value (`''` = all) |
| `selectedWorkflowIds` | `string[]` | Checkbox multi-select set |
| `categories` | `string[]` | Unique categories extracted from loaded templates (drives the filter dropdown) |

Derived:

- `filteredWorkflows` (`useMemo` over `workflows`, `searchQuery`,
  `categoryFilter`, `existingWorkflowIds`): excludes templates whose `id` is in
  `existingWorkflowIds`; search matches `name`, `description`, or any `tag`
  (case-insensitive substring); category is an exact match.

External store: `useNotificationStore((state) => state.addNotification)`.

## Search / Filter / Selection Behavior

- **Exclusion**: workflows already in the list are never shown.
- **Search**: case-insensitive substring against `name`, `description`, and `tags`.
- **Category filter**: exact `workflow.category` match; the dropdown is only
  rendered when `categories.length > 0`.
- **Select All / Deselect All**: act on the currently filtered (visible) set.
- **Empty state**: "All workflows are already in this list" when every loaded
  template is excluded; otherwise "No workflows match your search criteria"; a
  "Clear Filters" button appears when `searchQuery` or `categoryFilter` is set.
- **Save**: with no selection → warning toast "Please select at least one
  workflow" and abort; otherwise a success toast "Selected N workflow(s) to add"
  and `onWorkflowsAdded(selectedWorkflowIds)` is called. The surrounding
  `try/catch` only guards the (synchronous, notification-based) callback — no
  API call happens here.

## UI Structure

- **Loading state**: full-screen fixed backdrop (`z-[9999]`) with a centered
  spinner panel.
- **Shell**: `fixed inset-0 bg-black/50` backdrop; centered panel with daisyUI
  `bg-base-200`, width via CSS vars `--dialog-width-md` / `--dialog-width-full`,
  `max-h-[80vh] overflow-y-auto`.
- **Header** (sticky top): "Add Workflows to List" title + `Add workflows to
  "{listName}"` subtitle; X close button (`aria-label="Close"`, calls
  `onClose`).
- **Filters section**: search input ("Search by name, description, or tags..."),
  category select ("All Categories" + extracted categories), and an actions row
  showing "Showing N workflow(s) (M already in list)" with Select All / Deselect
  All ghost buttons.
- **Workflow list**: one checkbox row per filtered template — name, description,
  `v{version}`, category badge, up to 3 tag badges (+N overflow). Selected rows
  get `bg-primary/10 border-primary`.
- **Footer** (sticky bottom): Cancel (`onClose`) + primary "Add N Workflow(s)"
  button, disabled while nothing is selected.

## Related Components

- **Parents**: `components/features/workflows/WorkflowListEditor.tsx` and
  `components/features/workflows/WorkflowListPreview.tsx` — both compose this
  modal and pass `onWorkflowsAdded` to persist the selection.
- **Service**: `services/domains/llm/workflowService.ts` — `getTemplates()`
  data source.
- **Store**: `stores/notificationStore.ts` — `addNotification` toasts.
- **Types**: `types/workflows.ts` — `WorkflowTemplate` interface.
