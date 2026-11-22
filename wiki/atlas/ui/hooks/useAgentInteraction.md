---
title: useAgentInteraction
type: atlas-hook
path: frontend/src/hooks/useAgentInteraction.ts
confidence: high
updated: 2026-08-01
tags: [type/hook, domain/atlas-ui]
---
# useAgentInteraction

**Path**: `frontend/src/hooks/useAgentInteraction.ts`
**Type**: hook

## Purpose
The orchestrator hook for the entire chat interaction feature (854 lines — the largest hook in the app). It composes four sub-hooks — `useAgentSelection`, `useSessionManagement`, `useChatStreaming`, `useChatPersistence` — and coordinates agent selection, session lifecycle (temp → backend commit), SSE chat streaming, attachment upload, auto title generation, conversation export/import, and cognitive-pipeline state. It is the single entry point consumed by the `AgentInteraction` page.

## Exported API
```typescript
interface UseAgentInteractionReturn {
  // State
  agents: Agent[]
  sessions: ConversationSession[]
  state: AgentInteractionState

  // Agent actions
  handleAgentSelect: (agent: Agent) => void

  // Session actions
  handleSessionSelect: (session: ConversationSession) => Promise<void>
  handleSessionDelete: (sessionId: string) => void
  handleSessionRename: (sessionId: string, newTitle: string) => void
  handleGenerateTitle: (sessionId: string) => Promise<void>
  handleReloadSessions: () => Promise<void>
  handleCloseSession: () => void

  // Chat actions
  handleSendMessage: (content: string, overrideModel?: string, attachments?: File[]) => Promise<void>
  handleClearMessages: () => void
  handleDeleteMessage: (messageId: string) => Promise<void>
  handleExportConversation: () => Promise<void>
  handleImportSession: (importedSession: ConversationSession) => void
  handleSaveSession: () => Promise<void>
  createNewSession: (agent?: Agent) => ConversationSession | null
  stopStreaming: () => void

  // Selected agent (for backward compatibility)
  selectedAgent: Agent | null

  // Cognitive pipeline state
  cognitiveState: CognitiveState
  getCognitiveState: () => CognitiveState
}
```

`state` shape (`AgentInteractionState` from `types/agentInteraction` — note `connectionStatus` is hardcoded `'idle'` and `error` is the combined `agentError || sessionError || streamingError`):

```typescript
interface AgentInteractionState {
  selectedAgent: Agent | null
  currentSession: ConversationSession | null
  isStreaming: boolean
  connectionStatus: 'idle' | 'connecting' | 'connected' | 'error' | 'closed'
  error: string | null
  isLoadingAgents: boolean
  isReloadingSessions?: boolean
}
```

`cognitiveState` shape (`CognitiveState` from `services/domain/StreamingService`):

```typescript
interface CognitiveState {
  events: CognitiveEvent[]          // ordered cognitive_* SSE events from current stream
  latestTrace: CognitiveTraceCompleteEvent | null
  isActive: boolean
  executorStage: string             // e.g. 'streaming', 'thinking', 'idle'
}
```

Behavioral notes (from source):
- `handleSendMessage` throws `No session available` if there is no active session. It does not judge provider availability — that is the SERVER's pre-turn refusal (`domain.providers.refusal.refusal_statement`, read in `backend/app/api/v1/chat/router.py` before the pipeline starts), whose sentence ends the stream on the error frame. It uploads all `attachments` via `attachmentService.uploadAttachment(sessionId, file)` (continues without attachments if upload fails), then delegates to `startStream(content, overrideModel, attachmentIds)`. The user message is NOT added here — `StreamingService` adds it via the `onAddMessage` callback to avoid duplicates.
- `createNewSession(agent?)` creates a lazy temp session (`IdService.generateTempId()`, unique title `New Session {timestamp}`), registers it via `addLocalSession`, and sets the `pendingSession` flag. It is not synced to the backend until the first stream completes.
- `handleGenerateTitle` throws `Need at least 2 messages (user + assistant) to generate title` / `No assistant messages found to generate title from` when prerequisites are unmet; otherwise queues `titleService.generateTitleInBackground` with the last 10 messages (500 chars each), resolving the model from settings (`titleModelPreference`: `'agent'` → `${agent.provider}/${agent.model}`, `'custom'` → `titleCustomModel`, `'backend_default'` → `null`).
- `handleImportSession` re-IDs the imported session with a fresh temp ID and syncs it via `sessionSyncService.createSession` (fire-and-forget with warning log; falls back to `llama3.1:latest` if the selected agent has no model).
- `handleExportConversation` builds a text/plain blob (`conversation-{sessionId}-{timestamp}.txt`) and triggers a browser download; toasts success/failure via `useNotificationStore`.
- `handleSaveSession` pushes the session title (`updateSessionTitle`) then syncs every message (`syncMessage`), retrying each once after 1s on failure.

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| useAgentSelection | hook (`./useAgentSelection`) | Agents list, `selectedAgent`, loading state, `selectAgent` (exposed as `handleAgentSelect`) |
| useSessionManagement | hook (`./useSessionManagement`) | Sessions list, `currentSession`, delete/switch/reload/rename/replace/close, `addMessage`/`updateMessage`, `addLocalSession` |
| useChatStreaming | hook (`./useChatStreaming`) | `isStreaming`, `startStream`/`stopStream` (exposed as `stopStreaming`), `cognitiveState`, `getCognitiveState`; thin React wrapper over StreamingService |
| useChatPersistence | hook (`./useChatPersistence`) | Restores `selectedAgentId`/`currentSessionId` from localStorage; drives mount-time session restore |
| StreamingService | `services/domain/StreamingService` (via useChatStreaming) | SSE stream engine: AbortController cancellation, `chatService.createStreamingChatCompletion` with `stream: true`, SSE parsing of `event:`/`data:` lines, 100ms throttled UI updates, `CONTEXT_WINDOW = 20` message trimming, cognitive event accumulation |
| chatService | `services/domains/llm/chatService` (via StreamingService) | `createStreamingChatCompletion(request, { signal })`; `ChatMessage`, `ChatCompletionRequest` types |
| sessionSyncService | `services/sessionSyncService` | Backend session persistence: `createSession`, `deleteMessage`, `updateSessionTitle`, `syncMessage` |
| titleService | `services/domain/TitleService` | `generateTitleInBackground(sessionId, content, modelString, force)` for auto + manual title generation |
| sessionsService | `services/domain/SessionsService` | Backward-compat subscription to session list changes (data already lives in Zustand) |
| currentSessionService | `services/domain/CurrentSessionService` | `setContext(currentSession, selectedAgent)` keeps backend context service in sync |
| attachmentService | `services/domain/AttachmentService` | `uploadAttachment(sessionId, file)` → `{ id, original_filename, file_size }` |
| IdService | `services/domain/IdService` | `generateTempId()` (temp session IDs), `isTempId()` (commit decision), `equals()` |
| frontendLoggingService | `services/frontendLoggingService` | Structured logging (stream lifecycle, title gen, session commit, attachment upload) |
| useCognitiveHubStore | `stores/cognitiveHubStore` | Zustand source of truth: agents, sessions, `activeSession`, `activeAgent`, `setPendingSession` |
| useNotificationStore | `stores/notificationStore` | `addError`/`addSuccess` toasts for export/import flows |
| useSettingsStore | `stores/settingsStore` | `enableAutoTitle`, `titleModelPreference`, `titleCustomModel` |
| Agent, ConversationSession, ConversationMessage, AgentInteractionState | `types/agentInteraction` | Data shapes |
| CognitiveEvent, CognitiveState | `services/domain/StreamingService` | Cognitive pipeline types |

## Usage Example
```tsx
// pages/AgentInteraction.tsx (primary consumer)
const {
  agents,
  sessions,
  state,
  handleAgentSelect,
  handleSendMessage,
  handleSessionSelect,
  handleSessionDelete,
  handleSessionRename,
  handleGenerateTitle,
  handleImportSession,
  createNewSession,
  handleReloadSessions,
  handleCloseSession,
  handleClearMessages,
  stopStreaming,
  cognitiveState,
  getCognitiveState,
} = useAgentInteraction()

const { selectedAgent, currentSession, isStreaming, isReloadingSessions } = state

// Send with attachments
await handleSendMessage('Analyze this file', undefined, [file])

// New session (temp until first stream completes)
const session = createNewSession(selectedAgent)
```

## State / Data Flow
- **Composition**: reads agent + session state from sub-hooks, then re-exposes handlers; all mutable chat state lives in `useCognitiveHubStore` (Zustand), read via `getState()` inside callbacks to avoid stale closures.
- **Send pipeline**: `handleSendMessage` → session check → attachment upload → `startStream` (user message is added by StreamingService via `onAddMessage` → `addMessage(sessionId, message)`; deltas via `onUpdateMessage` → `updateMessage`).
- **SSE integration**: StreamingService opens the stream via `chatService.createStreamingChatCompletion` (fetch-based, `stream: true`, `AbortController` signal) and parses `event:`/`data:` lines from `response.body`. Regular chunks accumulate into the assistant message (100ms throttle); `cognitive_*` events (`cognitive_context_built`, `cognitive_executor_started`, `cognitive_executor_progress`, `cognitive_executor_completed`, `cognitive_memory_updated`, `cognitive_response_formatted`, `cognitive_trace_complete`) update `CognitiveState`, surfaced here as `cognitiveState`/`getCognitiveState`.
- **Session commit**: temp sessions are committed to the backend only after streaming completes. `handleStreamComplete` updates the message in the store, then in a microtask: (1) if the session still has a temp ID, `commitPendingSession` calls `sessionSyncService.createSession` and `replaceSession` with the merged messages (skipped if the backend already created the session during streaming); (2) auto-title generation triggers when `messagesCount >= 2` and the title is missing or starts with `New Session`, respecting `enableAutoTitle` and `titleModelPreference` settings.
- **Persistence**: `useChatPersistence` saves `selectedAgentId`/`currentSessionId` to localStorage on change; on mount the hook restores the session via `switchSession` (guarded by `hasRestoredRef`, only when backend sessions exist and the active session has no messages).
- **Service sync**: `currentSessionService.setContext(currentSession, selectedAgent)` runs on every session/agent change; `sessionsService.subscribe` is kept for backward compatibility (no merge needed).

## Related
- `pages/AgentInteraction.tsx` — primary consumer (destructures the full return, reads `state` fields)
- `hooks/index.ts` — re-export
- Sub-hooks: `useAgentSelection`, `useSessionManagement`, `useChatStreaming` (see `useChatStreaming.md`), `useChatPersistence`; chat macros live in the separate `useChatMacros` hook
- Services: `services/domain/StreamingService`, `services/domains/llm/chatService`, `services/sessionSyncService`, `services/domain/TitleService`, `services/domain/SessionsService`, `services/domain/CurrentSessionService`, `services/domain/AttachmentService`, `services/domain/IdService`
- Stores: `stores/cognitiveHubStore`, `stores/notificationStore`, `stores/settingsStore`
