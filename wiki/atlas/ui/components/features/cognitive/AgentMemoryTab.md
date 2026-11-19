---
title: AgentMemoryTab
type: atlas-component
path: frontend/src/components/features/cognitive/AgentMemoryTab.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# AgentMemoryTab

**Path**: `frontend/src/components/features/cognitive/AgentMemoryTab.tsx`
**Last Updated**: 2026-08-01

## Purpose

Memory profile tab for deep agents ("Agent Memory" tab on the Cognitive Pipeline page). Loads the list of provisioned deep agents from the server and shows a per-agent memory card containing: session/turn counts, summary count, fact count, and vector-index status (the badge row). Expanding a card (`Details`) reveals maintenance actions: Clear Sessions, Clear All Memory, Prune (30d), Clear Vectors, plus a facts-extracted note. An Export button downloads the agent's memory as JSON.

The component takes **no props** — it is self-contained. Agents are fetched dynamically from the backend and keyed by their `folder` (the per-agent directory, e.g. the deep-agent folder that backs the per-agent `cognitive_memory.db` and `agent_{id}:facts` fact store); the UI surfaces those facts via the `fact_count` field of each agent's status payload.

## Props Interface

No props. The component is exported as a default function component with an empty signature:

```typescript
export default function AgentMemoryTab()
```

It is rendered by the parent page without any props (see Related Components).

Internal data shapes (defined in this file, not exported):

```typescript
interface MemoryStatus {
  agent_folder: string
  has_cognitive_memory_db: boolean
  session_count: number
  turn_count: number
  has_summaries: boolean
  summary_count: number
  fact_count: number
  has_vector_index: boolean
  vector_turn_count: number
}

interface DeepAgent {
  folder: string
  name: string
  description: string
}
```

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `react` (`useEffect`, `useState`) | Hook | Load agents/statuses on mount and manage local UI state (agents, statuses, expanded, loading) |
| `useNotificationStore` (from `frontend/src/stores/notificationStore.ts`) | Zustand store | `addSuccess`/`addError` toasts for memory actions, prune, and export results. Note: referenced in this file without an explicit import statement |

### API calls (cognitive memory endpoints, base `/api/v1`)

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/v1/cognitive/memory/agents` | Load the list of deep agents (`DeepAgent[]`) on mount |
| `GET` | `/api/v1/cognitive/memory/{folder}/status` | Load per-agent `MemoryStatus` for each agent folder |
| `DELETE` | `/api/v1/cognitive/memory/{folder}/clear/sessions` | Clear session history for an agent (via `doAction`) |
| `DELETE` | `/api/v1/cognitive/memory/{folder}/clear/all` | Clear all memory for an agent (via `doAction`) |
| `POST` | `/api/v1/cognitive/memory/prune` | Prune entries older than 30 days; body `{ "max_days": 30 }` |
| `DELETE` | `/api/v1/cognitive/vectors/{folder}/all` | Clear the agent's vector index (shown only when `has_vector_index`) |
| `GET` | `/api/v1/cognitive/memory/{folder}/export` | Fetch agent memory as JSON; downloaded client-side as `{folder}-memory-export.json` |

## Usage Example

```tsx
// Rendered by the Cognitive Pipeline page under the 'agent-memory' tab.
// No props required.
import AgentMemoryTab from '../components/features/cognitive/AgentMemoryTab'

// in CognitivePipeline.tsx:
{activeTab === 'agent-memory' && <AgentMemoryTab />}
```

## State Used

Local component state only (no external/global state besides the notification store side effects):

| State | Type | Purpose |
|---|---|---|
| `agents` | `DeepAgent[]` | Deep agents loaded from `GET /api/v1/cognitive/memory/agents` |
| `statuses` | `Record<string, MemoryStatus>` | Per-folder memory status, keyed by `agent.folder` |
| `expanded` | `string \| null` | Folder of the currently expanded card (Details/Collapse toggle) |
| `loading` | `boolean` | True until the agents request settles; renders "Loading agents..." while true |

## Related Components

- Parent page: `frontend/src/pages/CognitivePipeline.tsx` — renders `AgentMemoryTab` when the active tab is `'agent-memory'`; sibling tabs include `MemoryProfilesTab`, `CognitiveProfilesTab`, and `PipelineConfigTab` (`frontend/src/components/features/cognitive/`).
- Notification store: `frontend/src/stores/notificationStore.ts` — source of `useNotificationStore` used for action result toasts.
