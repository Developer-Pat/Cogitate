---
title: SessionService
type: atlas-service
path: frontend/src/services/domain/SessionService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---

# SessionService (domain)

**Path**: `frontend/src/services/domain/SessionService.ts`
**Type**: service (exported class — instantiate per use; no singleton exported)

## Purpose
Domain-layer session service managing conversation sessions: session CRUD against the backend (via `sessionSyncService`), backend↔frontend conversion of session/message shapes, temp (unsynced) session support, and pure immutable helpers for session/message state mutations. The class docstring says it "works with cognitiveHubStore for state management", but the current code has no store imports — it only returns updated session objects for callers to merge into state themselves.

> ⚠️ NOTE: this class is NOT imported by any production code. See **Deprecation / Obsolete Notes**.

## Exported API
Single export — `export class SessionService` (no default export, no singleton). Exact signatures:

```typescript
export class SessionService {
  async loadSessions(): Promise<ConversationSession[]>
  async loadSession(sessionId: string): Promise<ConversationSession>
  async createSession(title: string, agentId: string, model: string): Promise<ConversationSession>
  async deleteSession(sessionId: string): Promise<boolean>
  async updateSessionTitle(sessionId: string, newTitle: string): Promise<ConversationSession>
  async reloadSessionsWithMessages(): Promise<ConversationSession[]>

  private convertBackendSession(backendSession: BackendSession | SessionSyncResponse): ConversationSession

  createTempSession(title: string, agentId: string, _model: string): ConversationSession
  isTempSession(sessionId: string): boolean
  mergeSessionMessages(targetSession: ConversationSession, sourceSession: ConversationSession): ConversationSession
  clearMessages(session: ConversationSession): ConversationSession
  addMessage(session: ConversationSession, message: ConversationMessage): ConversationSession
  updateMessage(session: ConversationSession, messageId: string, content: string, metadata?: Record<string, unknown>): ConversationSession | null
  removeMessage(session: ConversationSession, messageId: string): ConversationSession | null
  findById(sessions: ConversationSession[], sessionId: string): ConversationSession | undefined
  getActiveSession(sessions: ConversationSession[]): ConversationSession | undefined
}
```

Notes:
- Async methods (loadSessions, loadSession, createSession, deleteSession, updateSessionTitle, reloadSessionsWithMessages) delegate to `sessionSyncService` and rethrow wrapped `Error` on failure.
- Sync methods are pure/immutable — they return new session objects and never mutate inputs or touch backend/store state.
- `_model` in createTempSession is accepted but unused (underscore-prefixed).

## Endpoints
This class makes no HTTP calls itself — it delegates to `sessionSyncService` (basePath `/api/v1/sessions`). Endpoints hit transitively:

| Method | Endpoint | Via |
|--------|----------|-----|
| loadSessions | `GET /api/v1/sessions?include_messages=false` | sessionSyncService.getSessions() |
| loadSession | `GET /api/v1/sessions/:id` | sessionSyncService.getSession() |
| createSession | `POST /api/v1/sessions` (body: `{ agent_id, title }`) | sessionSyncService.createSession() |
| deleteSession | `DELETE /api/v1/sessions/:id` | sessionSyncService.deleteSession() |
| updateSessionTitle | `PUT /api/v1/sessions/:id` (body: `{ title }`) | sessionSyncService.updateSessionTitle() |
| reloadSessionsWithMessages | `GET /api/v1/sessions?include_messages=false` then parallel `GET /api/v1/sessions/:id` per session (concurrency limit 5) | sessionSyncService.reloadSessionsWithMessages() |

Temp sessions (`IdService.isTempId(sessionId)`) skip backend deletes — `deleteSession` returns `true` without any API call.

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| sessionSyncService (`services/sessionSyncService.ts`) | singleton API client | All backend session/message HTTP + backend→SessionSyncResponse conversion |
| BackendSession, SessionSyncResponse (`services/sessionSyncService.ts`) | types | Input shapes accepted by convertBackendSession |
| frontendLoggingService (`services/frontendLoggingService.ts`) | singleton logger | debug/info/error logging tagged 'SessionService' |
| IdService (`services/domain/IdService.ts`) | class | generateTempId(), isTempId(), toFrontend()/toBackend() ID conversion |
| ConversationSession, ConversationMessage (`types/agentInteraction`) | types | Frontend session/message shapes |

## Usage Example
From the class JSDoc:

```typescript
const sessionService = new SessionService()
const sessions = await sessionService.loadSessions()
const session = await sessionService.createSession('My Chat', 'agent-1', 'gpt-4')
await sessionService.deleteSession(sessionId)
```

## Data Flow / Notes
- **Load path**: `sessionSyncService.getSessions()` → `convertBackendSession()` → `ConversationSession[]`; empty/null backend results return `[]`.
- **Create path**: generate temp ID first (`IdService.generateTempId()`) → POST to backend → convert returned `BackendSession` → `ConversationSession`.
- **Delete path**: temp IDs short-circuit (return `true`, no API call); otherwise DELETE and return `true`; failures rethrow `Failed to delete session: <msg>`.
- **updateSessionTitle** returns a minimal object `{ id, title, updatedAt }` cast as `ConversationSession` — the caller is expected to merge it into state.
- **convertBackendSession** accepts both backend shapes: `BackendSession` (has `is_active`; message metadata fields `token_count`/`total_time_ms`/`tokens_per_second`/`model`/`provider` directly on the message) and `SessionSyncResponse` (has `memory`; metadata nested under `msg.metadata`). Both normalize into `ConversationSession` with `metadata: { tokenCount, totalTimeMs, tokensPerSecond, model, provider }`.
- Message helpers (addMessage, updateMessage, removeMessage, clearMessages, mergeSessionMessages) are synchronous and non-mutating; updateMessage/removeMessage return `null` when the message ID isn't found.
- **mergeSessionMessages** keeps target's messages when non-empty, otherwise source's — intended for replacing a temp session with the synced backend session.
- The class docstring claims it "works with cognitiveHubStore", but the current implementation has no cognitiveHubStore/Zustand import — state integration is left to callers (compare `SessionsService`, which does write to cognitiveHubStore).

## Related
Consumers (imports of `services/domain/SessionService`):
- `frontend/src/services/domain/__tests__/SessionService.test.ts` — the ONLY consumer (731-line Vitest suite mocking `sessionSyncService` + `frontendLoggingService`; covers loadSessions/loadSession/createSession/deleteSession/updateSessionTitle/reloadSessionsWithMessages, temp-session logic, and conversion).

No components, hooks, or other services import this class. It is not re-exported from `services/index.ts`.

Sibling/overlapping services (see their own atlas docs):
- `frontend/src/services/domain/SessionsService.ts` — **ACTIVE**. Singleton state wrapper writing to cognitiveHubStore (Zustand); consumers: `pages/Sessions.tsx`, `hooks/useAgentInteraction.ts`, `components/sessions/SessionFilters.tsx`, `services/domain/HistoryService.ts`. Uses `sessionSyncService.getSessions()` / `reloadSessionsWithMessages()`.
- `frontend/src/services/sessionSyncService.ts` — **ACTIVE**. Pure API client (the layer this class delegates to); consumers: `hooks/useSessionManagement.ts`, `hooks/useAgentInteraction.ts`, `services/domain/TitleService.ts`, `services/domain/SessionsService.ts`, `components/sessions/SessionTable.tsx`, `components/sessions/SessionDetailsModal.tsx`.
- `frontend/src/services/domain/CurrentSessionService.ts` — **ACTIVE**. Session/agent context provider; consumers: `hooks/useAgentInteraction.ts`, `services/domain/TitleService.ts`.
- `frontend/src/services/domains/llm/sessionService.ts` — **DORMANT**. Interface `ISessionService` + class + `sessionService` singleton (raw apiClient wrapper adding `/status`, `/active`, `/end` endpoints); exported from `services/index.ts` barrel and `ServiceFactory.getSessionService()`, but no production call sites were found.

## Deprecation / Obsolete Notes
- No `@deprecated` / "legacy" / "unused" markers anywhere in the file.
- **ZERO production consumers**: the only import is the unit test file. The class is exported but never instantiated by components, hooks, or other services, and it is omitted from the `services/index.ts` barrel.
- Effective status: **dormant/obsolete code**. The codebase has moved on to `SessionsService` (state) + `sessionSyncService` (API) + `CurrentSessionService` (context), which together cover all of this class's functionality and have real consumers. The llm-domain `sessionService.ts` is similarly dormant (exported, never called).
- Not formally marked deprecated — flagged here so it can be verified for removal.
