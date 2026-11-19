---
title: Session Sync Service
type: atlas-service
path: frontend/src/services/sessionSyncService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---

# Session Sync Service

**Path**: `frontend/src/services/sessionSyncService.ts`
**Type**: service

## Purpose

Pure API client for session operations. It owns all HTTP requests to the backend for sessions and messages, plus the data-format conversion between backend (snake_case, integer IDs) and frontend (camelCase metadata, string IDs) shapes.

Explicitly **not** responsible for:
- State management / caching (delegated to `SessionsService` in `services/domain/SessionsService.ts`)
- Context tracking (delegated to `CurrentSessionService`)

It is a stateless request/response client: no polling loop, no event subscription, no cache of its own. The sync model is **lazy / on-demand**: session titles are loaded without messages (`include_messages=false`), and full message history is fetched per-session only when a session is opened. Message persistence is handled by the backend auto-saving during chat — the service's message-write methods are explicit no-ops with a logged note.

## Exported API

Single-export module: `sessionSyncService` is exported both as a named export and as the default export (also re-exported from `services/index.ts`). Two interfaces are exported for consumers.

### Interfaces

```ts
export interface SessionSyncResponse {
  id: string
  title: string
  model: string
  agent_id: string
  memory: boolean
  tools: string[]
  messages?: SessionSyncMessage[]
  created?: number
  updated?: number
  created_at?: string  // For compatibility with backend format
  updated_at?: string  // For compatibility with backend format
}

export interface BackendSession {
  id: number
  title: string | null
  agent_id: number
  is_active: boolean
  created_at: string
  updated_at: string
  messages?: Array<{
    id: number
    role: string
    content: string
    created_at: string
    token_count?: number
    total_time_ms?: number
    tokens_per_second?: number
    model?: string
    provider?: string
  }>
}
```

(The internal `SessionSyncMessage` interface — `id`, `role`, `content`, `created_at` plus optional `token_count`/`total_time_ms`/`tokens_per_second`/`model`/`provider` either directly on the object or nested in `metadata` — is **not** exported.)

### Instance methods (class `SessionSyncService`, `basePath = '/api/v1/sessions'`)

```ts
async createSession(
  _sessionId: string,
  title: string,
  _agentId: string,
  _model: string
): Promise<SessionSyncResponse>
```
POSTs to the base path with `{ agent_id: IdService.toBackend(_agentId), title }`. `_sessionId` and `_model` are unused by the request; `_model` is only passed through as the model hint for `convertToSessionResponse`. Throws `'No response data from server'` if the response body is empty. Logs + rethrows on failure.

```ts
async getSession(sessionId: string): Promise<SessionSyncResponse>
```
GETs `{basePath}/{sessionId}` — returns the full session **with messages**. Logs + rethrows on failure.

```ts
async getSessions(): Promise<SessionSyncResponse[]>
```
GETs `{basePath}?include_messages=false` — titles only (lazy loading; messages fetched on demand). Reads `response.data.sessions` (defaults to `[]`). **On error returns `[]` instead of throwing** — the only method with this behavior.

```ts
async reloadSessionsWithMessages(): Promise<SessionSyncResponse[]>
```
Initial-load path: calls `getSessions()` then `getSession()` per session in batches of **5 concurrent** requests (`CONCURRENCY_LIMIT = 5`) to avoid overwhelming the backend. A failed per-session fetch logs a warning and returns the title-only session rather than failing the whole batch. Throws on overall failure. Doc comment warns: for cached sessions use `SessionsService`; this fetches straight from the backend and should not be called frequently.

```ts
async addMessage(
  _sessionId: string,
  _role: 'user' | 'assistant',
  _content: string,
  _messageId?: string
): Promise<void>
```
**No-op.** Backend auto-saves messages when the chat endpoint is called; logs a debug note.

```ts
async deleteSession(sessionId: string): Promise<void>
```
DELETEs `{basePath}/{sessionId}`. Logs + rethrows on failure.

```ts
async deleteMessage(sessionId: string, messageId: string): Promise<void>
```
**No-op** — backend does not support individual message deletion; logs a warning.

```ts
convertToFrontendSession(backendSession: SessionSyncResponse): ConversationSession
```
Public converter to the app's `ConversationSession` type. Handles both metadata shapes (fields directly on the message vs. nested `metadata` object) via `(metadata.token_count ?? metadata.tokenCount)` style access. Timestamps accept either `created`/`updated` (numbers) or `created_at`/`updated_at` (strings); falls back to `new Date()`.

```ts
async syncMessage(
  _sessionId: string,
  message: ConversationMessage
): Promise<void>
```
**No-op** — backend auto-saves; logs a debug note.

```ts
async syncAllMessages(
  _sessionId: string,
  _messages: ConversationMessage[]
): Promise<void>
```
**No-op** — backend auto-saves.

```ts
async updateSessionTitle(
  sessionId: string,
  newTitle: string
): Promise<void>
```
PUTs `{basePath}/{backendSessionId}` with `{ title: newTitle }`, converting the frontend string ID via `IdService.toBackend`. Checks the response for an `error` field and throws `Backend error: {message}` if present. Logs + rethrows on failure.

### Private helpers

- `convertToSessionResponse(backend: BackendSession, model?: string): SessionSyncResponse` — backend→frontend shape conversion. Falls back to title `New Session ${Date.now()}` when `backend.title` is null; falls back to model `'llama3.2'` with a logged warning when `model` is missing; maps `is_active` → `memory`, hardcodes `tools: []`, converts IDs via `IdService.toFrontend`, and flattens message metadata fields into a nested `metadata` object (only when at least one field is present).
- `parseTimestamp(timestamp: number | string): Date` — accepts string or number; warns on unknown format and returns `new Date()`.

## Endpoints

Base path: `/api/v1/sessions` (relative to `apiClient`'s base URL, `VITE_API_URL` or `http://localhost:8000`).

| Method | Endpoint | Purpose | Notes |
|---|---|---|---|
| POST | `/api/v1/sessions` | Create session | Body `{ agent_id, title }`; `agent_id` converted to backend integer |
| GET | `/api/v1/sessions?include_messages=false` | List sessions (titles only) | Lazy loading; response shape `{ sessions: BackendSession[] }` |
| GET | `/api/v1/sessions/{sessionId}` | Get session with full messages | Used on session open / switch |
| PUT | `/api/v1/sessions/{sessionId}` | Update session title | Body `{ title }`; ID converted to backend integer |
| DELETE | `/api/v1/sessions/{sessionId}` | Delete session | |

There are **no message-level endpoints**: no add/update/delete message routes exist — messages are created implicitly by the backend chat endpoint, and `addMessage`/`deleteMessage`/`syncMessage`/`syncAllMessages` are no-ops.

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `apiClient` (`services/apiClient.ts`) | HTTP client (`EnhancedApiClient`) | All network calls; provides auth token header, 3 retries, 10s timeout, `ApiResponse<T>` wrapping |
| `frontendLoggingService` | logging service | debug/info/warning/error logging with component tag `'SessionSyncService'` |
| `IdService` (`services/domain/IdService`) | ID conversion utility | `toFrontend()` / `toBackend()` between frontend string IDs and backend integer IDs; `isTempId` used by consumers to skip backend sync for temp sessions |
| `ConversationSession`, `ConversationMessage` (`types/agentInteraction`) | types | Output type of `convertToFrontendSession` / input of sync no-ops |

## Usage Example

```ts
import { sessionSyncService } from '../services/sessionSyncService'

// List titles (lazy) then open one session with full messages
const sessions = await sessionSyncService.getSessions()          // no messages
const full = await sessionSyncService.getSession(sessions[0].id) // with messages
const session = sessionSyncService.convertToFrontendSession(full)

// Create + rename + delete
const created = await sessionSyncService.createSession('tmp-id', 'New Session', agentId, model)
await sessionSyncService.updateSessionTitle(created.id, 'Renamed')
await sessionSyncService.deleteSession(created.id)

// Initial bulk load (5-way concurrency limit)
const all = await sessionSyncService.reloadSessionsWithMessages()
```

## Data Flow / Notes

- **ID mapping**: frontend string IDs ↔ backend integer IDs via `IdService`; `updateSessionTitle` and `createSession` convert on the way out, `convertToSessionResponse` converts on the way in. Consumers (e.g. `useSessionManagement.handleDeleteSession`) check `IdService.isTempId()` to avoid syncing temp sessions that don't exist on the backend.
- **Two conversion paths**: `convertToSessionResponse` (private) normalizes raw backend responses into `SessionSyncResponse`; `convertToFrontendSession` (public) turns those into `ConversationSession`. Both are defensive about metadata shape (flat snake_case fields vs. nested camelCase `metadata`).
- **Lazy-loading sync strategy**: `getSessions()` returns titles only; messages are fetched per-session via `getSession()` when a session is selected/switched (see `useSessionManagement.handleSwitchSession`). `SessionsService` previously polled on a 30s interval (`startBackgroundSync`), but that interval is **disabled/commented out** — there is no polling and no websocket/event channel; all sync is request-driven or backend-auto-saved during chat.
- **Failure semantics**: every method except `getSessions()` logs the error via `frontendLoggingService.error` and rethrows. `getSessions()` catches and returns `[]` (callers treat an empty list as "keep existing cached state"). `reloadSessionsWithMessages()` degrades gracefully per-session.
- **Error detection**: `updateSessionTitle` additionally inspects `'error' in response && response.error` and throws `Backend error: {message}`.
- **Title/model fallbacks**: null backend title → `New Session ${Date.now()}`; missing model → `'llama3.2'` with a logged warning (the default `llama3.2` fallback is a deliberate FIX-marker in the source — still present as of this doc).

## Related

Consumers (traced):
- `hooks/useSessionManagement.ts` — primary consumer: `getSessions` + `convertToFrontendSession` on mount, `createSession`, `getSession` on switch, `deleteSession`, `reloadSessionsWithMessages`, `updateSessionTitle` on rename
- `services/domain/SessionsService.ts` — `loadFromBackend(includeMessages)` → `getSessions()` / `reloadSessionsWithMessages()`; consumed by `pages/Sessions.tsx`
- `pages/Sessions.tsx` — sessions management UI (via `SessionsService`)
- `components/sessions/SessionTable.tsx`, `components/sessions/SessionDetailsModal.tsx` — dynamic `import('../../services/sessionSyncService')`; `getSession` + `convertToFrontendSession` to load/activate a session
- `hooks/useAgentInteraction.ts` — `createSession`, `deleteMessage`
- `hooks/useAIHub.ts` — `getSessions` + `convertToFrontendSession`, `createSession`, `getSession`
- `services/index.ts` — re-exports `sessionSyncService`
