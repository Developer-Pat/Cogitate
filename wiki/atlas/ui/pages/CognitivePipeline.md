---
title: Cognitive Pipeline
type: atlas-page
path: frontend/src/pages/CognitivePipeline.tsx
confidence: high
updated: 2026-07-31
tags: [type/page, domain/atlas-ui]
---
# Cognitive Pipeline

**Component**: `frontend/src/pages/CognitivePipeline.tsx`
**Route**: `/cognitive-pipeline` (lazy-loaded in `frontend/src/config/routes.ts`; `requiresAuth: true`, `permissions: ['admin', 'config_manager', 'developer']`, icon `brain`, breadcrumb `Cognitive Pipeline`)
**Last Updated**: 2026-07-31

## Purpose

Management hub for agent cognitive pipeline configuration. The page is a tabbed shell (DaisyUI `tabs tabs-bordered`) hosting four independent feature tabs: **Pipeline Config** (ad-hoc strategy selection), **Memory Profiles** (CRUD for named memory configurations), **Cognitive Profiles** (CRUD for reusable bundles of pipeline strategies + a referenced memory profile), and **Agent Memory** (inspection and maintenance of deep-agent cognitive memory stores). The page itself holds only tab state and a `PipelineConfig` draft; all data loading and mutation happens inside the tab components.

## Key Features

- **Four-tab navigation** (`pipeline` / `memory` / `cognitive` / `agent-memory`) driven by local `useState<TabId>`, with emoji icons (⚙️ 💾 🧠 📦).
- **Pipeline Config tab**: four strategy dropdowns — Context Builder (`default`/`minimal`/`augmented`/`skill_aware`), Executor (`default`/`fast`/`hybrid`/`stub`), Memory Manager (`default`/`noop`/`kv_store`), Response Formatter (`default`/`direct_yield`/`structured`) — each with a human-readable description under the select.
- **Cognitive profile picker**: dropdown loaded from `cognitiveProfileService.list()`; selecting a profile populates the strategy selects (context_builder, executor, response_formatter; memory_manager is forced to `'default'`).
- **"Reset to Defaults"** button restoring all four strategies to `'default'`.
- **"Show pipeline indicators" toggle** — reads/writes `settings.general.showPipelineIndicators` in the Zustand settings store; consumed downstream by `ResponseStream.tsx` (Agent Chat) to render pipeline strategy badges in response footers.
- **Memory Profiles tab**: full CRUD table (name, strategy, window size, persistence `memory`/`sqlite`, compaction threshold, summarization flag, built-in lock 🔒). Create form + inline row editing via DOM-element reads on Save; built-in profiles are read-only.
- **Cognitive Profiles tab**: full CRUD table (name, context_builder, executor, response_formatter, linked memory profile name). Bundles strategy selectors with a memory-profile picker; built-in profiles are read-only.
- **Agent Memory tab**: per-deep-agent cards showing memory status badges (sessions, turns, summaries, facts, vector index turns), plus **Export** (client-side JSON blob download) and maintenance actions **Clear Sessions**, **Clear All Memory**, **Prune (30d)**, **Clear Vectors**.

## Components Used

| Component | Path | Purpose |
|---|---|---|
| `PipelineConfigTab` | `frontend/src/components/features/cognitive/PipelineConfigTab.tsx` | Strategy selectors + cognitive profile dropdown + indicators toggle; exports the `PipelineConfig` type (`context_builder`, `executor`, `memory_manager`, `response_formatter`) |
| `MemoryProfilesTab` | `frontend/src/components/features/cognitive/MemoryProfilesTab.tsx` | Memory profile CRUD table and create form |
| `CognitiveProfilesTab` | `frontend/src/components/features/cognitive/CognitiveProfilesTab.tsx` | Cognitive profile CRUD table bundling strategies + memory profile reference |
| `AgentMemoryTab` | `frontend/src/components/features/cognitive/AgentMemoryTab.tsx` | Deep-agent memory status, export, and maintenance actions |
| `cognitiveProfileService` | `frontend/src/services/domain/CognitiveProfileService.ts` | API client (singleton) for `/api/v1/cognitive-profiles` CRUD |
| `memoryProfileService` | `frontend/src/services/domain/MemoryProfileService.ts` | API client (singleton) for `/api/v1/memory-profiles` CRUD |
| `frontendLoggingService` | `frontend/src/services/frontendLoggingService.ts` | Error logging on every fetch/mutation failure across all tabs |
| `useSettingsStore` | `frontend/src/stores/settingsStore.ts` | Zustand store; reads and writes `settings.general.showPipelineIndicators` |
| `useNotificationStore` | `frontend/src/stores/notificationStore` | Toast feedback (`addSuccess`/`addError`) for Agent Memory actions |

> Note: the radio-card `CognitiveProfileSelector` component (`frontend/src/components/features/cognitive/CognitiveProfileSelector.tsx`, profiles rendered as selectable cards with a part-code like `d-d-d-d`) is **not** used on this page — the Pipeline Config tab uses a plain `<select>` dropdown. The radio-card selector is used by the Agent Profiles page (`AgentProfiles/ProfileDetail.tsx`). Both share `cognitiveProfileService`.

## Hooks Used

| Hook | Path | Purpose |
|---|---|---|
| `useState` | react | Tab selection, `PipelineConfig` draft, profile lists, loading/error flags, edit/create form state, expanded agent cards |
| `useEffect` | react | Mount-time data fetching: profiles list (PipelineConfigTab), memory profiles (MemoryProfilesTab), cognitive + memory profiles in parallel (CognitiveProfilesTab), deep-agent list (AgentMemoryTab) |

No custom hooks are used; all state is local to the page and tab components.

## Data Flow

1. **Pipeline Config**: `cognitiveProfileService.list()` → `CognitiveProfile[]` rendered in a dropdown. Selecting a profile maps `context_builder`/`executor`/`response_formatter` into the parent's `PipelineConfig` state (`memory_manager` hardcoded to `'default'`); manual dropdown edits spread-update single keys. The resulting `PipelineConfig` lives in `CognitivePipeline`'s `useState` but is **not persisted to the backend from this page** — it is a draft for UI/planning. The indicators toggle flows into `useSettingsStore.updateSettings()`, which debounce-syncs to the backend via `userSettingsService`.
2. **Memory Profiles**: `memoryProfileService.list()` on mount → table. Create posts `MemoryProfileCreate`; Save in edit mode reads the row's DOM inputs and posts `MemoryProfileUpdate`; delete calls `delete(id)`. Every mutation refetches the list.
3. **Cognitive Profiles**: `Promise.all([cognitiveProfileService.list(), memoryProfileService.list()])` on mount → profiles table + memory-profile dropdown options. CRUD mirrors the memory-profiles flow (`CognitiveProfileCreate`/`CognitiveProfileUpdate`); the table resolves the linked memory profile name via `memory_profile_name` on the payload (fallback `-`).
4. **Agent Memory**: raw `fetch` (not `apiClient`) against `/api/v1/cognitive/memory/*`. Agents list loads first, then per-folder status is fetched sequentially. Actions call DELETE/POST endpoints, surface the backend `message` via `useNotificationStore`, and re-fetch statuses after ~500 ms. Export converts the JSON response into a Blob and triggers a browser download named `<folder>-memory-export.json`.
5. **Error handling**: every async failure is logged through `frontendLoggingService.error(...)`; the two CRUD tabs also surface a dismissible error alert; Agent Memory surfaces failures via notification toasts.

## State Management

| Store | Read | Write |
|---|---|---|
| `useSettingsStore` (Zustand, `frontend/src/stores/settingsStore.ts`) | `settings.general.showPipelineIndicators` (PipelineConfigTab checkbox) | `updateSettings({ general: { ...showPipelineIndicators: !value } })` — debounced backend sync via `userSettingsService` |
| `useNotificationStore` (Zustand) | — | `addSuccess('Memory Action' / 'Export' / 'Prune', msg)` and `addError(...)` from AgentMemoryTab |

All other state (tabs, config draft, profile lists, loading/error, edit/create forms) is local component state.

## API Endpoints Called

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/cognitive-profiles` | List cognitive profiles (`cognitiveProfileService.list()`, optional `?include_builtin=false`) |
| GET | `/api/v1/cognitive-profiles/{id}` | Fetch single cognitive profile |
| POST | `/api/v1/cognitive-profiles` | Create cognitive profile |
| PUT | `/api/v1/cognitive-profiles/{id}` | Update cognitive profile |
| DELETE | `/api/v1/cognitive-profiles/{id}` | Delete cognitive profile |
| GET | `/api/v1/memory-profiles` | List memory profiles (optional `?include_builtin=false`) |
| GET | `/api/v1/memory-profiles/{id}` | Fetch single memory profile |
| POST | `/api/v1/memory-profiles` | Create memory profile |
| PUT | `/api/v1/memory-profiles/{id}` | Update memory profile |
| DELETE | `/api/v1/memory-profiles/{id}` | Delete memory profile |
| GET | `/api/v1/cognitive/memory/agents` | List deep agents with memory stores (AgentMemoryTab) |
| GET | `/api/v1/cognitive/memory/{folder}/status` | Memory status for a deep agent (sessions, turns, summaries, facts, vector index) |
| DELETE | `/api/v1/cognitive/memory/{folder}/clear/sessions` | Clear an agent's session history |
| DELETE | `/api/v1/cognitive/memory/{folder}/clear/all` | Clear all memory for an agent |
| DELETE | `/api/v1/cognitive/vectors/{folder}/all` | Clear an agent's vector index |
| POST | `/api/v1/cognitive/memory/prune` | Prune entries older than `max_days` (body `{ max_days: 30 }`) |
| GET | `/api/v1/cognitive/memory/{folder}/export` | Export agent memory as JSON |

## Related Pages

- [[AgentInteraction]] — chat page; its `ResponseStream.tsx` consumes `settings.general.showPipelineIndicators` to show pipeline strategy badges in response footers (controlled from the Pipeline Config tab)
- [[AgentProfiles]] — agent profile detail uses the radio-card `CognitiveProfileSelector` backed by the same `cognitiveProfileService`
- [[Settings]] — the settings store updated by the indicators toggle is managed from here
