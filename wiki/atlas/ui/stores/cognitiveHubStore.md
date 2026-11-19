---
title: Cognitive Hub Store
type: atlas-store
path: frontend/src/stores/cognitiveHubStore.ts
confidence: high
updated: 2026-08-01
tags: [type/store, domain/atlas-ui]
---
# Cognitive Hub Store

**Path**: `frontend/src/stores/cognitiveHubStore.ts`
**Type**: store (Zustand)
**Last Updated**: 2026-08-01

## Purpose

Central singleton Zustand store for AI context state: agents, active agent, chat sessions, streaming flags, provider health, and the offline sync queue. It replaces local `useState` in `useSessionManagement` and `useChatPersistence`, and survives navigation because it is a module-level singleton rather than a component-mounted store.

Since the Phase C1 refactoring, this file composes focused sub-store slices using the Zustand slices pattern; `cognitiveHubStore.ts` itself is the composition + persistence layer. It is the app's shared agent state — `useAgentSelection` explicitly treats it as the **single source of truth** for agent list/selection state.

## State Shape

Copied verbatim from the source. The combined store state is `CognitiveHubState`, which extends the four slice interfaces.

### Combined state (`CognitiveHubState`)

```typescript
interface CognitiveHubState
  extends AgentSlice,
    StreamSlice,
    ProviderHealthSlice,
    SyncQueueSlice {
  // ─────────────────────────────────────────────────────────────
  // User Preferences (kept here — tightly coupled to persist config)
  // ─────────────────────────────────────────────────────────────

  /** Where to persist active context */
  persistenceScope: PersistenceScope

  /** Set persistence scope preference */
  setPersistenceScope: (scope: PersistenceScope) => void
}
```

### `AgentSlice` (from `agentStore.ts`)

```typescript
export interface AgentSlice {
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

  /** Update session status */
  updateSessionStatus: (sessionId: string, status: 'active' | 'inactive' | 'unloaded') => void

  /** Unload messages from inactive sessions to save memory */
  unloadInactiveSessions: () => void

  /** Close active session (mark as inactive) */
  closeActiveSession: () => void
}
```

### `StreamSlice` (from `streamStore.ts`)

```typescript
export interface StreamSlice {
  /** Whether currently streaming a response */
  isStreaming: boolean

  /** Session ID currently being streamed to */
  streamingFor: string | null

  /** Update streaming status */
  setIsStreaming: (streaming: boolean, sessionId?: string) => void
}
```

### `ProviderHealthSlice` (from `providerHealthStore.ts`)

```typescript
export interface ProviderHealthSlice {
  /** Health status per provider */
  providerHealth: Record<string, ProviderHealthStatus>

  /** Currently active provider (from activeAgent) */
  activeProvider: string | null

  /** Update provider health map */
  setProviderHealth: (health: Record<string, ProviderHealthStatus>) => void
}
```

### `SyncQueueSlice` (from `syncQueueStore.ts`)

```typescript
export interface SyncQueueSlice {
  /** Messages pending sync to backend */
  pendingMessages: PendingMessage[]

  /** Number of messages pending sync */
  pendingSyncCount: number

  /** Add message to pending sync queue */
  addToPendingQueue: (sessionId: string, message: ConversationMessage) => void

  /** Remove message from pending queue (on successful sync) */
  removeFromPendingQueue: (messageId: string) => void

  /** Increment retry count for a message */
  incrementRetryCount: (messageId: string) => void

  /** Clear all pending messages */
  clearPendingQueue: () => void
}
```

### Shared types (from `types.ts`)

```typescript
export type PersistenceScope = 'local' | 'session' | 'none'

export type ProviderHealthStatus = 'up' | 'degraded' | 'down'

export interface PendingMessage {
  id: string
  sessionId: string
  message: ConversationMessage
  retryCount: number
  createdAt: number
  lastAttemptAt: number
}
```

### Domain types (from `../types/agentInteraction`)

- `Agent`: `{ id, name, description, capabilities: string[], provider, model, parameters: AgentParameters, isAvailable, profileImageUrl?, loadedFrom?: 'localStorage' | 'backend', lastRefreshed?, isStale? }`
- `ConversationSession`, `ConversationMessage` (role `'user' | 'assistant' | 'system' | 'tool'`, content, timestamp, metadata, streaming flags)

## Actions

Exact signatures, grouped by slice.

**Agent slice** (`agentStore.ts`):
- `setAgents: (agents: Agent[]) => void`
- `setLoadingAgents: (loading: boolean) => void`
- `setAgentError: (error: string | null) => void`
- `setActiveAgent: (agent: Agent | null) => void` — also sets `activeProvider: agent?.provider || null`
- `setActiveSession: (session: ConversationSession | null) => void`
- `setSessions: (sessions: ConversationSession[]) => void` — replaces entire list
- `upsertSession: (session: ConversationSession) => void` — prepends / replaces by id
- `removeSession: (sessionId: string) => void`
- `replaceSessionById: (oldId: string, newSession: ConversationSession) => void` — merges messages from the old session
- `renameSessionById: (sessionId: string, title: string) => void` — atomic, stale-closure safe
- `addSessionMessage: (sessionId: string, message: ConversationMessage) => void` — dedupes by message id
- `updateSessionMessage: (sessionId: string, messageId: string, content: string, metadata?: unknown) => void`
- `setPendingSession: (pending: boolean) => void`
- `hydrateFromPersistedIds: () => Promise<void>` — no-op placeholder (see Deprecation notes)
- `updateSessionStatus: (sessionId: string, status: 'active' | 'inactive' | 'unloaded') => void`
- `unloadInactiveSessions: () => void` — drops messages from non-active sessions
- `closeActiveSession: () => void` — marks active session inactive

**Stream slice** (`streamStore.ts`):
- `setIsStreaming: (streaming: boolean, sessionId?: string) => void`

**Provider health slice** (`providerHealthStore.ts`):
- `setProviderHealth: (health: Record<string, ProviderHealthStatus>) => void`

**Sync queue slice** (`syncQueueStore.ts`):
- `addToPendingQueue: (sessionId: string, message: ConversationMessage) => void`
- `removeFromPendingQueue: (messageId: string) => void`
- `incrementRetryCount: (messageId: string) => void`
- `clearPendingQueue: () => void`

**Composition layer** (`cognitiveHubStore.ts`):
- `setPersistenceScope: (scope: PersistenceScope) => void` — switches scoped storage routing

## Selectors / Exports

- `useCognitiveHubStore` — the store hook, `create<CognitiveHubState>()(devtools(persist(...)))`. No standalone selector functions; consumers use inline selectors: `useCognitiveHubStore((state) => state.activeAgent)`, and `useCognitiveHubStore.getState()` for imperative access.
- `export default useCognitiveHubStore` — default export alias.
- Type re-exports: `PersistenceScope`, `ProviderHealthStatus`, `PendingMessage` from `./types` (backward-compat re-exports).
- Slice creators (`createAgentSlice`, `createStreamSlice`, `createProviderHealthSlice`, `createSyncQueueSlice`) are imported from sibling files; the combined store spreads them.

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `zustand` (`create`) | npm | Store factory |
| `zustand/middleware` (`devtools`, `persist`, `PersistStorage`) | npm | Redux-DevTools integration + state persistence |
| `./agentStore` (`createAgentSlice`, `AgentSlice`) | local slice | Agents, active agent, sessions, session lifecycle |
| `./streamStore` (`createStreamSlice`, `StreamSlice`) | local slice | Streaming status flags |
| `./providerHealthStore` (`createProviderHealthSlice`, `ProviderHealthSlice`) | local slice | Provider health map + active provider |
| `./syncQueueStore` (`createSyncQueueSlice`, `SyncQueueSlice`) | local slice | Offline sync queue |
| `./types` (`PersistenceScope`, `ProviderHealthStatus`, `PendingMessage`) | local types | Shared store types |

## Usage Example

```tsx
import { useCognitiveHubStore } from '../stores/cognitiveHubStore'

function AgentSwitcher() {
  // Selector-based reads — component re-renders only when its slice changes
  const agents = useCognitiveHubStore((s) => s.agents)
  const activeAgent = useCognitiveHubStore((s) => s.activeAgent)
  const isLoading = useCognitiveHubStore((s) => s.isLoadingAgents)
  const setActiveAgent = useCognitiveHubStore((s) => s.setActiveAgent)

  return (
    <select
      value={activeAgent?.id ?? ''}
      disabled={isLoading}
      onChange={(e) => {
        const agent = agents.find((a) => String(a.id) === e.target.value)
        if (agent) setActiveAgent(agent)
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

- **Singleton**: module-level store, not mounted in the React tree — survives navigation. `CognitiveHubProvider` mounts once at app root (a plain component, NOT a context provider; "the Zustand store is the source of truth") to run boot hydration, provider-health polling, and the offline retry processor.
- **Persistence**: wrapped in `persist` middleware under storage key `cogitate-hub-storage`. `partialize` persists `agents`, `activeAgentId` (`activeAgent?.id ?? null` — only the ID, not the full object, to avoid stale data), `activeSessionId`, `activeSession`, `persistenceScope`, and `sessions`.
- **Scoped storage**: custom `createScopedStorage()` routes get/set/remove to `localStorage`, `sessionStorage`, or nowhere based on `persistenceScope` (`'local' | 'session' | 'none'`). `onRehydrateStorage` re-applies the persisted scope and logs a rehydration summary (agent/session counts, active agent name).
- **Restore flow** — there is no single `restore` action in the store; restore is distributed:
  1. Zustand `persist` rehydrates persisted state automatically; `onRehydrateStorage` logs the result.
  2. `CognitiveHubProvider.hydrate()` reads `localStorage['cogitate-hub-storage']` on boot, calls `setAgents` + `setActiveAgent`, then refreshes the active agent from `/api/v1/agents/:id` (or `/api/v1/agents` if the list was not persisted) so the model is never stale; corrupted storage JSON is cleared.
  3. `useAgentSelection.restoreAgentSelection()` validates the persisted `activeAgentId` still exists in `agents` (clears it if not), falls back to `AgentService.getSelectedAgent(agents)`, then auto-selects `agents[0]`.
- **`useAgentSelection` as single source of truth**: its code comment reads "Use cognitive hub store for shared state (single source of truth)". `agents`, `isLoadingAgents`, `agentError`, and `activeAgent` are all read from and written through this store. `activeAgentId` persistence via localStorage (`cogitate-hub-storage`) is observed in its restore logic (`hubState.activeAgent?.id` / raw `activeAgentId`), and `handleSelectAgent` additionally refreshes the selected agent from the backend in the background.
- **DevTools**: `devtools` middleware named `CognitiveHubStore`, enabled only when `import.meta.env.DEV`.
- **Gotcha**: the `onRehydrateStorage` comment claims Zustand "reconstructs activeAgent from the agents list during rehydration", but `partialize` only persists `activeAgentId` — the ID→object resolution is actually performed by consumers (`CognitiveHubProvider` and `useAgentSelection`), which explicitly handle the case where `activeAgent` is not yet set.
- **Stale doc reference**: the header `@see docs/hub/PHASED-IMPLEMENTATION-PLAN.md` points at a plan that has moved to `_archive/docs/2026-04-11-hub-consolidation/`.

## Related

Consumers (18 files in `frontend/src` import `useCognitiveHubStore`):

- **Hooks**: `useAgentSelection` (single source of truth for agent selection), `useAIHub`, `useAgentInteraction`, `useSessionManagement`, `useUIStateBridge`
- **Components**: `SessionManager` (agentInteraction feature), `SessionTable`, `SessionDetailsModal` (sessions)
- **Pages**: `Sessions`
- **Services**: `TitleService`, `SessionsService`, `StreamingService`, `offlineSyncQueue` (plus `SessionsService.test.ts`, `StreamingService.test.ts`)
- **Providers**: `CognitiveHubProvider` (boot hydration)
- **Utils**: `cogitateDevTools`

## Deprecation / Obsolete Notes

- No `@deprecated`, `legacy`, "no longer used", or `unused` markers in `cognitiveHubStore.ts` or any of the four slice files (grep-verified).
- `hydrateFromPersistedIds()` is an intentional no-op placeholder (docstring: "This will be implemented in Phase 3 with CognitiveHubProvider") — not deprecated, but non-functional; real restore is handled by the persist middleware plus provider/hook logic documented above.
- The header doc comment's reference to `docs/hub/PHASED-IMPLEMENTATION-PLAN.md` is stale (plan now lives under `_archive/docs/2026-04-11-hub-consolidation/`).
- The store is actively consumed by 18 files in `frontend/src` — in active use, not obsolete.
- No references to removed/archived features appear in this store or its consumers (grep-verified). The atlas's documented log-source exception does not apply here — no such API fields or log sources are connected to this store.
