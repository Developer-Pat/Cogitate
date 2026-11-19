---
title: Agent Store
type: atlas-store
path: frontend/src/stores/agentStore.ts
confidence: high
updated: 2026-08-01
tags: [type/store, domain/atlas-ui]
---
# Agent Store

**Path**: `frontend/src/stores/agentStore.ts`
**Type**: store (Zustand — slice of the combined Cognitive Hub store, `create()` slices pattern)

## Purpose

The **agent slice** of the combined Cognitive Hub store. It owns the agent list, the currently selected agent, conversation sessions (list + active session), and session lifecycle (active / inactive / unloaded). Extracted from `cognitiveHubStore.ts` during the Phase C1 refactoring into a focused `StateCreator` slice; this file exports the `AgentSlice` interface and the `createAgentSlice` slice factory.

This is a `create()` slice pattern, not a standalone store: `createAgentSlice(set, get, store)` is spread — alongside `createStreamSlice`, `createProviderHealthSlice`, and `createSyncQueueSlice` — into the singleton `useCognitiveHubStore` in `cognitiveHubStore.ts`, wrapped in `devtools` + `persist` middleware. There is no separate `useAgentStore` hook; consumers access this slice through `useCognitiveHubStore` (see [Selectors / Exports](#selectors--exports)).

**Scope note**: despite the "Agent Store" name, this slice does **not** contain create/update/delete agent actions. Agent CRUD is handled elsewhere — fetching via `AgentService` (driven by `useAgentSelection`), agent-profile UI state in `agentProfilesStore.ts`. This slice provides bulk list replacement (`setAgents`), selection (`setActiveAgent`), and full session/message management.

## State Shape

The slice interface, verbatim from the source:

```ts
export interface AgentSlice {
  // ─────────────────────────────────────────────────────────────
  // Agent Management
  // ─────────────────────────────────────────────────────────────

  /** List of all available agents */
  agents: Agent[]

  /** Whether agents are currently loading */
  isLoadingAgents: boolean

  /** Error loading agents, if any */
  agentError: string | null

  /** Currently selected agent */
  activeAgent: Agent | null

  /** Current active chat session */
  activeSession: ConversationSession | null

  /** All sessions for the active agent */
  sessions: ConversationSession[]

  /** Lazy session flag — true when session created but not yet committed to backend */
  pendingSession: boolean

  // ─────────────────────────────────────────────────────────────
  // Agent Management Actions
  // ─────────────────────────────────────────────────────────────

  /** Set list of all agents */
  setAgents: (agents: Agent[]) => void

  /** Set agents loading state */
  setLoadingAgents: (loading: boolean) => void

  /** Set agent error */
  setAgentError: (error: string | null) => void

  /** Set active agent */
  setActiveAgent: (agent: Agent | null) => void

  /** Set active session */
  setActiveSession: (session: ConversationSession | null) => void

  /** Set all sessions (replaces entire list) */
  setSessions: (sessions: ConversationSession[]) => void

  /** Add or update a single session (prepends to list) */
  upsertSession: (session: ConversationSession) => void

  /** Remove a session by ID */
  removeSession: (sessionId: string) => void

  /** Replace a session by old ID with new session */
  replaceSessionById: (oldId: string, newSession: ConversationSession) => void

  /** Rename a session by ID — atomic update using fresh store state, safe from stale closures */
  renameSessionById: (sessionId: string, title: string) => void

  /** Add message to a session */
  addSessionMessage: (sessionId: string, message: ConversationMessage) => void

  /** Update message content in a session */
  updateSessionMessage: (sessionId: string, messageId: string, content: string, metadata?: unknown) => void

  /** Set pending session flag */
  setPendingSession: (pending: boolean) => void

  /** Hydrate store from persisted IDs (called on boot) */
  hydrateFromPersistedIds: () => Promise<void>

  // ─────────────────────────────────────────────────────────────
  // Session Lifecycle Actions
  // ─────────────────────────────────────────────────────────────

  /** Update session status */
  updateSessionStatus: (sessionId: string, status: 'active' | 'inactive' | 'unloaded') => void

  /** Unload messages from inactive sessions to save memory */
  unloadInactiveSessions: () => void

  /** Close active session (mark as inactive) */
  closeActiveSession: () => void
}
```

The domain types come from `frontend/src/types/agentInteraction.ts` (verbatim):

```ts
export interface Agent {
  id: string;
  name: string;
  description: string;
  capabilities: string[];
  provider: string;
  model: string;
  parameters: AgentParameters;
  isAvailable: boolean;
  profileImageUrl?: string;  // Optional profile image URL
  // Freshness metadata - tracks data freshness to prevent stale data bugs
  loadedFrom?: 'localStorage' | 'backend';
  lastRefreshed?: string;  // ISO 8601 timestamp
  isStale?: boolean;  // True if data may be outdated
}

export interface ConversationSession {
  id: string
  title: string
  agentId: string
  messages?: ConversationMessage[]  // Optional for lazy loading
  createdAt: Date
  updatedAt: Date
  isActive: boolean
  status?: 'active' | 'inactive' | 'unloaded'  // Session lifecycle status
  /** Per-session cognitive pipeline configuration */
  cognitiveConfig?: CognitiveSessionConfig
}

export interface ConversationMessage {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  timestamp: Date;
  agentId?: string;
  isStreaming?: boolean;
  metadata?: MessageMetadata;
  tool_call_id?: string;
  tool_name?: string;
  tool_result?: unknown;
}
```

## Actions

Exact signatures (from the `AgentSlice` interface) with implementation notes:

### Agent Management

| Action | Signature | Behavior |
|---|---|---|
| `setAgents` | `(agents: Agent[]) => void` | Replaces the whole `agents` list. |
| `setLoadingAgents` | `(loading: boolean) => void` | Toggles `isLoadingAgents`. |
| `setAgentError` | `(error: string \| null) => void` | Sets/clears `agentError`. |
| `setActiveAgent` | `(agent: Agent \| null) => void` | Sets `activeAgent` **and cross-slice writes** `activeProvider: agent?.provider \| null` (field owned by `ProviderHealthSlice`). |
| `setActiveSession` | `(session: ConversationSession \| null) => void` | Sets `activeSession`. |
| `setSessions` | `(sessions: ConversationSession[]) => void` | Replaces the entire `sessions` list. |
| `upsertSession` | `(session: ConversationSession) => void` | Prepends the session and filters out any existing session with the same id (add-or-update). |
| `removeSession` | `(sessionId: string) => void` | Filters the session out of `sessions`. Does not touch `activeSession`. |
| `replaceSessionById` | `(oldId: string, newSession: ConversationSession) => void` | Replaces a temp session by old id. Looks in `sessions` first, then `activeSession`; if the new session has no messages, merges the old session's messages (preserves messages added during the pending-session phase); updates `activeSession` to the new session object. If not found anywhere, prepends (shouldn't happen). |
| `renameSessionById` | `(sessionId: string, title: string) => void` | Atomic update using fresh store state (stale-closure safe). Deep-copies `messages`; sets `title` + `updatedAt`; assigns the **same object reference** to the sessions list and `activeSession` to avoid sync divergence. |
| `addSessionMessage` | `(sessionId: string, message: ConversationMessage) => void` | Appends a message (deep-copied array). Skips duplicates by message id (logs a warning via `frontendLoggingService`). If the session only exists as `activeSession`, it is prepended to the list; `activeSession` gets the same updated reference. |
| `updateSessionMessage` | `(sessionId: string, messageId: string, content: string, metadata?: unknown) => void` | Maps over the session's messages, replacing `content` and conditionally `metadata` on the matching id; bumps `updatedAt`; keeps list + `activeSession` on the same reference. |
| `setPendingSession` | `(pending: boolean) => void` | Sets the lazy-session flag. |
| `hydrateFromPersistedIds` | `() => Promise<void>` | **No-op placeholder** — comment: "will be implemented in Phase 3 with CognitiveHubProvider". |

### Session Lifecycle

| Action | Signature | Behavior |
|---|---|---|
| `updateSessionStatus` | `(sessionId: string, status: 'active' \| 'inactive' \| 'unloaded') => void` | Maps over `sessions`, setting `status` on the match. |
| `unloadInactiveSessions` | `() => void` | For every non-active session with messages, clears `messages` and marks `status: 'unloaded'` (keeps title). Active session stays in memory. |
| `closeActiveSession` | `() => void` | Marks the active session `status: 'inactive'`, `isActive: false` in both the list and `activeSession` (messages kept in memory). |

## Selectors / Exports

- **Exports from this file**: `AgentSlice` (type) and `createAgentSlice` (`StateCreator<CombinedState, [], [], AgentSlice>`). No hooks or selector helpers are defined here.
- **Consumption**: through the combined store hook `useCognitiveHubStore` (`cognitiveHubStore.ts`, default export):
  - Hook form: `useCognitiveHubStore((s) => s.sessions)` — reactive per-field selection.
  - Imperative form: `useCognitiveHubStore.getState()` / `useCognitiveHubStore.subscribe()` — used by services and event handlers.
- `CombinedState = AgentSlice & StreamSlice & ProviderHealthSlice & SyncQueueSlice` — each slice types its `set`/`get` against the full combined store, enabling cross-slice access.
- `AgentSlice` is also imported as a type by `streamStore.ts`, `providerHealthStore.ts`, `syncQueueStore.ts` (combined-state typing) and `utils/cogitateDevTools.ts` (store inspection).

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `zustand` (`StateCreator`) | lib | Slice factory typing for the `create()` slices pattern. |
| `../types/agentInteraction` | types | `Agent`, `ConversationSession`, `ConversationMessage` domain types. |
| `../services/frontendLoggingService` | service | `warning()` log on duplicate `addSessionMessage` attempts. |
| `./providerHealthStore` (`ProviderHealthSlice`) | store (type) | `setActiveAgent` writes the cross-slice `activeProvider` field. |
| `./streamStore` (`StreamSlice`) | store (type) | Combined-state typing only. |
| `./syncQueueStore` (`SyncQueueSlice`) | store (type) | Combined-state typing only. |
| `./cognitiveHubStore.ts` (composing store) | store | Spreads `createAgentSlice` into `useCognitiveHubStore` with `devtools` + `persist`. |

## Usage Example

```tsx
import { useCognitiveHubStore } from '../stores/cognitiveHubStore'
import type { Agent } from '../types/agentInteraction'

function AgentSwitcher() {
  const agents = useCognitiveHubStore((s) => s.agents)
  const activeAgent = useCognitiveHubStore((s) => s.activeAgent)
  const setActiveAgent = useCognitiveHubStore((s) => s.setActiveAgent)

  const handleSelect = (agent: Agent) => {
    setActiveAgent(agent) // also sets activeProvider (ProviderHealth slice)
  }

  return (
    <select
      value={activeAgent?.id}
      onChange={(e) => {
        const agent = agents.find((a) => a.id === e.target.value)
        if (agent) handleSelect(agent)
      }}
    >
      {agents.map((a) => (
        <option key={a.id} value={a.id}>{a.name}</option>
      ))}
    </select>
  )
}
```

## Data Flow / Notes

- **Composition**: `cognitiveHubStore.ts` builds `useCognitiveHubStore = create<CognitiveHubState>()(devtools(persist((set, get, store) => ({ ...createAgentSlice(set, get, store), ...createStreamSlice(...), ...createProviderHealthSlice(...), ...createSyncQueueSlice(...), persistenceScope: 'local', setPersistenceScope }), { name: 'cogitate-hub-storage', partialize, storage: scopedStorage, onRehydrateStorage }), { name: 'CognitiveHubStore', enabled: import.meta.env.DEV }))`. `persist` wraps the whole combined state; `partialize` selects which keys are written.
- **Persistence** (`partialize`): `{ agents, activeAgentId: state.activeAgent?.id ?? null, activeSessionId: state.activeSession?.id ?? null, activeSession, persistenceScope, sessions }`. Note `activeAgentId` / `activeSessionId` are derived keys **not** part of `AgentSlice`; only `activeAgentId` (not the full agent object) is persisted "to avoid stale data". Per the comment in `cognitiveHubStore.ts`, `activeAgent` is reconstructed from the persisted agents list on rehydration. `useAgentSelection` reads the persisted `activeAgentId` via `(hubState as unknown as Record<string, unknown>).activeAgentId` to reconcile the selection.
- **Storage routing**: `scopedStorage` routes to `localStorage` / `sessionStorage` / none based on `persistenceScope`; `onRehydrateStorage` restores the scope and logs restored counts.
- **Cross-slice write**: `setActiveAgent(agent)` also sets `activeProvider` (owned by `ProviderHealthSlice`) — the only cross-slice write in this file.
- **Reference-sync pattern**: session-mutating actions (`addSessionMessage`, `updateSessionMessage`, `renameSessionById`, `replaceSessionById`, `closeActiveSession`) build ONE updated session object and assign the same reference to both `sessions[i]` and `activeSession` when the target is active — preventing divergence between the list and the active session.
- **Lazy/pending sessions**: `pendingSession: true` means a temp session exists client-side but is not yet committed to the backend; `replaceSessionById` later swaps the temp id for the backend id while preserving any messages added in between.
- **Agent loading flow**: `useAgentSelection.loadAgents()` → `AgentService.getAgents()` → `setLoadingAgents(true)` / `setAgents(list)` / `setAgentError(...)` / `setLoadingAgents(false)`. Selecting an agent calls `setActiveAgent` immediately (responsive UI) then background-refreshes via `AgentService.getAgent(id)` to replace stale cached agents.
- **Session lifecycle**: statuses `'active' | 'inactive' | 'unloaded'`; `unloadInactiveSessions` drops messages (keeps titles) to save memory; `closeActiveSession` keeps messages in memory but marks inactive.

## Related

Consumers (all via `useCognitiveHubStore` from `cognitiveHubStore.ts`):

| Consumer | Usage |
|---|---|
| `hooks/useAgentInteraction.ts` | Main chat flow: reads/writes `activeSession`, `sessions`, `setPendingSession`; heavy `getState()` use. |
| `hooks/useSessionManagement.ts` | Session create/select/delete/rename orchestration over `sessions` + `activeSession`. |
| `hooks/useAgentSelection.ts` | `agents`, `activeAgent`, `isLoadingAgents`, `agentError` + `setAgents` / `setActiveAgent` / `setLoadingAgents` / `setAgentError`; loads agents via `AgentService`. |
| `hooks/useAIHub.ts` | Accesses the whole store. |
| `hooks/useUIStateBridge.ts` | Bridges `activeAgent` / `activeSession` into legacy UI state. |
| `providers/CognitiveHubProvider.tsx` | Provides the full store to the component tree. |
| `components/features/agentInteraction/SessionManager.tsx` | Reads `activeAgent`. |
| `components/sessions/SessionTable.tsx`, `SessionDetailsModal.tsx` | Imperative `getState().setActiveSession(...)`. |
| `pages/Sessions.tsx` | `sessions` list + `renameSessionById`. |
| `services/domain/SessionsService.ts` | Session CRUD: `setSessions`, `upsertSession`, `removeSession`, reads `sessions`. |
| `services/domain/TitleService.ts` | Auto-title: `renameSessionById` + session lookup. |
| `services/domain/StreamingService.ts`, `services/offlineSyncQueue.ts` | Streaming/offline-sync flows reading hub state (incl. sync-queue slice). |
| `utils/cogitateDevTools.ts` | Dev-tools snapshot/subscribe; imports `AgentSlice` type. |

## Deprecation / Obsolete Notes

- **No `@deprecated` / "legacy" markers** anywhere in `agentStore.ts`, and the slice is actively consumed by hooks, services, pages, and components — nothing here is obsolete.
- **`hydrateFromPersistedIds` is a documented no-op placeholder** — comment says "will be implemented in Phase 3 with CognitiveHubProvider. For now, it's a no-op placeholder." It exists in the interface and initial state but performs no work.
- **Commented-out `traceService` diagnostics**: large blocks of commented-out tracing calls remain in `setActiveAgent`, `setSessions`, `removeSession`, `replaceSessionById`, `renameSessionById`, `addSessionMessage`, `updateSessionMessage`. Dead code, not executed.
- **Removed-feature check**: this store contains no references to any of the removed features previously documented in the old atlas (verified by grep during documentation; the grep-based check passes with zero matches).
- **Notable gaps** (not deprecations, but scope facts): agent CRUD actions do not exist in this slice (only `setAgents` bulk set + `setActiveAgent` selection); agent-profile UI state lives in `agentProfilesStore.ts`; agent fetching lives in `AgentService` via `useAgentSelection`.
