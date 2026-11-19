---
title: MemoryProfilesTab
type: atlas-component
path: frontend/src/components/features/cognitive/MemoryProfilesTab.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---

# MemoryProfilesTab

**Path**: `frontend/src/components/features/cognitive/MemoryProfilesTab.tsx`
**Last Updated**: 2026-08-01

## Purpose

CRUD table for memory profile configurations, rendered as the "Memory Profiles" tab of the Cognitive Pipeline page (`CognitivePipeline.tsx`). It lists all memory profiles from the API in a table (Name, Strategy, Window, Persistence, Compaction, Summary, Built-in, Actions), lets the user create new profiles via an inline "+ New Profile" form, and edit/delete user-defined profiles in place.

Built-in profiles (`is_builtin === true`, e.g. the backend-seeded `conversational`, `quick-response`, `research-std`, `balanced-chat`, `code-gen`, `research-pro`, `system-admin` profiles) are displayed with a 🔒 lock in the "Built-in" column and cannot be edited or deleted — the Edit/Delete buttons are hidden for them. The component does not hardcode any profile names or part codes (e.g. `ctx-exe-fmt-mem`-style strategy identifiers); it renders whatever the API returns and the strategy select only offers `default`.

## Props Interface

The component takes **no props**:

```typescript
export default function MemoryProfilesTab()
```

The data shapes it operates on are defined in `frontend/src/services/domain/MemoryProfileService.ts`:

```typescript
/** Memory profile data from the API */
export interface MemoryProfile {
  id: number;
  name: string;
  description?: string | null;
  strategy: string;
  window_size: number;
  persistence: string;
  compaction_threshold?: number | null;
  summarization: boolean;
  config?: Record<string, unknown> | null;
  is_builtin: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

/** Payload for creating a memory profile */
export interface MemoryProfileCreate {
  name: string;
  description?: string | null;
  strategy?: string;
  window_size?: number;
  persistence?: string;
  compaction_threshold?: number | null;
  summarization?: boolean;
  config?: Record<string, unknown> | null;
}

/** Payload for updating a memory profile */
export interface MemoryProfileUpdate {
  name?: string;
  description?: string | null;
  strategy?: string;
  window_size?: number;
  persistence?: string;
  compaction_threshold?: number | null;
  summarization?: boolean;
  config?: Record<string, unknown> | null;
}
```

## Dependencies

| Dependency | Type | Purpose |
| --- | --- | --- |
| `memoryProfileService` (class `MemoryProfileService`) | Service singleton — `frontend/src/services/domain/MemoryProfileService.ts` | API client for memory-profile CRUD against base path `/api/v1/memory-profiles` |
| `frontendLoggingService` | Service — `frontend/src/services/frontendLoggingService` | Logs errors for failed list/create/update/delete operations (`'MemoryProfilesTab', 'Failed to ...'`) |
| `useState`, `useEffect` | React hooks | Local component state; fetches profile list on mount |

API calls made (all via `memoryProfileService` → `apiClient`):

| Method | Endpoint | When |
| --- | --- | --- |
| `list()` | `GET /api/v1/memory-profiles` | On mount and after every successful create/update/delete |
| `create(data)` | `POST /api/v1/memory-profiles` | "Create Profile" button in the new-profile form |
| `update(id, data)` | `PUT /api/v1/memory-profiles/:id` | "Save" button in an editing row |
| `delete(id)` | `DELETE /api/v1/memory-profiles/:id` | "Delete" button on a non-built-in row |

## Usage Example

```tsx
import MemoryProfilesTab from '../components/features/cognitive/MemoryProfilesTab'

// In CognitivePipeline.tsx — rendered as the "Memory Profiles" tab:
{activeTab === 'memory' && <MemoryProfilesTab />}
```

## State Used

| State | Type | Initial | Purpose |
| --- | --- | --- | --- |
| `profiles` | `MemoryProfile[]` | `[]` | Rows fetched from the API and rendered in the table |
| `loading` | `boolean` | `true` | Shows a DaisyUI spinner while fetching; gates the table render |
| `error` | `string \| null` | `null` | Error banner text (dismissible); set on failed list/create/update/delete |
| `editingId` | `number \| null` | `null` | Profile id currently in inline edit mode; `null` = no row editing |
| `showCreate` | `boolean` | `false` | Toggles the inline "+ New Profile" create form |
| `formData` | `MemoryProfileCreate` | `{ name: '', description: '', strategy: 'default', window_size: 50, persistence: 'memory', compaction_threshold: null, summarization: false }` | New-profile form fields |

Behavioral details:

- The create form offers: name (required, button disabled without it), description, strategy select (**only `default`**), window size number input, persistence select (`memory` | `sqlite`), compaction threshold number input (empty ⇒ `null`), and an "Enable summarization" checkbox.
- Inline edit mode uses **uncontrolled** inputs identified by DOM ids (`edit-name-{id}`, `edit-ws-{id}`, `edit-pers-{id}`, `edit-ct-{id}`, `edit-sum-{id}`); "Save" reads them via `document.getElementById`. The update payload includes name, window_size, persistence, compaction_threshold, and summarization — **strategy is not part of the update payload**.
- Built-in profiles (`is_builtin`) render 🔒, cannot be edited or deleted, and no Save/Edit/Delete actions are shown for them.

## Related Components

- Parent / usage: `frontend/src/pages/CognitivePipeline.tsx` (renders it as the `memory` tab alongside PipelineConfigTab, CognitiveProfilesTab, AgentMemoryTab)
- API service: `frontend/src/services/domain/MemoryProfileService.ts` (types + REST client)
- Sibling tabs: `frontend/src/components/features/cognitive/PipelineConfigTab.tsx`, `frontend/src/components/features/cognitive/CognitiveProfilesTab.tsx`, `frontend/src/components/features/cognitive/AgentMemoryTab.tsx`
