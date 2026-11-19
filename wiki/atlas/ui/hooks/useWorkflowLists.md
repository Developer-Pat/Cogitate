---
title: useWorkflowLists
type: atlas-hook
path: frontend/src/hooks/useWorkflowLists.ts
confidence: high
updated: 2026-08-01
tags: [type/hook, domain/atlas-ui]
---
# useWorkflowLists

**Path**: `frontend/src/hooks/useWorkflowLists.ts`
**Type**: hook

## Purpose

`useWorkflowLists` manages workflow-list state for the Workflow Template Management UI. It loads lists from the backend through the LLM-domain `workflowListsService` (`frontend/src/services/domains/llm/workflowListsService.ts`, REST calls against `/api/v1/workflow-lists`), exposes client-side tag filtering (match-any semantics), list selection plus per-list workflow loading, and full CRUD for lists along with add/remove of workflows to/from a list. It also owns the `react-hook-form` instance used for the list-create form.

## Exported API

The hook takes no arguments and returns the following shape (exact interface from source):

```ts
interface UseWorkflowListsReturn {
  workflowLists: WorkflowList[];
  filteredLists: WorkflowList[];
  loading: boolean;
  error: string | null;
  tags: string[];
  filterTags: string[];
  setFilterTags: (tags: string[]) => void;
  refreshLists: () => Promise<void>;
  selectedList: WorkflowList | null;
  setSelectedList: (list: WorkflowList | null) => void;
  selectedListWorkflows: WorkflowInList[];
  loadListWorkflows: (listId: string) => Promise<void>;
  createList: (data: WorkflowListCreate) => Promise<void>;
  updateList: (id: string, data: WorkflowListUpdate) => Promise<void>;
  deleteList: (id: string) => Promise<void>;
  addWorkflowToList: (listId: string, workflowId: string) => Promise<void>;
  removeWorkflowFromList: (listId: string, workflowId: string) => Promise<void>;
  form: unknown; // UseFormReturn<WorkflowListCreate>
}
```

Internal state (single `useState<WorkflowListState>`):

```ts
interface WorkflowListState {
  workflowLists: WorkflowList[];
  filteredLists: WorkflowList[];
  loading: boolean;
  error: string | null;
  selectedList: WorkflowList | null;
  selectedListWorkflows: WorkflowInList[];
  tags: string[];
  filterTags: string[];
}
```

Data types (`frontend/src/types/workflows.ts`):

```ts
export interface WorkflowList {
  id: string;
  name: string;
  description?: string;
  user_key: string;
  workflow_ids: string[];
  workflow_count: number;
  is_default: boolean;
  tags?: string[];
  created_at: string;
  updated_at: string;
}

export interface WorkflowListCreate {
  name: string;
  description?: string;
  user_key?: string;
  workflow_ids?: string[];
  is_default?: boolean;
  tags?: string[];
}

export interface WorkflowListUpdate {
  name?: string;
  description?: string;
  workflow_ids?: string[];
  is_default?: boolean;
  tags?: string[];
}

export interface WorkflowInList {
  template_id: string;
  name: string;
  description?: string;
  version: string;
  tags?: string[];
}
```

The hook delegates all I/O to `workflowListsService` (singleton `WorkflowListsService`, base path `/api/v1/workflow-lists`):

```ts
interface IWorkflowListsService {
  getLists(params?: { user_key?: string; tags?: string }): Promise<ApiResponse<WorkflowList[]>>;
  getListById(id: string): Promise<ApiResponse<WorkflowList>>;
  createList(data: WorkflowListCreate): Promise<ApiResponse<WorkflowList>>;
  updateList(id: string, data: WorkflowListUpdate): Promise<ApiResponse<WorkflowList>>;
  deleteList(id: string): Promise<ApiResponse<{ message: string }>>;
  getWorkflowsInList(id: string): Promise<ApiResponse<WorkflowInList[]>>;
  addWorkflowToList(listId: string, workflowId: string): Promise<ApiResponse<WorkflowList>>;
  removeWorkflowFromList(listId: string, workflowId: string): Promise<ApiResponse<WorkflowList>>;
}
```

## Dependencies

| Dependency | Type | Purpose |
| --- | --- | --- |
| `workflowListsService` (`../services/domains/llm/workflowListsService`) | LLM-domain service singleton | All REST calls: `getLists`, `createList`, `updateList`, `deleteList`, `getWorkflowsInList`, `addWorkflowToList`, `removeWorkflowFromList` |
| `apiClient` (`../services/apiClient`) | `EnhancedApiClient` singleton (used by the service) | HTTP layer (retries, logging) backing all service calls; `ApiResponse<T>` envelopes |
| `useForm` + `zodResolver` (`react-hook-form`, `@hookform/resolvers/zod`) | Form library / resolver | List-create form state; validated against `workflowTemplateFormSchema` |
| `workflowTemplateFormSchema` (`../types/workflows`) | Zod schema | Validation for the create form (`name` min 1/max 100, `description` min 1/max 500, `category` required, `tags`, `isPublic`, `isCustomizable`) |
| `WorkflowList`, `WorkflowListCreate`, `WorkflowListUpdate`, `WorkflowInList` (`../types/workflows`) | Types | Return shapes and parameter types |
| `useState`, `useEffect`, `useCallback` | React hooks | Single-state store, filter-effect + mount-load effect, memoized callbacks |

## Usage Example

```tsx
import { useWorkflowLists } from '../hooks/useWorkflowLists';
import type { WorkflowListCreate } from '../types/workflows';

function WorkflowListManager() {
  const {
    filteredLists,
    loading,
    error,
    tags,
    filterTags,
    setFilterTags,
    selectedList,
    setSelectedList,
    selectedListWorkflows,
    loadListWorkflows,
    createList,
    form
  } = useWorkflowLists();

  // Tag filter (match ANY selected tag); effect in the hook re-applies filtering
  const toggleTag = (tag: string) =>
    setFilterTags(
      filterTags.includes(tag)
        ? filterTags.filter(t => t !== tag)
        : [...filterTags, tag]
    );

  const handleCreate = (data: WorkflowListCreate) => {
    void createList(data); // on success: loadLists() re-syncs + form.reset()
  };

  const handleSelect = (listId: string) => {
    const list = filteredLists.find(l => l.id === listId) ?? null;
    setSelectedList(list); // clears selectedListWorkflows
    if (list) void loadListWorkflows(list.id);
  };

  return (
    <div>
      {tags.map(tag => (
        <button key={tag} onClick={() => toggleTag(tag)}>{tag}</button>
      ))}
      {loading && <p>Loading lists…</p>}
      {error && <p>{error}</p>}
      <ul>
        {filteredLists.map(list => (
          <li key={list.id} onClick={() => handleSelect(list.id)}>
            {list.name} ({list.workflow_count})
          </li>
        ))}
      </ul>
      <form onSubmit={form.handleSubmit(handleCreate)}>
        <input {...form.register('name')} />
        <button type="submit">Create list</button>
      </form>
    </div>
  );
}
```

## State / Data Flow

- **Single state object**: all data lives in one `useState<WorkflowListState>`; callbacks update it with `setState(prev => …)` spread merges.
- **Load on mount**: `useEffect(() => { loadLists(); }, [loadLists])`. `loadLists` calls `workflowListsService.getLists()`, sets `workflowLists` + `filteredLists`, and derives `tags` by collecting unique tags across all lists (via `Set`). On service error, `error` is set from `response.error?.message` or the thrown `Error` message; failures also fall back to generic messages ('Failed to load workflow lists', etc.).
- **Tag filtering**: `setFilterTags` only writes `filterTags`; a `useEffect` on `state.filterTags` calls `applyFilters`, which filters `workflowLists` to lists whose `tags` overlap `filterTags` with match-any semantics (`list.tags?.some(tag => filterTags.includes(tag))`). Empty `filterTags` shows all lists.
- **CRUD**: `createList` / `updateList` / `deleteList` set `loading = true, error = null`, call the service, and on success `await loadLists()` to re-sync (create also calls `form.reset()`; update additionally sets `selectedList` to the response data; delete clears `selectedList` and `selectedListWorkflows`). Failures set `error` and `loading = false`.
- **Selection**: `setSelectedList` sets `selectedList` and clears `selectedListWorkflows`. `loadListWorkflows(listId)` fetches member workflows via `getWorkflowsInList` and stores them in `selectedListWorkflows`; failures are logged to the console (no `error` state set).
- **Membership mutations**: `addWorkflowToList` / `removeWorkflowFromList` call the service, then `loadLists()` and reload the selected list's workflows; failures are console-logged.
- **No SSE**: this hook is REST-only via `apiClient`; no event/SSE wiring.

## Related

- `frontend/src/pages/WorkflowTemplates.tsx` — primary consumer (default import `useWorkflowLists`); uses the full CRUD/selection/filter API and the `form` for its list editor.
- `frontend/src/pages/WorkflowExecution.tsx` — consumes `workflowLists` (named import) to drive list-based selection mode.
- `frontend/src/services/domains/llm/workflowListsService.ts` — the service the hook delegates to (REST `/api/v1/workflow-lists`).
- `frontend/src/types/workflows.ts` — `WorkflowList*` types and `workflowTemplateFormSchema`.
- `frontend/src/hooks/useWorkflowExecution.ts`, `frontend/src/hooks/useWorkflowValidation.ts` — sibling hooks used alongside `useWorkflowLists` in `WorkflowTemplates.tsx`.
