---
title: useSessionManagement
type: atlas-hook
path: frontend/src/hooks/useSessionManagement.ts
confidence: high
updated: 2026-09-19
tags: [type/hook, domain/atlas-ui]
---
# useSessionManagement

**Path**: `frontend/src/hooks/useSessionManagement.ts`
**Type**: hook

## Purpose

Hook for managing conversation session CRUD operations: loading, creating, switching, renaming, reloading, and deleting chat sessions, plus message-level helpers (`addMessage` / `updateMessage`). The hook is a thin orchestration layer — session state lives in the `cognitiveHubStore` (Zustand singleton, `agentStore` slice) and backend I/O goes through `sessionSyncService` (`/api/v1/sessions`). The header comment states it was **MIGRATED TO COGNITIVE HUB**: reads/writes now go to/from `cognitiveHubStore` instead of local `useState`.

## Exported API

`useSessionManagement(): UseSessionManagementReturn` — takes no arguments.

```ts
interface UseSessionManagementReturn {
  sessions: ConversationSession[]
  currentSession: ConversationSession | null
  isLoadingSessions: boolean
  isReloadingSessions: boolean
  error: string | null
  createSession: (title: string, agentId: string, model: string) => Promise<ConversationSession>
  deleteSession: (sessionId: string) => void
  switchSession: (session: ConversationSession) => Promise<void>
  reloadSessions: () => Promise<void>
  renameSession: (sessionId: string, newTitle: string) => void
  replaceSession: (oldId: string, newSession: ConversationSession) => void
  clearCurrentSession: () => void
  clearCurrentSessionMessages: () => void
  closeSession: () => void
  addLocalSession: (session: ConversationSession) => void
  addMessage: (sessionId: string, message: ConversationMessage) => void
  updateMessage: (sessionId: string, messageId: string, content: string, metadata?: Record<string, unknown>) => void
}
```

| Return field | Source / behavior |
|---|---|
| `sessions` | Store slice `state.sessions` (`useCognitiveHubStore(state => state.sessions)`) |
| `currentSession` | Store slice `state.activeSession` (`useCognitiveHubStore(state => state.activeSession)`) |
| `isLoadingSessions` | Local `useState` flag toggled by `loadSessions` |
| `isReloadingSessions` | Local `useState` flag toggled by `reloadSessions` |
| `error` | Local `useState<string \| null>`; `'Failed to load sessions'` on load error, `'Failed to reload sessions: <msg>'` on reload error |
| `createSession` | `handleCreateSession` — creates session on backend first, then upserts into store |
| `deleteSession` | `handleDeleteSession` — removes from store; backend `DELETE` only for non-temp IDs |
| `switchSession` | `handleSwitchSession` — reloads full session from backend, sets active; never changes the active agent |
| `reloadSessions` | `handleReloadSessions` — full reload of sessions + messages from backend |
| `renameSession` | `handleRenameSession` — store rename + fire-and-forget backend title sync |
| `replaceSession` | `replaceSession` — swaps temp ID for real backend ID via `replaceSessionById` |
| `clearCurrentSession` | `hubStore.setActiveSession(null)` |
| `clearCurrentSessionMessages` | Sets `activeSession` copy with `messages: []` and fresh `updatedAt` |
| `closeSession` | `hubStore.closeActiveSession()` (marks active session inactive) |
| `addLocalSession` | `addLocalSession` — upserts a session (deduped by exact ID) and sets it active; used for async backend-synced sessions |
| `addMessage` | `addMessageToSession` — `hubStore.addSessionMessage(sessionId, message)` |
| `updateMessage` | `updateMessageInSession` — `hubStore.updateSessionMessage(sessionId, messageId, content, metadata)` |

`ConversationSession` (from `types/agentInteraction`):

```ts
interface ConversationSession {
  id: string
  title: string
  agentId: string
  messages?: ConversationMessage[]   // Optional — lazy loading; absent until loaded
  createdAt: Date
  updatedAt: Date
  isActive: boolean
  status?: 'active' | 'inactive' | 'unloaded'
  cognitiveConfig?: CognitiveSessionConfig
}
```

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `sessionSyncService` (`../services/sessionSyncService`) | Service (singleton class) | Pure API client for `/api/v1/sessions`: `getSessions()` (`GET ?include_messages=false` — titles only, lazy message loading), `getSession(id)` (`GET /{id}`), `createSession(...)` (`POST` with `{agent_id, title}`), `deleteSession(id)` (`DELETE /{id}`), `updateSessionTitle(id, title)` (`PUT /{id}`), `reloadSessionsWithMessages()` (list + batched `getSession` fetches, concurrency 5), `convertToFrontendSession(...)` (backend → `ConversationSession` shape). NOTE: message add/sync methods are no-ops — the backend auto-saves messages during chat |
| `useCognitiveHubStore` (`../stores/cognitiveHubStore`) | Zustand store (singleton) | Source of truth for `sessions` / `activeSession` / `activeAgent`; actions `setSessions`, `upsertSession`, `removeSession`, `replaceSessionById`, `renameSessionById`, `addSessionMessage`, `updateSessionMessage`, `setActiveSession`, `updateSessionStatus`, `closeActiveSession`. Persisted via `persist` middleware (storage key `cogitate-hub-storage`, localStorage/sessionStorage routed by `persistenceScope`) |
| `frontendLoggingService` (`../services/frontendLoggingService`) | Service | Debug/info/warning logging for session lifecycle events |
| `IdService` (`../services/domain/IdService`) | Static utility | `generateTempId()` (`session-{timestamp}-{random}`), `isTempId()`, `toBackend()`/`toFrontend()` ID conversion |
| `ConversationSession`, `ConversationMessage` (`../types/agentInteraction`) | Types | Session and message shapes |

## Usage Example

```tsx
import { useSessionManagement } from '../hooks/useSessionManagement'

function SessionSidebar() {
  const {
    sessions,
    currentSession,
    isLoadingSessions,
    createSession,
    deleteSession,
    switchSession,
    renameSession,
    reloadSessions,
  } = useSessionManagement()

  const handleNew = () => {
    createSession('New Session', activeAgentId, activeAgentModel).then(session => {
      // session is already upserted into the store and set active
      console.log('created', session.id)
    })
  }

  return (
    <aside>
      <button onClick={handleNew} disabled={isLoadingSessions}>New session</button>
      <button onClick={reloadSessions}>Reload</button>
      <ul>
        {sessions.map(s => (
          <li key={s.id} className={s.id === currentSession?.id ? 'active' : ''}>
            <button onClick={() => switchSession(s)}>{s.title}</button>
            <button onClick={() => renameSession(s.id, 'Renamed')}>Rename</button>
            <button onClick={() => deleteSession(s.id)}>Delete</button>
          </li>
        ))}
      </ul>
    </aside>
  )
}
```

## State / Data Flow

- **Boot**: `useEffect` (empty deps, mount-only) calls `loadSessions()`.
- **Load (`loadSessions`)**: reads cached sessions from the store (restored from localStorage by Zustand persist), fetches titles-only from backend (`getSessions()`), converts via `convertToFrontendSession`, then **merges cached messages back into backend sessions** (backend returns sessions without messages when `include_messages=false`). Temp sessions (`IdService.isTempId`) created during loading are preserved and appended. Result written to the store with `hubStore.setSessions`. If the backend returns empty, cached/temp sessions with messages are kept instead of clearing; on error the existing state is kept and `error` is set to `'Failed to load sessions'`.
- **Create (`createSession`)**: generates a temp ID (`session-{ts}-{rand}`), guards against duplicate concurrent creates with a `Set` ref, then `sessionSyncService.createSession(...)` (POST). The backend response is converted into a `ConversationSession` (`id` becomes the real backend ID), then `hubStore.upsertSession` + `hubStore.setActiveSession`.
- **Switch (`switchSession`)**: deliberately does **not** restore the session's agent — the user's explicit `activeAgent` selection is preserved. Always reloads the session from the backend (`getSession`) to get latest messages. Cached local title changes are preserved (unless the title is the default `'New Session'` / `'New Session {timestamp}'`, in which case the backend title wins). If the session was temp and the backend returned a different ID, `replaceSessionById` swaps it; otherwise `upsertSession`. Then sets active and `updateSessionStatus(id, 'active')`. On backend failure, falls back to the locally cached session.
- **Delete (`deleteSession`)**: `removeSession` + clears `activeSession` if it matches; only calls `sessionSyncService.deleteSession` for real (non-temp) IDs — temp sessions don't exist on the backend yet. A **failed** delete is not swallowed: the list is reloaded (the optimistically-removed row comes back) and an error notification is raised — the row left the store BEFORE the request, so silence would claim a deletion the backend never made.
- **Rename (`renameSession`)**: `renameSessionById` (atomic store update reading fresh state, avoiding stale-closure overwrites that would erase messages), then fire-and-forget `updateSessionTitle` (PUT); a failed title save reloads the list and raises an error notification for the same reason (the store already shows the new title).
- **Reload (`reloadSessions`)**: `sessionSyncService.reloadSessionsWithMessages()` (list then per-session GET in batches of 5) → `setSessions`; the current session is refreshed if still present, cleared if deleted on the backend.
- **Message helpers**: `addMessage`/`updateMessage` delegate straight to the store (`addSessionMessage` — dedupes by message ID; `updateSessionMessage`). `addLocalSession` upserts by exact-ID match (dedupes the same-timestamp false-positive bug) and activates the session — used when sessions are created optimistically and synced to the backend asynchronously (see `commitPendingSession` in `useAgentInteraction`).
- **Persistence**: no direct storage access in the hook. The `cognitiveHubStore` `persist` middleware (name `cogitate-hub-storage`) persists `sessions` (including messages, for offline access), `activeSession`, `activeAgentId`, `agents`, and `persistenceScope` to localStorage (or sessionStorage / none, per `persistenceScope`). Backend sessions are loaded without messages; cached messages are merged in from the store on load.

## Related

- `useAgentInteraction` (`frontend/src/hooks/useAgentInteraction.ts`) — primary consumer; destructures `sessions`, `currentSession`, `createSession`, `switchSession`, `renameSession`, `replaceSession`, `clearCurrentSessionMessages`, `closeSession`, `addLocalSession`, `addMessage`, `updateMessage`, and implements `commitPendingSession` which uses `replaceSession`/`addLocalSession` to swap temp sessions for backend IDs after streaming completes.
- `hooks/index.ts` — re-exports `useSessionManagement`.
- `stores/cognitiveHubStore.ts` + `stores/agentStore.ts` — state source of truth (session list, active session, lifecycle actions); the `agentStore` slice docs note it "Replaces local useState in useSessionManagement and useChatPersistence."
- `services/sessionSyncService.ts` — backend API client for `/api/v1/sessions` (create/get/list/delete/update-title).
- `services/domain/IdService.ts` — temp-ID generation and detection used for offline-first session creation.
