import { chatService } from '../domains/llm/chatService'
import { sessionSyncService } from '../sessionSyncService'
import { frontendLoggingService } from '../frontendLoggingService'

import { MetricsService } from './MetricsService'
import { MessageService } from './MessageService'
import { apiClient } from '../apiClient'
import { useCognitiveHubStore } from '@/stores/cognitiveHubStore'
import { useNotificationStore } from '@/stores/notificationStore'
import type { Agent, ConversationMessage, MessageMetadata } from '@/types/agentInteraction'
import type { ChatMessage, ChatCompletionRequest } from '../domains/llm/chatService'

// Context window limit for messages sent to LLM
const CONTEXT_WINDOW = 20

// Debounce interval for UI updates during streaming (ms)
const STREAM_UPDATE_INTERVAL_MS = 100

// ---------------------------------------------------------------------------
// Cognitive event types
// ---------------------------------------------------------------------------

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

/**
 * StreamingService - Manage SSE streaming for chat responses
 *
 * Handles SSE stream connection, message accumulation, throttled updates,
 * and stream completion with metadata calculation.
 *
 * @example
 * ```typescript
 * const streamingService = new StreamingService()
 * const result = await streamingService.startStream(content, options)
 * streamingService.stopStream()
 * ```
 */
export class StreamingService {
  private metricsService: MetricsService
  private messageService: MessageService

  // Stream state
  private streamController: AbortController | null = null
  private streamingMessage: ConversationMessage | null = null
  private error: string | null = null
  private isStreaming = false

  // Throttling state
  private lastUpdateTime = 0
  private pendingUpdate = false
  private pendingContent = ''
  private updateTimer: ReturnType<typeof setTimeout> | null = null

  // Metadata state
  private backendMetadata: Record<string, unknown> | null = null

  // Cognitive state
  private cognitiveState: CognitiveState = {
    events: [],
    latestTrace: null,
    isActive: false,
    executorStage: 'idle',
  }

  /** Tracks the current SSE event type between `event:` and `data:` lines */
  private currentEventType: string | null = null

  constructor() {
    this.metricsService = new MetricsService()
    this.messageService = new MessageService()
  }

  /**
   * Get the current cognitive state.
   */
  getCognitiveState(): CognitiveState {
    return { ...this.cognitiveState, events: [...this.cognitiveState.events] }
  }

  /**
   * Reset cognitive state for a new stream.
   */
  private resetCognitiveState(): void {
    this.cognitiveState = {
      events: [],
      latestTrace: null,
      isActive: false,
      executorStage: 'idle',
    }
  }

  /**
   * Start streaming a response
   *
   * @param content - User message content
   * @param options - Streaming options (agent, session, callbacks)
   */
  async startStream(content: string, options: StreamingOptions): Promise<void> {
    const { agent, callbacks, attachmentIds } = options;
    const hubState = useCognitiveHubStore.getState()
    const session = hubState.activeSession

    // [DIAGNOSTIC] Log agent at entry point
    // traceService.trace('StreamingService', 'startStream:entry', {
      // agentId: agent.id,
      // agentModel: agent.model,
      // agentProvider: agent.provider,
      // loadedFrom: agent.loadedFrom,
      // lastRefreshed: agent.lastRefreshed,
      // isStale: agent.isStale,
      // sessionId: session?.id
    // }, ['data', 'validation'])

    // traceService.trace('StreamingService', 'startStream', {
      // sessionId: session?.id,
      // agentId: agent.id,
      // contentLength: content.length,
      // model: agent.model,
      // provider: agent.provider,
      // loadedFrom: agent.loadedFrom,
      // lastRefreshed: agent.lastRefreshed,
      // isStale: agent.isStale
    // }, ['lifecycle', 'user-action'])

    if (!session) {
      frontendLoggingService.error('StreamingService', 'No session available')
      throw new Error('No session available')
    }

    // [VALIDATION] Check agent model consistency with backend
    // This detects stale localStorage data before streaming
    await this.validateAgentModel(agent)

    // Use session from store (it's always fresh after commit)
    // The options sessionId may be stale from React closure

    try {
      this.isStreaming = true
      this.error = null
      this.backendMetadata = null
      this.resetCognitiveState()
      this.currentEventType = null

      callbacks.onStreamStart?.()

      // Create abort controller
      this.streamController = new AbortController()

      // Create messages
      const userMessage = this.messageService.createUserMessage(content, agent.id)
      const assistantMessage = this.messageService.createAssistantMessage(agent.id, true)

      this.streamingMessage = assistantMessage

      // Add messages via callback with session ID
      callbacks.onAddMessage?.(userMessage, session.id)
      callbacks.onAddMessage?.(assistantMessage, session.id)

      // Prepare request
      const recentMessages = (session.messages || []).slice(-CONTEXT_WINDOW)
      const chatMessages: ChatMessage[] = [
        ...recentMessages.map(msg => ({
          role: msg.role as 'user' | 'assistant' | 'system',
          content: msg.content
        })),
        { role: 'user', content }
      ]

      // Handle both temp and backend session IDs
      // Temp sessions (string IDs) will be created by backend automatically
      const sessionIdForBackend = parseInt(session.id)
      const isTempSession = isNaN(sessionIdForBackend)
      
      if (isTempSession) {
        frontendLoggingService.warning('StreamingService', 'Streaming to temp session - backend will create it', {
          sessionId: session.id
        })
      }

      const request: ChatCompletionRequest = {
        model: agent.model,
        messages: chatMessages,
        stream: true,
        profile: agent.id,
        session_id: isTempSession ? 0 : sessionIdForBackend,  // Use 0 for temp, backend will create
        // THE AUTO-TITLE FLAG (2026-09-09, B1): TRUE. The backend's
        // finalization only fires when the session title is still a
        // placeholder (None / "New Session" / "Untitled"), so it
        // self-limits to the first conversation — the hardcoded
        // false was a debugging leftover that left chat-created
        // sessions permanently untitled (the title service fired on
        // the temp id instead and 404'd).
        attachment_ids: attachmentIds
        // NO SAMPLING ON THE REQUEST (G4). This block carried `options.temperature` and
        // `options.top_p` read off the agent object, and the transport
        // (`chatService.createStreamingChatCompletion`) builds its backend request from
        // agent_id / message / session_id / stream / attachment_ids — it DROPPED `options`
        // entirely, so the pair travelled nowhere while looking like it did. Only
        // `/api/v1/chat/completions` reads `options`, and that is a no-agent surface for an
        // external caller: an agent's own sampling is the server's to resolve.
      }

      frontendLoggingService.debug('StreamingService', 'Starting stream', {
        model: request.model,
        sessionId: request.session_id
      })

      // Start streaming
      const response = await chatService.createStreamingChatCompletion(request, {
        signal: this.streamController.signal
      })

      if (!response.body) {
        throw new Error('No response body received')
      }

      // Process stream and get accumulated content
      const accumulatedContent = await this.processStream(response.body, assistantMessage.id, session.id, callbacks)

      // Finalize message with accumulated content
      await this.finalizeMessage(assistantMessage.id, accumulatedContent, agent, session.id, userMessage, callbacks)

      // traceService.trace('StreamingService', 'startStreamComplete', {
        // sessionId: session.id,
        // messageId: assistantMessage.id
      // }, ['lifecycle'])

    } catch (err) {
      // traceService.trace('StreamingService', 'startStreamError', {
        // error: String(err),
        // agentId: agent.id,
        // provider: agent.provider
      // }, ['error'])
      await this.handleError(err, callbacks)
    }
  }

  /**
   * Stop streaming
   */
  stopStream(): void {
    if (this.streamController) {
      frontendLoggingService.debug('StreamingService', 'Stopping stream')
      this.streamController.abort()
      this.streamController = null
    }

    if (this.isStreaming) {
      this.isStreaming = false
      this.streamingMessage = null
    }

    // Clear pending update
    if (this.updateTimer) {
      clearTimeout(this.updateTimer)
      this.updateTimer = null
      this.pendingUpdate = false
    }
  }

  /**
   * Get current streaming state
   */
  getState(): { isStreaming: boolean; streamingMessage: ConversationMessage | null; error: string | null } {
    return {
      isStreaming: this.isStreaming,
      streamingMessage: this.streamingMessage,
      error: this.error
    }
  }

  /**
   * Validate agent model matches backend
   * Detects stale localStorage data
   */
  private async validateAgentModel(agent: Agent): Promise<void> {
    try {
      // Only validate if agent appears stale
      if (agent.isStale || !agent.lastRefreshed) {
        const response = await apiClient.get<{model?: string; provider?: string}>(`/api/v1/agents/${agent.id}`)
        if (response.data) {
          const backendModel = response.data.model
          const cachedModel = agent.model
          
          if (backendModel !== cachedModel) {
            // [TRACE] Model mismatch detected
            // traceService.trace('StreamingService', 'modelMismatchDetected', {
              // agentId: agent.id,
              // cachedModel: cachedModel,
              // backendModel: backendModel,
              // provider: agent.provider
            // }, ['error', 'validation'])
            
            frontendLoggingService.error('StreamingService', 'Agent model mismatch - cached data is stale', {
              agentId: agent.id,
              cachedModel: cachedModel,
              backendModel: backendModel
            })
          } else {
            // [TRACE] Model validated
            // traceService.trace('StreamingService', 'modelValidated', {
              // agentId: agent.id,
              // model: backendModel,
              // validationTime: performance.now() - startTime
            // }, ['validation'])
          }
        }
      }
    } catch (error) {
      // Silently continue - don't block streaming for validation
      frontendLoggingService.warning('StreamingService', 'Agent validation skipped - backend unavailable', {
        agentId: agent.id,
        error: error instanceof Error ? error.message : 'Unknown error'
      })
    }
  }

  /**
   * Process SSE stream
   * @returns The accumulated content from the stream
   */
  private async processStream(
    body: ReadableStream<Uint8Array>,
    messageId: string,
    sessionId: string,
    callbacks: StreamingCallbacks
  ): Promise<string> {
    // traceService.trace('StreamingService', 'processStream START', { messageId })

    const reader = body.getReader()
    const decoder = new TextDecoder()
    let accumulatedContent = ''
    let chunkCount = 0
    let lineBuffer = ''
    let streamComplete = false

    const streamStartTime = performance.now()
    let firstChunkTime: number | null = null

    try {
      while (!streamComplete) {
        const { done, value } = await reader.read()

        if (done) {
          if (lineBuffer.trim()) {
            this.processSSELine(lineBuffer, accumulatedContent, messageId, sessionId, callbacks)
          }
          frontendLoggingService.debug('StreamingService', 'processStream END - reader done', {
            chunkCount,
            accumulatedContentLength: accumulatedContent.length
          })
          break
        }

        chunkCount++
        const chunk = decoder.decode(value, { stream: true })
        const fullText = lineBuffer + chunk
        const lines = fullText.split('\n')

        lineBuffer = fullText.endsWith('\n') ? '' : lines.pop() || ''

        for (const line of lines) {
          try {
            const result = this.processSSELine(line, accumulatedContent, messageId, sessionId, callbacks)
            if (result) {
              accumulatedContent = result.accumulatedContent
              if (result.firstChunkTime && !firstChunkTime) {
                firstChunkTime = result.firstChunkTime
              }
              if (result.streamComplete) {
                streamComplete = true
                break
              }
            }
          } catch (lineErr) {
            frontendLoggingService.error('StreamingService', 'Error processing SSE line', lineErr, {
              line: line.substring(0, 100)
            })
            // Continue processing other lines
          }
        }
      }
    } catch (readErr) {
      frontendLoggingService.error('StreamingService', 'Error reading stream', readErr, {
        chunkCount,
        accumulatedContentLength: accumulatedContent.length,
        lineBufferLength: lineBuffer.length
      })
      throw readErr
    } finally {
      reader.releaseLock()
    }

    // Flush pending update
    this.flushPendingUpdate(messageId, accumulatedContent, sessionId, callbacks)

    // traceService.trace('StreamingService', 'processStream COMPLETE', {
      // chunkCount,
      // totalCharacters: accumulatedContent.length
    // })

    // Log performance metrics
    const streamEndTime = performance.now()
    const totalStreamTime = streamEndTime - streamStartTime
    const totalCharacters = accumulatedContent.length
    const charsPerSecond = totalCharacters > 0 ? (totalCharacters / (totalStreamTime / 1000)) : 0

    frontendLoggingService.info('StreamingService', 'Stream completed', {
      totalCharacters,
      totalStreamTime: `${totalStreamTime.toFixed(0)}ms`,
      charsPerSecond: `${charsPerSecond.toFixed(1)} chars/s`,
      timeToFirstChunk: firstChunkTime ? `${(firstChunkTime - streamStartTime).toFixed(0)}ms` : 'N/A'
    })

    return accumulatedContent
  }

  /**
   * Process a single SSE line
   */
  private processSSELine(
    line: string,
    accumulatedContent: string,
    messageId: string,
    sessionId: string,
    callbacks: StreamingCallbacks
  ): { accumulatedContent: string; firstChunkTime?: number; streamComplete?: boolean } | null {
    if (!line.trim()) return null

    // Handle event type
    if (line.startsWith('event: ')) {
      const eventType = line.slice(7)

      // Track cognitive event types for the next data: line
      if (eventType.startsWith('cognitive_')) {
        this.currentEventType = eventType
        return { accumulatedContent }
      }

      // Track error events so the following data: line can be routed to
      // the error handler (backend emits `event: error` + `data: {"error": ...}`)
      if (eventType === 'error') {
        this.currentEventType = 'error'
        return { accumulatedContent }
      }

      // Event types are handled via their corresponding data lines
      // Just return and let the data: line be processed
      if (eventType === 'session_id' || eventType === 'session_title' || eventType === 'notification') {
        return { accumulatedContent }
      }
      return { accumulatedContent }
    }

    // Handle data
    if (line.startsWith('data: ')) {
      const data = line.slice(6)

      if (data === '[DONE]' || data === '{}') {
        return { accumulatedContent, streamComplete: true }
      }

      try {
        const parsed = JSON.parse(data)

        // ── Error event handling ──────────────────────────────────────────
        // Backend emits: event: error + data: {"error": {type, message,
        // error_class, provider, model, session_id}}. Previously this was
        // SILENTLY DROPPED — the user saw an empty response with no
        // explanation. Now: log it, surface via onStreamError + toaster.
        if (this.currentEventType === 'error' && parsed.error) {
          this.currentEventType = null // consume the event type
          const errorInfo = parsed.error
          // THE HONEST SENTENCE IS PREFERRED (2026-09-26). The backend now
          // classifies the failure and sends `user_message` beside the
          // provider's raw text — "The upstream for this model is overloaded or
          // unavailable — try another model, or the paid version of this one".
          // The raw text is a diagnostic; this is the sentence a person can act
          // on, so it is what the toast and the caller carry when it exists.
          const rawMessage = errorInfo.message || 'Unknown streaming error'
          const message = errorInfo.user_message || rawMessage
          const errorType = errorInfo.type || 'streaming_exception'
          const provider = errorInfo.provider
          const model = errorInfo.model

          frontendLoggingService.error('StreamingService', `SSE error (${errorType}): ${rawMessage}`, {
            errorClass: errorInfo.error_class,
            category: errorInfo.category,
            userMessage: errorInfo.user_message,
            provider,
            model,
            sessionId,
          })

          // Mark the stream as failed so consumers can reflect it in UI
          this.error = message
          this.isStreaming = false
          this.streamingMessage = null

          // Reset the cognitive pipeline indicators — on error the
          // `cognitive_trace_complete` event never arrives, so isActive stays
          // true and the "Thinking" spinner spins forever. Mirror the
          // trace-complete reset here.
          this.cognitiveState.isActive = false
          this.cognitiveState.executorStage = 'idle'

          // Surface a user-visible toast. A hard LIMIT STOP is not a failure: the
          // turn was stopped on purpose and the partial answer is kept (the
          // backend's `limit_stop`, D.3). It says what happened and it toasts as a
          // warning — the generic "Provider error" headline would claim a fault
          // that did not happen.
          const isLimitStop = errorType === 'limit_stop'
          const title = isLimitStop
            ? 'Turn stopped'
            : provider && model
              ? `Provider error (${provider}/${model})`
              : 'Chat error'
          const toaster = useNotificationStore.getState()
          if (isLimitStop) {
            toaster.addWarning(title, message, 6000)
          } else {
            toaster.addError(title, message, 6000)
          }

          // Notify the caller (useAgentInteraction's onStreamError → logging/state).
          // The type rides the Error so a consumer can tell a turn that was STOPPED
          // from one that FAILED — the agent-failure toast is for the latter.
          const streamError = new Error(message) as Error & { errorType?: string }
          streamError.errorType = errorType
          callbacks.onStreamError?.(streamError)

          // Stop processing this line — stream is effectively failed
          return { accumulatedContent, streamComplete: true }
        }

        // ── Cognitive event handling ──────────────────────────────────────
        // If we have a pending cognitive event type from a preceding event: line,
        // parse the data as a cognitive event and route it to the callback.
        if (this.currentEventType && this.currentEventType.startsWith('cognitive_')) {
          const eventType = this.currentEventType
          this.currentEventType = null // consume the event type

          const cognitiveEvent = this.buildCognitiveEvent(eventType, parsed)
          if (cognitiveEvent) {
            // Update internal cognitive state
            this.updateCognitiveState(cognitiveEvent)

            // Notify caller via callback
            callbacks.onCognitiveEvent?.(cognitiveEvent)
          }
          return { accumulatedContent }
        }

        // Handle session_id from backend (creates new session during streaming)
        // Backend sends: event: session_id followed by data: {"session_id": 18}
        if (parsed.session_id && typeof parsed.session_id === 'number' && !parsed.choices && !parsed.done) {
          frontendLoggingService.info('StreamingService', 'Backend session created during streaming', {
            tempSessionId: sessionId,
            backendSessionId: parsed.session_id
          })

          // Update the session ID in the store immediately
          try {
            const hubState = useCognitiveHubStore.getState()
            const currentSession = hubState.activeSession

            if (currentSession && currentSession.id === sessionId) {
              const backendSessionId = String(parsed.session_id)
              const updatedSession = {
                ...currentSession,
                id: backendSessionId
              }

              hubState.setActiveSession(updatedSession)

              const state = hubState
              const tempSessionIdx = state.sessions.findIndex(s => s.id === sessionId)

              if (tempSessionIdx >= 0) {
                state.sessions[tempSessionIdx] = updatedSession
                hubState.setSessions([...state.sessions])
              } else {
                hubState.upsertSession(updatedSession)
              }

              frontendLoggingService.debug('StreamingService', 'Session ID updated in store', {
                oldId: sessionId,
                newId: backendSessionId,
                replacedInList: tempSessionIdx >= 0
              })
            }
          } catch (updateErr) {
            frontendLoggingService.error('StreamingService', 'Failed to update session ID in store', updateErr)
          }

          return { accumulatedContent }
        }

        // Handle session title from backend (2026-09-09, B1): the
        // backend's finalization now generates the title itself, so
        // its event is APPLIED to the store session — the frontend's
        // own background job then sees a real title and skips (no
        // double generation, no rename-notification spam).
        if (parsed.session_id && parsed.title) {
          frontendLoggingService.info('StreamingService', 'Backend title event applied', {
            title: parsed.title,
            sessionId: parsed.session_id
          })
          try {
            const hubState = useCognitiveHubStore.getState()
            const targetId = String(parsed.session_id)
            const sessions = hubState.sessions.map(s =>
              s.id === targetId ? { ...s, title: parsed.title } : s
            )
            hubState.setSessions(sessions)
            const active = hubState.activeSession
            if (active && active.id === targetId) {
              hubState.setActiveSession({ ...active, title: parsed.title })
            }
          } catch (err) {
            frontendLoggingService.error('StreamingService', 'Failed to apply the backend title', err)
          }
          return { accumulatedContent }
        }

        // Handle metadata from final chunk
        if (parsed.done && parsed.metadata) {
          frontendLoggingService.info('StreamingService', 'Received backend metadata', parsed.metadata)

          // THE SETTLE GUARANTEE (2026-08-24, the user's report):
          // the last-message pipeline indicator kept running — the
          // trace-complete event can miss (the stream tail), so the
          // isActive stayed true and the spinner spun forever. The
          // error path already mirrors this reset; the DONE event
          // now guarantees the settle on the success path too.
          this.cognitiveState.isActive = false
          this.cognitiveState.executorStage = 'idle'
          // THE THINKING SEGREGATION (2026-08-24): merge — never
          // wipe the live-accumulated reasoning with an empty
          // backend field (the pre-fix done event had none).
          const mergedMetadata = {
            ...this.backendMetadata,
            ...parsed.metadata,
            reasoning: parsed.metadata.reasoning || this.backendMetadata?.reasoning || '',
          }
          this.backendMetadata = mergedMetadata

          if (parsed.metadata.truncated) {
            this.showTruncationNotification()
          }

          callbacks.onUpdateMessage?.(messageId, accumulatedContent, parsed.metadata, sessionId)
          return { accumulatedContent, streamComplete: true }
        }

        // Handle content chunk
        if (parsed.choices?.[0]?.delta) {
          const contentChunk = parsed.choices[0].delta.content
          const reasoningChunk = parsed.choices[0].delta.reasoning
          const finishReason = parsed.choices[0].finish_reason

          // THE THINKING SEGREGATION (2026-08-24): the reasoning
          // chunks accumulate separately and ride the message
          // metadata — the bubble's Thinking fold fills live; the
          // content stays clean.
          let accumulatedReasoning = ''
          if (reasoningChunk) {
            accumulatedReasoning += reasoningChunk
            this.backendMetadata = {
              ...this.backendMetadata,
              reasoning: accumulatedReasoning,
            }
            this.throttledUpdate(messageId, accumulatedContent, sessionId, callbacks, this.backendMetadata)
          }

          if (contentChunk) {
            accumulatedContent += contentChunk

            // Throttled update
            this.throttledUpdate(messageId, accumulatedContent, sessionId, callbacks)

            // Check for truncation
            if (finishReason === 'length') {
              frontendLoggingService.warning('StreamingService', 'Response truncated (finish_reason: length)')
              this.backendMetadata = {
                ...this.backendMetadata,
                truncated: true,
                truncationReason: 'max_tokens'
              }
            }
          }

          return { accumulatedContent }
        }
      } catch (parseError) {
        if (data.startsWith('{')) {
          console.warn('[StreamingService] Failed to parse SSE data:', parseError)
        }
      }
    }

    return { accumulatedContent }
  }

  /**
   * Build a typed CognitiveEvent from an SSE event type and parsed JSON data.
   * Returns null if the event type is unknown.
   */
  private buildCognitiveEvent(eventType: string, data: Record<string, unknown>): CognitiveEvent | null {
    switch (eventType) {
      case 'cognitive_context_built':
        return {
          type: 'cognitive_context_built',
          data: data as unknown as CognitiveContextBuiltEvent,
        }
      case 'cognitive_executor_started':
        return {
          type: 'cognitive_executor_started',
          data: data as unknown as CognitiveExecutorStartedEvent,
        }
      case 'cognitive_executor_progress':
        return {
          type: 'cognitive_executor_progress',
          data: data as unknown as CognitiveExecutorProgressEvent,
        }
      case 'cognitive_executor_completed':
        return {
          type: 'cognitive_executor_completed',
          data: data as unknown as CognitiveExecutorCompletedEvent,
        }
      case 'cognitive_memory_updated':
        return {
          type: 'cognitive_memory_updated',
          data: data as unknown as CognitiveMemoryUpdatedEvent,
        }
      case 'cognitive_response_formatted':
        return {
          type: 'cognitive_response_formatted',
          data: data as unknown as CognitiveResponseFormattedEvent,
        }
      case 'cognitive_trace_complete':
        return {
          type: 'cognitive_trace_complete',
          data: data as unknown as CognitiveTraceCompleteEvent,
        }
      default:
        frontendLoggingService.warning('StreamingService', `Unknown cognitive event type: ${eventType}`)
        return null
    }
  }

  /**
   * Update internal cognitive state based on an incoming cognitive event.
   */
  private updateCognitiveState(event: CognitiveEvent): void {
    this.cognitiveState.events.push(event)

    switch (event.type) {
      case 'cognitive_context_built':
        this.cognitiveState.isActive = true
        break

      case 'cognitive_executor_started':
        this.cognitiveState.isActive = true
        this.cognitiveState.executorStage = 'thinking'
        break

      case 'cognitive_executor_progress':
        this.cognitiveState.executorStage = event.data.stage
        break

      case 'cognitive_executor_completed':
        this.cognitiveState.executorStage = 'idle'
        break

      case 'cognitive_memory_updated':
        // Memory update — no stage change needed
        break

      case 'cognitive_response_formatted':
        // Response formatting — no stage change needed
        break

      case 'cognitive_trace_complete':
        this.cognitiveState.isActive = false
        this.cognitiveState.executorStage = 'idle'
        this.cognitiveState.latestTrace = event.data
        break
    }
  }

  /**
   * Throttled UI update
   */
  private throttledUpdate(messageId: string, content: string, sessionId: string, callbacks: StreamingCallbacks, metadata?: unknown): void {
    const now = performance.now()
    const timeSinceLastUpdate = now - this.lastUpdateTime

    if (timeSinceLastUpdate >= STREAM_UPDATE_INTERVAL_MS) {
      this.lastUpdateTime = now
      this.pendingUpdate = false

      callbacks.onUpdateMessage?.(messageId, content, metadata, sessionId)
    } else if (!this.pendingUpdate) {
      this.pendingUpdate = true
      this.pendingContent = content
      this.updateTimer = setTimeout(() => {
        if (this.pendingUpdate) {
          this.lastUpdateTime = performance.now()
          this.pendingUpdate = false
          // THE FORWARD-ONLY FIX (2026-09-01, the user's dance
          // report): the timer captured the content AT SCHEDULE —
          // the chunks that arrived while it waited never reached
          // it, so the display REGRESSED to the older text ('the
          // text appears and disappears in chunks... it backs up').
          // The pendingContent holds the LATEST — the timer fires
          // the newest text, the stream only moves forward.
          callbacks.onUpdateMessage?.(messageId, this.pendingContent, undefined, sessionId)
        }
      }, STREAM_UPDATE_INTERVAL_MS - timeSinceLastUpdate)
    } else {
      // THE FORWARD-ONLY (continued): the chunks that arrive while
      // a timer's pending update the pendingContent — the newest
      // text always wins.
      this.pendingContent = content
    }
  }

  /**
   * Flush pending update
   */
  private flushPendingUpdate(messageId: string, content: string, sessionId: string, callbacks: StreamingCallbacks): void {
    if (this.pendingUpdate) {
      this.lastUpdateTime = performance.now()
      this.pendingUpdate = false
      // the pendingContent — the latest wins (2026-09-01).
      callbacks.onUpdateMessage?.(messageId, this.pendingContent || content, undefined, sessionId)
    }
  }

  /**
   * Finalize the streaming message
   */
  private async finalizeMessage(
    messageId: string,
    accumulatedContent: string,
    agent: Agent,
    sessionId: string,
    userMessage: ConversationMessage,
    callbacks: StreamingCallbacks
  ): Promise<void> {
    // traceService.trace('StreamingService', 'finalizeMessage', {
      // messageId,
      // accumulatedContentLength: accumulatedContent.length,
      // userMessageId: userMessage.id
    // })

    this.isStreaming = false
    this.streamController = null

    // THE FALLBACK TRUNCATION CHECK (G.2, rewritten) — against the SERVER's number.
    //
    // This compared `content.length / 4` against `agent.parameters.maxTokens || 4000`:
    // the client's copy of the DECLARATION, plus an invented default, while the wire
    // carried a different number entirely (Bob declares 8192 and is sent 16000). A turn
    // could therefore be flagged as truncated for exceeding a budget nothing used — and
    // with the declaration now living in `llm_spec.max_output` the client could not even
    // read it. The frame carries what it carried (`metadata.budget.sent`, G-A ii), so
    // that is the number the estimate is judged against; when the frame carries none
    // (a turn that never reached a provider), NO estimate runs — the server's own
    // `truncated` flag is the authority, and this is the courtesy behind it.
    const sentBudget = (this.backendMetadata?.budget as { sent?: number } | undefined)?.sent
    const estimatedTokens = Math.round(accumulatedContent.length / 4)
    const isNearTokenLimit =
      typeof sentBudget === 'number' && estimatedTokens >= sentBudget * 0.95

    if (isNearTokenLimit && !this.backendMetadata?.truncated) {
      frontendLoggingService.warning('StreamingService', 'Response truncated (token count fallback)', {
        estimatedTokens,
        sentBudget,
        model: agent.model,
        provider: agent.provider
      })
      this.backendMetadata = {
        ...this.backendMetadata,
        truncated: true,
        truncationReason: 'max_tokens_fallback'
      }
      // THE MESSAGE (2026-09-22): the estimate used to mark the metadata
      // and say NOTHING — the backend's finish_reason flag is the
      // authoritative signal, but a turn whose streams carried no stop
      // reason lands here, and the user must be told either way.
      this.showTruncationNotification()
    }

    // Calculate final metadata
    const streamEndTime = performance.now()
    const totalStreamTime = streamEndTime - (this.lastUpdateTime || streamEndTime)
    
    // Debug: Log backend metadata state
    // traceService.trace('StreamingService', 'finalizeMessage:debug', {
      // hasBackendMetadata: !!this.backendMetadata,
      // backendMetadataProvider: this.backendMetadata?.provider,
      // backendMetadataModel: this.backendMetadata?.model,
      // agentProvider: agent.provider,
      // agentModel: agent.model
    // })
    
    // FIX: Ensure backend metadata is used with correct provider/model
    const finalMetadata = this.backendMetadata 
      ? {
          ...this.backendMetadata,
          model: this.backendMetadata.model || agent.model,
          provider: this.backendMetadata.provider || agent.provider
        }
      : this.metricsService.calculateStreamMetrics(
          accumulatedContent,
          Math.round(totalStreamTime),
          agent.model,
          agent.provider
        )

    // Create final message
    const finalMessage: ConversationMessage = {
      id: messageId,
      role: 'assistant',
      content: accumulatedContent,
      timestamp: new Date(),
      agentId: agent.id,
      isStreaming: false,
      metadata: finalMetadata as unknown as MessageMetadata | undefined
    }

    this.streamingMessage = null

    // traceService.trace('StreamingService', 'callingOnStreamComplete', {
      // messageId: finalMessage.id,
      // contentLength: finalMessage.content.length
    // })
    callbacks.onStreamComplete?.(finalMessage)

    // Sync messages to backend
    await this.syncMessages(sessionId, userMessage, finalMessage)
  }

  /**
   * Sync messages to backend
   */
  private async syncMessages(
    sessionId: string,
    userMessage: ConversationMessage,
    assistantMessage: ConversationMessage
  ): Promise<void> {
    try {
      await sessionSyncService.syncMessage(sessionId, userMessage)
    } catch {
      useCognitiveHubStore.getState().addToPendingQueue(sessionId, userMessage)
      frontendLoggingService.warning('StreamingService', 'User message sync failed - added to pending queue')
    }

    try {
      await sessionSyncService.syncMessage(sessionId, assistantMessage)
    } catch {
      useCognitiveHubStore.getState().addToPendingQueue(sessionId, assistantMessage)
      frontendLoggingService.warning('StreamingService', 'Assistant message sync failed - added to pending queue')
    }
  }

  /**
   * Handle stream error
   */
  private async handleError(err: unknown, callbacks: StreamingCallbacks): Promise<void> {
    frontendLoggingService.error('StreamingService', 'Stream error', err)

    // Check if aborted
    if (err instanceof Error && err.name === 'AbortError') {
      // User-initiated abort - don't show error
      return
    }

    this.error = 'Failed to send message: ' + (err instanceof Error ? err.message : 'Unknown error')
    this.isStreaming = false
    this.streamController = null
    this.streamingMessage = null

    callbacks.onStreamError?.(err instanceof Error ? err : new Error('Unknown error'))
  }

  /**
   * Show truncation notification
   */
  private showTruncationNotification(): void {
    import('@/stores/notificationStore').then(({ useNotificationStore }) => {
      useNotificationStore.getState().addNotification({
        type: 'warning',
        title: 'Response Truncated',
        // State what happened. The old copy promised "You can continue
        // the response." — there is no continue affordance in the UI,
        // and a promise the app cannot keep is worse than the fact.
        message: 'The response was cut off at the max token limit.',
        duration: 5000
      })
    }).catch(err => {
      frontendLoggingService.error('StreamingService', 'Failed to show truncation notification', err)
    })
  }
}
