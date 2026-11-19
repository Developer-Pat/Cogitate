---
title: StreamingService
type: atlas-service
path: frontend/src/services/domain/StreamingService.ts
confidence: high
updated: 2026-09-25
tags: [type/service, domain/atlas-ui]
---
# StreamingService

**Path**: `frontend/src/services/domain/StreamingService.ts`
**Type**: service

## Purpose

The chat streaming engine. Manages the full lifecycle of an SSE-streamed chat response: opens the stream through the LLM chat service, accumulates content chunks from the `ReadableStream` body, throttles UI updates (100 ms debounce), finalizes the assistant message with backend or locally-computed metadata, and parses/routes `cognitive_*` SSE events into a typed cognitive state.

It is core chat infrastructure — the single place where streaming, message creation, temp-session promotion, truncation detection, and post-stream message persistence are orchestrated. It is a plain class (not a singleton); the React layer instantiates one per hook instance via `useChatStreaming`.

## Exported API (exact signatures)

Single named export: `export class StreamingService` (no default export). The file also exports the types below.

### Public methods

```ts
constructor()

getCognitiveState(): CognitiveState
// Returns a defensive copy: { ...this.cognitiveState, events: [...this.cognitiveState.events] }

async startStream(content: string, options: StreamingOptions): Promise<void>
// Throws 'No session available' if useCognitiveHubStore has no activeSession.
// Validates agent model against backend, creates user + assistant messages,
// calls chatService.createStreamingChatCompletion, processes the SSE body,
// finalizes the message, and syncs both messages to the backend.

stopStream(): void
// Aborts streamController, clears isStreaming/streamingMessage, cancels pending update timer.

getState(): { isStreaming: boolean; streamingMessage: ConversationMessage | null; error: string | null }
```

### Exported interfaces & types

```ts
export interface CognitiveComponentData {
  component: string
  strategy: string
  duration_ms: number
  tokens_used?: number
  error?: string | null
  metadata?: Record<string, unknown>
}

export interface CognitiveContextBuiltEvent {
  component: 'context_builder'
  strategy: string
  duration_ms: number
  tokens_used: number
  sources: string[]
  error?: string | null
}

export interface CognitiveExecutorStartedEvent {
  component: 'executor'
  strategy: string
}

export interface CognitiveExecutorProgressEvent {
  component: 'executor'
  token_count: number
  tool_calls: number
  stage: string
}

export interface CognitiveExecutorCompletedEvent {
  component: 'executor'
  strategy: string
  duration_ms: number
  tokens_used: number
  error?: string | null
}

export interface CognitiveMemoryUpdatedEvent {
  component: 'memory_manager'
  strategy: string
  duration_ms: number
  compaction_triggered: boolean
  stored_keys: string[]
  error?: string | null
}

export interface CognitiveResponseFormattedEvent {
  component: 'response_formatter'
  strategy: string
  duration_ms: number
  error?: string | null
}

export interface CognitiveTraceCompleteEvent {
  trace: {
    context_builder: CognitiveComponentData
    executor: CognitiveComponentData
    memory_manager: CognitiveComponentData
    response_formatter: CognitiveComponentData
    total_duration_ms: number
    total_tokens: number
  }
  metrics: {
    total_duration_ms: number
    total_tokens: number
    llm_calls: number
    tool_calls: number
    cache_hits: number
  }
  memory_delta: {
    stored_keys: string[]
    evicted_keys: string[]
    compaction_triggered: boolean
  } | null
  error?: string | null
}

export type CognitiveEvent =
  | { type: 'cognitive_context_built'; data: CognitiveContextBuiltEvent }
  | { type: 'cognitive_executor_started'; data: CognitiveExecutorStartedEvent }
  | { type: 'cognitive_executor_progress'; data: CognitiveExecutorProgressEvent }
  | { type: 'cognitive_executor_completed'; data: CognitiveExecutorCompletedEvent }
  | { type: 'cognitive_memory_updated'; data: CognitiveMemoryUpdatedEvent }
  | { type: 'cognitive_response_formatted'; data: CognitiveResponseFormattedEvent }
  | { type: 'cognitive_trace_complete'; data: CognitiveTraceCompleteEvent }

export interface CognitiveState {
  /** Ordered list of cognitive events received during the current stream */
  events: CognitiveEvent[]
  /** Latest trace data (set when cognitive_trace_complete arrives) */
  latestTrace: CognitiveTraceCompleteEvent | null
  /** Whether the cognitive pipeline is currently active */
  isActive: boolean
  /** Current executor stage (e.g. 'streaming', 'thinking', 'idle') */
  executorStage: string
}

export interface StreamingCallbacks {
  onStreamStart?: () => void
  onStreamComplete?: (message: ConversationMessage) => void
  onStreamError?: (error: Error) => void
  onAddMessage?: (message: ConversationMessage, sessionId: string) => void
  onUpdateMessage?: (messageId: string, content: string, metadata?: unknown, sessionId?: string) => void
  /** Called when a cognitive SSE event is received */
  onCognitiveEvent?: (event: CognitiveEvent) => void
}

export interface StreamingOptions {
  agent: Agent
  sessionId: string  // Pass ID instead of session object
  callbacks: StreamingCallbacks
  attachmentIds?: number[]  // Attachment IDs to include in message context
}

// NOTE: StreamingResult and StreamChunk are exported but have no consumers (see Deprecation notes).
export interface StreamingResult {
  isStreaming: boolean
  streamingMessage: ConversationMessage | null
  error: string | null
  abortController: AbortController | null
}

export interface StreamChunk {
  content: string
  finishReason?: string | null
  metadata?: unknown
}
```

### Private methods (internal pipeline)

`resetCognitiveState()`, `validateAgentModel(agent)`, `processStream(body, messageId, sessionId, callbacks)`, `processSSELine(line, accumulatedContent, messageId, sessionId, callbacks)`, `buildCognitiveEvent(eventType, data)`, `updateCognitiveState(event)`, `throttledUpdate(messageId, content, sessionId, callbacks)`, `flushPendingUpdate(...)`, `finalizeMessage(messageId, accumulatedContent, agent, sessionId, userMessage, callbacks)`, `syncMessages(sessionId, userMessage, assistantMessage)`, `handleError(err, callbacks)`, `showTruncationNotification()`.

## Endpoints

| Endpoint | Method | Used for | Via |
|---|---|---|---|
| `/api/v1/chat/stream` | POST (SSE) | Streaming chat completion; body: `{ agent_id, message, session_id, stream: true, attachment_ids }` | `chatService.createStreamingChatCompletion` → `apiClient.stream` |
| `/api/v1/agents/{id}` | GET | Stale-agent model validation before streaming (only when `agent.isStale` or no `lastRefreshed`); failure is non-blocking | `apiClient.get` |
| Message persistence | — | `sessionSyncService.syncMessage(sessionId, message)` — currently a no-op; backend auto-saves messages when the chat endpoint is called | `sessionSyncService` |

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `chatService` (`../domains/llm/chatService`) | service singleton | `createStreamingChatCompletion(request, { signal })` — opens the SSE stream |
| `sessionSyncService` (`../sessionSyncService`) | service singleton | `syncMessage(sessionId, message)` — post-stream message persistence (currently no-op) |
| `frontendLoggingService` (`../frontendLoggingService`) | service singleton | Debug/info/warning/error logging throughout |
| `MetricsService` (`./MetricsService`) | class (instantiated in constructor) | `calculateStreamMetrics(content, durationMs, model, provider)` — fallback metadata when backend sends none |
| `MessageService` (`./MessageService`) | class (instantiated in constructor) | `createUserMessage(content, agentId)` / `createAssistantMessage(agentId, isStreaming)` |
| `apiClient` (`../apiClient`) | HTTP client | `GET /api/v1/agents/{id}` for stale model validation |
| `useCognitiveHubStore` (`../../stores/cognitiveHubStore`) | zustand store | `getState().activeSession`, `setActiveSession`, `setSessions`, `upsertSession`, `addToPendingQueue` — session source of truth + temp-session promotion |
| `useNotificationStore` (`../../stores/notificationStore`) | zustand store (dynamic `import()`) | `addNotification` — 'Response Truncated' warning |
| `Agent`, `ConversationMessage`, `MessageMetadata` (`../../types/agentInteraction`) | types | Public API types |
| `ChatMessage`, `ChatCompletionRequest` (`../domains/llm/chatService`) | types | Request shaping |

## Usage Example

Direct service usage (as documented in the class JSDoc):

```ts
import { StreamingService } from '../services/domain/StreamingService'

const streamingService = new StreamingService()
const result = await streamingService.startStream(content, {
  agent,
  sessionId: session.id,
  callbacks: {
    onStreamStart: () => console.log('stream started'),
    onUpdateMessage: (messageId, content) => console.log(content),
    onStreamComplete: (message) => console.log('done', message),
    onStreamError: (error) => console.error(error),
    onCognitiveEvent: (event) => console.log('cognitive', event.type),
  },
})
streamingService.stopStream()
```

Normal app usage goes through `useChatStreaming` (see Related), which instantiates the service internally:

```ts
const { startStream, stopStream, isStreaming, cognitiveState, getCognitiveState } = useChatStreaming({
  agent, session,
  onAddMessage, onUpdateMessage, onMessageComplete, onCognitiveEvent,
})
await startStream('Hello', undefined, attachmentIds)
```

## Data Flow / Notes

1. **startStream flow**: reads `activeSession` from `useCognitiveHubStore` (ignores the `options.sessionId` for the session itself — it's only used for callback routing and is noted as potentially stale from a React closure) → validates agent model → `isStreaming = true`, resets cognitive state → fires `onStreamStart` → creates `AbortController` → creates user + assistant messages via `MessageService` and fires `onAddMessage` for both → builds `ChatCompletionRequest` (last `CONTEXT_WINDOW = 20` session messages + new user message; `stream: true`; `profile: agent.id`; `session_id: 0` for temp sessions or the parsed int id; `generate_title: false`; `attachment_ids`) → `chatService.createStreamingChatCompletion(request, { signal })`. The request carries **no sampling and no budget**: an agent's own declaration is the server's to resolve, and the transport (`chatService`) builds its backend body from `agent_id` / `message` / `session_id` / `stream` / `attachment_ids`, so a client-side pair would travel nowhere.
2. **SSE processing** (`processStream`/`processSSELine`): reads the body with a `TextDecoder`, buffers partial lines, and handles per line:
   - `event: <type>` — tracks the event type for the next `data:` line (only `cognitive_*` types are retained in `currentEventType`; other event names are passed through and handled by their data payload).
   - `data: [DONE]` or `data: {}` — stream complete.
   - `data: {"session_id": N, ...}` (no `choices`, no `done`) — backend created the session during streaming (temp-session promotion): updates `useCognitiveHubStore` active session + sessions list immediately.
   - `data: {"session_id": N, "title": ...}` — title event; explicitly ignored (titles are generated in the background).
   - `data: {"done": true, "metadata": {...}}` — final chunk; stores `backendMetadata`, fires truncation notification if `metadata.truncated`, fires `onUpdateMessage`, marks stream complete.
   - `data: {"choices":[{"delta":{"content": ...}, "finish_reason": ...}]}` — content chunk appended to accumulated content; `finish_reason: 'length'` marks truncation (`truncationReason: 'max_tokens'`).
   - Cognitive events (below) routed to `onCognitiveEvent` and internal `cognitiveState`.
3. **Throttled UI updates**: `onUpdateMessage` fires at most every `STREAM_UPDATE_INTERVAL_MS = 100` ms via `throttledUpdate`; a trailing timer flushes the final pending update (`flushPendingUpdate`) after the stream ends.
4. **finalizeMessage**: clears streaming state, fallback truncation check (only when the done frame carried `metadata.budget.sent`: estimated tokens `content.length / 4` ≥ 95% of that number — the SERVER's, never the client's copy of the declaration and never an invented default; a frame with no budget raises no estimate, leaving the server's `truncated` flag as the authority), builds final metadata (backend metadata merged with model/provider fallback, else `MetricsService.calculateStreamMetrics`), fires `onStreamComplete` with the finalized `ConversationMessage`, then `syncMessages` (user + assistant) with failed syncs queued via `addToPendingQueue`.
5. **Cognitive events** (SSE `event: cognitive_*`): `cognitive_context_built`, `cognitive_executor_started`, `cognitive_executor_completed`, `cognitive_memory_updated`, `cognitive_response_formatted`, `cognitive_trace_complete` — plus `cognitive_executor_progress` (updates `executorStage`). `updateCognitiveState` maintains `isActive` (true on context_built/executor_started, false on trace_complete) and `executorStage` ('thinking' on executor_started, event `stage` on progress, 'idle' on completed/trace_complete). `cognitive_trace_complete` sets `latestTrace`.
6. **stopStream** aborts the controller and clears pending timers; user-initiated aborts do NOT surface as errors (`handleError` swallows `AbortError`). Other errors set `error = 'Failed to send message: ' + message` and fire `onStreamError`.

## Related

- **`useChatStreaming` hook** (`frontend/src/hooks/useChatStreaming.ts`) — the primary consumer. Instantiates a `StreamingService` per hook instance (`useRef`), wires `StreamingCallbacks` to React state, polls `getState()` + `getCognitiveState()` on a 100 ms interval, exposes `startStream(content, overrideModel?, attachmentIds?)`, `stopStream`, `sendMessage` (alias of startStream), `isStreaming`, `streamingMessage`, `error`, `cognitiveState`, `getCognitiveState`. Exported from `hooks/index.ts`.
- **`useAgentInteraction` hook** (`frontend/src/hooks/useAgentInteraction.ts`) — consumes `useChatStreaming` (line 414) and imports `CognitiveEvent`/`CognitiveState` types; relies on StreamingService's `onAddMessage` to add the user message.
- **`useAIHub` hook** (`frontend/src/hooks/useAIHub.ts`) — consumes `useChatStreaming` (line 124).
- **Components (type-only consumers)**: `CognitiveIndicator.tsx`, `CognitiveTraceDebugOverlay.tsx` (also `CognitiveTraceCompleteEvent`), `ResponseStream.tsx` (`CognitiveState`).
- **`cogitateDevTools.ts`** (`frontend/src/utils/`) — type-only (`CognitiveState`).
- **Tests**: `frontend/src/services/domain/__tests__/StreamingService.test.ts`.

## Deprecation / Obsolete Notes

- **Not deprecated.** No `@deprecated`/legacy markers in the source, and it is actively consumed (useChatStreaming → useAgentInteraction/useAIHub) plus covered by a dedicated test suite. This is core chat infrastructure.
- **Unused exports**: `StreamingResult` and `StreamChunk` are exported but have no importers anywhere in `frontend/src` — candidates for removal, though harmless.
- **`sessionSyncService.syncMessage` is a no-op** (backend auto-saves messages when the chat endpoint is called). The `syncMessages` + `addToPendingQueue` path in `finalizeMessage` is therefore effectively vestigial — it logs and queues but never performs a network call.
- **Commented-out tracing**: all `traceService.trace(...)` calls are commented out (diagnostic tracing disabled); `frontendLoggingService` is the active logging path.
- **`generate_title: false`** is hardcoded in the stream request ("DISABLED FOR DEBUGGING" per source comment) — backend title generation is off; titles are generated in the background elsewhere.
- **Legacy diagnostic block**: the `// [DIAGNOSTIC]` commented log in `startStream` references a removed `traceService` import pattern; the import itself has already been removed.

## SSE Error Events (F1 — fixed 2026-08-03)

Backend emits `event: error` + `data: {"error": {...}}` on LLM failure
(e.g. model not found, auth failure). Previously the frontend SILENTLY
DROPPED these — user saw an empty response. Now:
- `event: error` is tracked (currentEventType) and `parsed.error` routed
- Error is logged (frontendLoggingService), stream marked failed
- Generic toast via notificationStore (Provider error (provider/model))
- `onStreamError` callback fired → useAgentInteraction adds an
  agent-aware toast ("Agent X failed — message (provider/model)")

