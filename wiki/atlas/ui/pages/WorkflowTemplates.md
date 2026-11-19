---
title: Workflow Templates
type: atlas-page
path: frontend/src/pages/WorkflowTemplates.tsx
confidence: high
updated: 2026-07-31
tags: [type/page, domain/atlas-ui]
---
# Workflow Templates

**Component**: `frontend/src/pages/WorkflowTemplates.tsx`
**Route**: `/workflow-templates` (`requiresAuth: true`, icon `template`, breadcrumb "Workflow Templates") — registered in `frontend/src/config/routes.ts` and lazy-loaded
**Last Updated**: 2026-07-31

## Purpose

Main page for discovering, managing, and executing workflow templates, and for managing user-defined "workflow lists" (named collections of workflows). It is organized into two tabs — **Templates** and **Workflow Lists** — each with its own grid/table view toggle, filtering, and CRUD flows. All template and list data is fetched through the workflow domain services (`workflowService`, `workflowListsService`) and held in local hook state; there is no global store involvement on this page.

## Key Features

- **Tabs**: "Templates" and "Workflow Lists" switch the page content and the header action button (Import Template + Create Template vs. Create List).
- **Templates tab**:
  - Grid/table view toggle (defaults to table).
  - Table view (`WorkflowTemplateTable`): client-side search (name/description/tag), category dropdown, workflow-type dropdown, tag-chip filter bar, sortable columns (name, category, workflow_type, version, updated_at, tags), and pagination (default 25 rows/page).
  - **Import Template** button opens the `WorkflowImport` modal (JSON file upload with client-side parse + preview; YAML import is not yet supported).
  - **Create Template** button opens the `WorkflowEditor` modal in create mode.
  - Row/card actions: select (opens `WorkflowPreview`), edit (opens `WorkflowEditor`), execute (fires workflow execution); the grid `WorkflowCard` also has an export action that currently only logs (not implemented).
  - Empty states ("No templates found") with a Create Template CTA; error banner when the template load fails.
- **Workflow Lists tab**:
  - Grid/table view toggle; tag filter chips (grid view only) derived from list tags.
  - **Create List** button opens `WorkflowListEditor`; rows/cards support select (preview), edit, and delete (confirm dialog).
  - `WorkflowListPreview` / `WorkflowListEditor` show the list's workflows and support add/remove membership; after mutations the page reloads the list's workflows and refreshes all lists.
- Template validation runs before save: `WorkflowEditor` calls `onValidate` → `POST /api/v1/workflows/templates/validate`; the returned `isValid` gates the save.
- All failures are logged client-side via `frontendLoggingService` (`frontend/src/services/frontendLoggingService.ts`).

## Components Used

| Component | Path | Purpose |
|---|---|---|
| PageContainer | `frontend/src/components/ui/PageContainer` | Page layout wrapper |
| PageBanner | `frontend/src/components/ui/PageBanner` | Page header with title, icon, tooltip, and tab-dependent action buttons (Import Template / Create Template / Create List) |
| WorkflowCard | `frontend/src/components/features/workflows/WorkflowCard` | Grid-view card for a template (select / edit / export / execute) |
| WorkflowTemplateTable | `frontend/src/components/features/workflows/WorkflowTemplateTable` | Table view of templates with internal sort, filter, and pagination state |
| WorkflowTemplateTableFilters | `frontend/src/components/features/workflows/WorkflowTemplateTableFilters` | Search input, category/type dropdowns, tag-chip filter bar, clear-filters button |
| WorkflowTemplateTableHeader | `frontend/src/components/features/workflows/WorkflowTemplateTableHeader` | Sortable column headers for the template table |
| WorkflowTemplateTableRow | `frontend/src/components/features/workflows/WorkflowTemplateTableRow` | Renders one template row with select / edit / execute (and optional delete) actions |
| WorkflowTablePagination | `frontend/src/components/features/workflows/WorkflowTablePagination` | Pagination controls + page-size selector |
| WorkflowPreview | `frontend/src/components/features/workflows/WorkflowPreview` | Modal preview of a selected template (execute / edit / close) |
| WorkflowEditor | `frontend/src/components/features/workflows/WorkflowEditor` | Modal for creating/editing a template; `onSave` → create/update, `onValidate` → validate endpoint |
| WorkflowImport | `frontend/src/components/features/workflows/WorkflowImport` | Modal that parses an uploaded JSON template file client-side (FileReader) and previews it; submits via page `onImport` handler |
| WorkflowListCard | `frontend/src/components/features/workflows/WorkflowListCard` | Grid-view card for a workflow list (select / edit / delete) |
| WorkflowTable | `frontend/src/components/features/workflows/WorkflowTable` | Table view of workflow lists (uses its own Filters / Header / Row / Actions / Pagination subcomponents) |
| WorkflowListPreview | `frontend/src/components/features/workflows/WorkflowListPreview` | Modal showing a list's workflows with add/remove membership actions |
| WorkflowListEditor | `frontend/src/components/features/workflows/WorkflowListEditor` | Modal for creating/editing a list and managing its member workflows |

## Hooks Used

| Hook | Path | Purpose |
|---|---|---|
| usePageTitle | `frontend/src/hooks/usePageTitle.tsx` | Sets the document title and meta description ("Workflow Templates" + subtitle) |
| useWorkflowTemplates | `frontend/src/hooks/useWorkflowTemplates.ts` | Loads templates + categories/tags on mount, holds filter/selection state, exposes `createTemplate`, `updateTemplate`, `deleteTemplate`, `refreshTemplates`, and a react-hook-form `form` (zod-validated) |
| useWorkflowLists | `frontend/src/hooks/useWorkflowLists.ts` | Loads workflow lists, derives unique tags, holds selection, exposes list CRUD plus `loadListWorkflows`, `addWorkflowToList`, `removeWorkflowFromList` |
| useWorkflowExecution | `frontend/src/hooks/useWorkflowExecution.ts` | `executeWorkflow` fires execution and manages status polling/SSE plumbing; the page only uses `executeWorkflow` and discards `polling` |
| useWorkflowValidation | `frontend/src/hooks/useWorkflowValidation.ts` | `validateTemplate` → validate endpoint; returns `{ isValid, errors, warnings }` |

Note: `useWorkflowExecution` also depends on `useNotifications` (`frontend/src/hooks/useNotifications.ts`). The data hooks use `react-hook-form` `useForm` with `zodResolver` and schemas from `frontend/src/types/workflows.ts`.

## Data Flow

1. **Load on mount**: `useWorkflowTemplates.loadTemplates()` runs `Promise.all([workflowService.getTemplates(), workflowService.getTemplateCategories()])`; `useWorkflowLists.loadLists()` runs `workflowListsService.getLists()`.
2. **Template list**: `getTemplates()` merges `GET /api/v1/workflows/templates` (simple templates) with `GET /api/v1/multi-agent/templates` (mapped to `WorkflowTemplate` shape: category "Multi-Agent", `workflowType 'multi_agent'`, complexity "complex", `isCustomizable: false`), deduplicating by id (multi-agent templates appear on both endpoints).
3. **Categories/tags**: `getTemplateCategories()` calls `GET /api/v1/workflows/templates/categories`. The backend returns `{ categories: [{id, name, ...}], tags: [{name, count}] }`; the service normalizes both to plain string arrays — categories via `name ?? id ?? ''`, tags via `name ?? ''`, empty strings filtered out. A legacy bare-array response yields empty arrays.
4. **Filtering split**: the hook's own filters (search, category, complexity, tags, isPublic, isCustomizable, sort) default to unfiltered, and the page never calls `setFilters`; it also passes a no-op `onFilterTagsChange` to the table. Effective filtering therefore happens client-side inside `WorkflowTemplateTable` (search, category, type, tag chips, sort, pagination) over the hook's `filteredTemplates`.
5. **Selection**: `handleTemplateSelect` → `setSelectedTemplate` + `WorkflowPreview` modal.
6. **Execute**: `handleTemplateExecute` → `useWorkflowExecution.executeWorkflow(templateId, {})` → `POST /api/v1/workflows/execute` (or `/api/v1/multi-agent/execute` for multi-agent), 120s timeout; backend status `started` is normalized to `running`. Errors are logged via `frontendLoggingService`.
7. **Create/Edit**: `WorkflowEditor` `onSave` → `createTemplate` (`POST /api/v1/workflows/templates`) or `updateTemplate` (`PUT /api/v1/workflows/templates/{id}`); each then calls `loadTemplates()` to refresh. `onValidate` → `validateTemplate` → `POST /api/v1/workflows/templates/validate`.
8. **Import**: `WorkflowImport` parses a `.json` file in the browser and calls the page's `onImport`, which currently only calls `refreshTemplates()` and closes the modal. The service method `workflowService.importTemplate` (`POST /api/v1/workflows/templates/import`) exists but is **not wired** to this modal.
9. **Lists**: `handleListSelect` → `loadListWorkflows(list.id)` → `GET /api/v1/workflow-lists/{id}/workflows`; membership changes call `POST`/`DELETE /api/v1/workflow-lists/{listId}/workflows/{workflowId}`, then reload the list's workflows and call `refreshLists()` to update counts. Delete uses a `confirm()` dialog before `DELETE /api/v1/workflow-lists/{id}`.

## State Management

No global store is read or written by this page. All state is local:

- Page-level `useState`: `activeTab`, `templateViewMode`, `viewMode`, modal visibility flags (`showPreview`, `showEditor`, `showImport`, `showListPreview`, `showListEditor`), and the entities being edited (`editingTemplate`, `editingList`).
- Hook-level `useState`: `useWorkflowTemplates` (templates, filteredTemplates, filters, loading, error, selectedTemplate, categories, tags), `useWorkflowLists` (workflowLists, filteredLists, loading, error, selectedList, selectedListWorkflows, tags, filterTags), `useWorkflowExecution` (executions, selectedExecution, loading, error, polling).

The broader workflows feature touches stores only indirectly: `WorkflowSelectionModal` (not imported by this page) uses `notificationStore`, and `useWorkflowExecution` may post notifications via `useNotifications`. Errors surface through local `error` state rendered as alert banners per tab.

## API Endpoints Called

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/workflows/templates` | List simple workflow templates (`workflowService.getTemplates`) |
| GET | `/api/v1/multi-agent/templates` | List multi-agent templates; merged and deduped with the simple list |
| GET | `/api/v1/workflows/templates/categories` | Categories + tags; backend returns `{categories: [{id, name, ...}], tags: [{name, count}]}` normalized to `string[]` by the service |
| POST | `/api/v1/workflows/templates` | Create a template (editor save → `createTemplate`) |
| PUT | `/api/v1/workflows/templates/{id}` | Update a template (`updateTemplate`) |
| DELETE | `/api/v1/workflows/templates/{id}` | Delete a template (exposed by the hook; not wired to page UI) |
| POST | `/api/v1/workflows/templates/validate` | Template validation (editor `onValidate`) |
| POST | `/api/v1/workflows/templates/import` | Import a template — service method exists but the page's import modal only refreshes the list and does not call it |
| POST | `/api/v1/workflows/execute` | Execute a simple workflow template (120s timeout; status `started` → `running`) |
| POST | `/api/v1/multi-agent/execute` | Execute a multi-agent workflow template |
| GET | `/api/v1/workflow-lists` | List workflow lists (response body wraps items in `workflow_lists`) |
| POST | `/api/v1/workflow-lists` | Create a workflow list |
| PUT | `/api/v1/workflow-lists/{id}` | Update a workflow list |
| DELETE | `/api/v1/workflow-lists/{id}` | Delete a workflow list |
| GET | `/api/v1/workflow-lists/{id}/workflows` | List workflows contained in a list |
| POST | `/api/v1/workflow-lists/{listId}/workflows/{workflowId}` | Add a workflow to a list |
| DELETE | `/api/v1/workflow-lists/{listId}/workflows/{workflowId}` | Remove a workflow from a list |

SSE (available via `frontend/src/services/sseClient.ts` `SSEClientFactory`, not actively consumed by this page): `GET /api/v1/workflows/{workflowId}/progress` streams workflow execution progress. `useWorkflowExecution` keeps SSE disconnect plumbing (`setSSEDisconnect`/`disconnectSSE`) but the page relies on the hook's interval polling of `GET /api/v1/workflows/{executionId}/status` (`workflowService.getExecution`).

## Related Pages

- [[WorkflowExecution]] — `/workflow-execution`: monitor workflows executed from this page
- [[Dashboard]] — `/`: system overview linking into workflow templates
- [[AgentTemplates]] — `/agents/templates`: separate template feature for agent profiles (distinct from workflow templates)
