---
title: Workflow Service
type: atlas-service
path: frontend/src/services/domains/llm/workflowService.ts
confidence: high
updated: 2026-08-10
tags: [type/service, domain/atlas-ui]
---
# Workflow Service

**Path**: `frontend/src/services/domains/llm/workflowService.ts`
**Type**: service

## Purpose

Service abstraction layer for workflow management with proper domain boundaries. Wraps the `/api/v1/workflows` (and `/api/v1/multi-agent/*`) backend endpoints behind a typed `IWorkflowService` interface, exposing template CRUD, template discovery & filtering (categories, tags, search), execution management (execute, status, list, cancel, retry), import/export, and validation. It also normalizes backend response shapes into the frontend `WorkflowTemplate` / `WorkflowExecution` formats (multi-agent template mapping, status `'started'` → `'running'`, category/tag object → string normalization).

## Exported API

Multi-export file — exports three symbols:

- `interface IWorkflowService` — the service contract (all method signatures below)
- `export const workflowService: IWorkflowService` — singleton instance (`new WorkflowService()`)
- `export default workflowService` — same singleton, exported for dependency injection

Exact method signatures (from `IWorkflowService`, implemented by `class WorkflowService implements IWorkflowService`):

```ts
// Template Management
getTemplates(): Promise<ApiResponse<WorkflowTemplate[]>>
getTemplateById(id: string): Promise<ApiResponse<WorkflowTemplate>>
createTemplate(template: Omit<WorkflowTemplate, 'id' | 'createdAt' | 'updatedAt'>): Promise<ApiResponse<WorkflowTemplate>>
updateTemplate(id: string, template: Partial<WorkflowTemplate>): Promise<ApiResponse<WorkflowTemplate>>
deleteTemplate(id: string): Promise<ApiResponse<{ message: string }>>

// Template Discovery & Filtering
getTemplateCategories(): Promise<ApiResponse<WorkflowCategoriesResponse>>
searchTemplates(query: string, filters?: Record<string, unknown>): Promise<ApiResponse<WorkflowTemplatesResponse>>

// Execution Management
executeTemplate(id: string, inputs: Record<string, unknown>, workflowType?: 'simple' | 'multi_agent'): Promise<ApiResponse<WorkflowExecution>>
getExecution(executionId: string): Promise<ApiResponse<WorkflowExecution>>
getExecutions(templateId?: string, triggerId?: string): Promise<ApiResponse<WorkflowExecutionsResponse>>
cancelExecution(executionId: string): Promise<ApiResponse<{ message: string }>>
retryExecution(executionId: string): Promise<ApiResponse<WorkflowExecution>>

// Import/Export
importTemplate(data: WorkflowImportData): Promise<ApiResponse<WorkflowImportResponse>>
exportTemplate(id: string, format: 'json' | 'yaml', includeExecutions?: boolean): Promise<ApiResponse<WorkflowExportResponse>>

// Validation
validateTemplate(template: WorkflowTemplate): Promise<ApiResponse<{ isValid: boolean; errors: string[]; warnings: string[] }>>
validateExecution(templateId: string, inputs: Record<string, unknown>): Promise<ApiResponse<{ isValid: boolean; errors: string[]; warnings: string[] }>>
```

## Endpoints

`basePath = '/api/v1/workflows'`; multi-agent endpoints live under `/api/v1/multi-agent`.

| Method | Endpoint | Used by |
|---|---|---|
| GET | `/api/v1/workflows/templates` | `getTemplates()` (simple templates) |
| GET | `/api/v1/multi-agent/templates` | `getTemplates()` (merged, deduped by id) |
| GET | `/api/v1/workflows/templates/{id}` | `getTemplateById()` (tried first) |
| GET | `/api/v1/multi-agent/templates/{id}` | `getTemplateById()` (fallback) |
| POST | `/api/v1/workflows/templates` | `createTemplate()` |
| PUT | `/api/v1/workflows/templates/{id}` | `updateTemplate()` |
| DELETE | `/api/v1/workflows/templates/{id}` | `deleteTemplate()` |
| GET | `/api/v1/workflows/templates/categories` | `getTemplateCategories()` |
| GET | `/api/v1/workflows/templates/search?q=...&<filter>=...` | `searchTemplates()` (query + filters as query params) |
| POST | `/api/v1/workflows/execute` (simple) / `/api/v1/multi-agent/execute` (multi_agent) | `executeTemplate()` — 120000 ms timeout |
| GET | `/api/v1/workflows/{executionId}/status` | `getExecution()` |
| GET | `/api/v1/workflows/executions` (`template_id` / `trigger_id` / `limit`) | `getExecutions(templateId?, triggerId?)` — reads `workflow_execution_history`; `trigger_id` filters scheduled runs (Automation page per-trigger history). Altered 2026-08-10: was hitting a non-existent route; now real. |
| POST | `/api/v1/workflows/executions/{executionId}/cancel` | `cancelExecution()` |
| POST | `/api/v1/workflows/executions/{executionId}/retry` | `retryExecution()` |
| POST | `/api/v1/workflows/templates/import` | `importTemplate()` |
| GET | `/api/v1/workflows/templates/{id}/export?format=...&includeExecutions=true` | `exportTemplate()` |
| POST | `/api/v1/workflows/templates/validate` | `validateTemplate()` |
| POST | `/api/v1/workflows/templates/{templateId}/validate-execution` | `validateExecution()` |

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `../shared/apiClient` (`apiClient`) | internal shared service | HTTP client (`EnhancedApiClient`) used for all GET/POST/PUT/DELETE calls; base URL from `VITE_API_URL` or `http://localhost:8000`; supports timeout, retries, auth token |
| `../../../types/index` (`ApiResponse`) | type | Generic `ApiResponse<T>` envelope (`data`, `status`, `timestamp`, `error`) returned by every method |
| `../../../types/workflows` | types | `WorkflowTemplate`, `WorkflowExecution`, `WorkflowTemplatesResponse`, `WorkflowExecutionsResponse`, `WorkflowCategoriesResponse`, `WorkflowImportResponse`, `WorkflowExportResponse`, `WorkflowImportData` |

## Usage Example

```ts
import { workflowService } from '../services/domains/llm/workflowService';

// Load templates + categories/tags in parallel
const [templates, categories] = await Promise.all([
  workflowService.getTemplates(),
  workflowService.getTemplateCategories()
]);

// Execute a template as multi-agent (routes to /api/v1/multi-agent/execute)
const exec = await workflowService.executeTemplate(
  templateId,
  { initial_message: 'Hello' },
  'multi_agent'
);
```

## Data Flow / Notes

- **`getTemplates()`** fetches simple (`/api/v1/workflows/templates`) and multi-agent (`/api/v1/multi-agent/templates`) templates in parallel, maps multi-agent records into the frontend `WorkflowTemplate` shape (category `'Multi-Agent'`, version `'1.0.0'`, author `'System'`, empty steps/inputs/outputs, synthetic timestamps), then deduplicates by `id` — multi-agent templates appear in both endpoints.
- **`getTemplateById()`** tries the simple endpoint first; if no data, falls back to the multi-agent endpoint with the same shape mapping.
- **`getTemplateCategories()` normalization**: the backend returns `{ categories: [{id, name, description, template_count}], tags: [{name, count}] }` objects, but `WorkflowCategoriesResponse` expects `string[]`. The service maps objects to name strings (`c.name ?? c.id ?? ''` / `t.name ?? ''`) and filters empties. A legacy array-shaped response yields empty arrays. Before this fix the raw objects flowed through, causing 'Objects are not valid as a React child' and duplicate-key errors in `WorkflowTemplateTableFilters`; verified with 383 passing tests.
- **`executeTemplate()`** posts `{ template_id, initial_message, inputs }` with a 120 s timeout, then transforms the backend response: status `'started'` → `'running'`, id taken from `workflow_id`, execution time computed from `started_at`/`completed_at` (seconds), plus a synthetic single-element `stepExecutions` array and initial `logs` entry.
- **`getExecution()`** hits `/{executionId}/status` and normalizes status the same way, extracts the error from `error` / `execution_result.error_details.message` / `execution_result.error`, maps `execution_result` into `stepExecutions`/`logs`, and uses the dedicated `outputs` field (not `execution_result`) for outputs.
- The service is instantiated once (`new WorkflowService()`) and exported both as a named const (`workflowService`) and as default (dependency injection). It is also re-exported from `frontend/src/services/index.ts`.

## Related

- `frontend/src/hooks/useWorkflowTemplates.ts` — primary consumer; wraps `getTemplates`, `getTemplateCategories`, `createTemplate`, `updateTemplate`, `deleteTemplate` with filter/selection state, react-hook-form, and zod validation (`workflowTemplateFormSchema`).
- `frontend/src/hooks/useWorkflowExecution.ts` — uses `workflowService` for execution lifecycle.
- `frontend/src/hooks/useWorkflowValidation.ts` — uses `workflowService` for validation.
- `frontend/src/components/features/workflows/WorkflowSelectionModal.tsx` — imports `workflowService`.
- `frontend/src/pages/WorkflowTemplates.tsx` — template management page, driven by `useWorkflowTemplates`.
- `frontend/src/pages/WorkflowExecution.tsx` — execution page, also uses `useWorkflowTemplates`.
- `frontend/src/services/index.ts` — services barrel; imports and re-exports `workflowService` and type `IWorkflowService`.

## Deprecation / Obsolete Notes

- **Not deprecated.** No `@deprecated`, "deprecated", "legacy", or "unused" markers in the source. The only "Legacy" occurrence is a code comment about an old array-shaped categories response inside `getTemplateCategories()` — that describes a historical API response format, not a deprecation of the service itself.
- **Actively consumed**: imported by 3 hooks (`useWorkflowTemplates`, `useWorkflowExecution`, `useWorkflowValidation`), 1 component (`WorkflowSelectionModal`), and the services barrel (`services/index.ts`); the `WorkflowTemplates` and `WorkflowExecution` pages consume it via the hooks. The zero-consumer concern does not apply.
- Recent changes are maintenance-only: the categories/tags normalization, tsc error fixes, and ESLint `no-explicit-any` cleanups.

## Retention (the run windows)

`getRetention()` / `updateRetention(partial)` / `pruneRetention(dryRun = true)` wrap
`GET` / `PUT /api/v1/workflows/retention` and `POST /api/v1/workflows/retention/prune`. The policy
lives in the app settings, so these read and write CONFIG rather than restating it: a **preview**
returns the same counts and bytes an apply would and changes nothing, and an apply sends
`confirm=true` — the endpoint refuses to act without it. Consumed by
[[atlas/ui/hooks/useWorkflowRetention|useWorkflowRetention]] via
[[atlas/ui/components/features/workflows/RetentionCard|RetentionCard]].
