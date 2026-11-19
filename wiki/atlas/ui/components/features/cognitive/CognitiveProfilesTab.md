---
title: CognitiveProfilesTab
type: atlas-component
path: frontend/src/components/features/cognitive/CognitiveProfilesTab.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---

# CognitiveProfilesTab

**Path**: `frontend/src/components/features/cognitive/CognitiveProfilesTab.tsx`
**Last Updated**: 2026-08-01

## Purpose

CRUD table for **cognitive profile** configurations — named bundles of cognitive-pipeline strategy selectors (`context_builder`, `executor`, `response_formatter`) plus an optional linked memory profile. Cognitive profiles describe *capabilities / pipeline configuration* (how context is built, how execution is dispatched, how responses are formatted) — not agent roles or personas.

The component:

- Loads all cognitive profiles and all memory profiles in parallel on mount.
- Provides an inline "create" card (`+ New Profile`) that captures name, description, strategy selectors, and a memory profile picker.
- Renders profiles in a table with inline row editing (name, context builder, executor, response formatter, memory profile) and delete.
- Locks built-in profiles (`is_builtin`) — Edit/Delete buttons are hidden for them (shown with a 🔒 marker).
- Shows a spinner while loading and an error alert with a Dismiss button on any failed operation.

**Note**: the component edits `name`, `description`, `context_builder`, `executor`, `response_formatter`, and `memory_profile_id`. It does **not** edit `temperature`, system prompts, or the free-form `config` blob in the UI (those are service/API-level fields only).

## Props Interface

The component takes **no props** — it is a self-contained state-driven default export:

```tsx
export default function CognitiveProfilesTab()
```

The data shapes it operates on are imported from `CognitiveProfileService`:

```ts
/** Cognitive profile data from the API */
export interface CognitiveProfile {
  id: number;
  name: string;
  description?: string | null;
  context_builder: string;
  executor: string;
  response_formatter: string;
  memory_profile_id?: number | null;
  memory_profile_name?: string | null;
  config?: Record<string, unknown> | null;
  is_builtin: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

/** Payload for creating a cognitive profile */
export interface CognitiveProfileCreate {
  name: string;
  description?: string | null;
  context_builder?: string;
  executor?: string;
  response_formatter?: string;
  memory_profile_id?: number | null;
  config?: Record<string, unknown> | null;
}

/** Payload for updating a cognitive profile */
export interface CognitiveProfileUpdate {
  name?: string;
  description?: string | null;
  context_builder?: string;
  executor?: string;
  response_formatter?: string;
  memory_profile_id?: number | null;
  config?: Record<string, unknown> | null;
}
```

Strategy selector options surfaced in the UI:

| Field | Options |
|---|---|
| `context_builder` | `default`, `minimal`, `augmented` |
| `executor` | `default`, `fast`, `hybrid`, `stub` |
| `response_formatter` | `default`, `direct_yield`, `structured` |

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `useState`, `useEffect` | React hooks | Local component state; fetch-on-mount via `useEffect(..., [])` |
| `cognitiveProfileService` (`CognitiveProfileService`) | Domain service singleton | API client for cognitive profiles — `list()`, `create()`, `update(id, data)`, `delete(id)` against `/api/v1/cognitive-profiles` |
| `CognitiveProfile`, `CognitiveProfileCreate`, `CognitiveProfileUpdate` | Types | Data shapes for profiles and CRUD payloads (see above) |
| `memoryProfileService` (`MemoryProfileService`) | Domain service singleton | `list()` against `/api/v1/memory-profiles` to populate the memory profile pickers |
| `MemoryProfile` | Type | Memory profile shape (`id`, `name`, strategy/window/persistence fields) |
| `frontendLoggingService` | Logging service | `frontendLoggingService.error(source, message, err)` on all fetch/create/update/delete failures |

## Usage Example

```tsx
import CognitiveProfilesTab from '../../components/features/cognitive/CognitiveProfilesTab'

// Rendered as one of the tabs inside the cognitive pipeline page
function CognitivePipelinePage() {
  return (
    <div role="tabpanel">
      <CognitiveProfilesTab />
    </div>
  )
}
```

The component is mounted from `frontend/src/pages/CognitivePipeline.tsx`.

## State Used

| State | Type | Initial | Purpose |
|---|---|---|---|
| `profiles` | `CognitiveProfile[]` | `[]` | Rows rendered in the table |
| `memoryProfiles` | `MemoryProfile[]` | `[]` | Options for the memory profile `<select>` in create card and edit rows |
| `loading` | `boolean` | `true` | Spinner shown while initial fetch is in flight |
| `error` | `string \| null` | `null` | Error message shown in a dismissible `alert-error` banner |
| `editingId` | `number \| null` | `null` | Row id currently in inline-edit mode (only one at a time) |
| `showCreate` | `boolean` | `false` | Toggles the create-profile card; button text flips between `+ New Profile` and `Cancel` |
| `formData` | `CognitiveProfileCreate` | empty form (`name: ''`, selectors `'default'`, `memory_profile_id: null`) | Binds the create-card inputs |

## API Calls

All calls go through the `cognitiveProfileService` singleton (base path `/api/v1/cognitive-profiles`) via the shared `apiClient`:

| Operation | Call | HTTP |
|---|---|---|
| Initial load | `cognitiveProfileService.list()` + `memoryProfileService.list()` via `Promise.all` | `GET /api/v1/cognitive-profiles` (+ `GET /api/v1/memory-profiles`) |
| Create | `cognitiveProfileService.create(formData)` | `POST /api/v1/cognitive-profiles` |
| Update | `cognitiveProfileService.update(id, data)` | `PUT /api/v1/cognitive-profiles/:id` |
| Delete | `cognitiveProfileService.delete(id)` | `DELETE /api/v1/cognitive-profiles/:id` |

Every CRUD handler re-fetches data via `fetchData()` afterward. Edit-row inputs are read directly from the DOM via `document.getElementById` using ids like `ce-name-{id}`, `ce-cb-{id}`, `ce-ex-{id}`, `ce-rf-{id}`, `ce-mp-{id}`. Create is gated on a non-empty `name` (the button is disabled otherwise).

## Related Components

| Component | Path | Relationship |
|---|---|---|
| `CognitivePipeline` | `frontend/src/pages/CognitivePipeline.tsx` | Parent page that hosts this tab |
| `MemoryProfilesTab` | `frontend/src/components/features/cognitive/MemoryProfilesTab.tsx` | Sibling tab; manages the memory profiles this tab references |
| `PipelineConfigTab` | `frontend/src/components/features/cognitive/PipelineConfigTab.tsx` | Sibling tab for pipeline configuration |
| `AgentMemoryTab` | `frontend/src/components/features/cognitive/AgentMemoryTab.tsx` | Sibling tab for agent memory settings |
| `CognitiveProfileSelector` | `frontend/src/components/features/cognitive/CognitiveProfileSelector.tsx` | Sibling selector component for choosing a cognitive profile |
| `CognitiveProfileService` | `frontend/src/services/domain/CognitiveProfileService.ts` | API client backing this tab's CRUD |
| `MemoryProfileService` | `frontend/src/services/domain/MemoryProfileService.ts` | API client for the memory profile picker |
