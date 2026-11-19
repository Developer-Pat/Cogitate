/**
 * Hook for managing chat message streaming
 *
 * Thin wrapper around StreamingService for React integration.
 * Handles callback wiring and state subscription.
 */

import { useState, useCallback, useRef, useEffect } from 'react'
import { StreamingService, type StreamingCallbacks, type CognitiveEvent, type CognitiveState } from '../services/domain/StreamingService'

import type { Agent, ConversationSession, ConversationMessage } from '../types/agentInteraction'

interface UseChatStreamingOptions {
  agent: Agent | null
  session: ConversationSession | null
  onMessageComplete?: (message: ConversationMessage) => void
  onStreamStart?: () => void
  onStreamError?: (error: Error) => void
  onAddMessage?: (message: ConversationMessage, sessionId: string) => void
  onUpdateMessage?: (messageId: string, content: string, metadata?: unknown, sessionId?: string) => void
  /** Called when a cognitive SSE event is received */
  onCognitiveEvent?: (event: CognitiveEvent) => void
}

interface UseChatStreamingReturn {
  isStreaming: boolean
  streamingMessage: ConversationMessage | null
  error: string | null
  startStream: (content: string, overrideModel?: string, attachmentIds?: number[]) => Promise<void>
  stopStream: () => void
  sendMessage: (content: string, overrideModel?: string, attachmentIds?: number[]) => Promise<void>
  /** Current cognitive pipeline state */
  cognitiveState: CognitiveState
  /** Get a fresh snapshot of cognitive state from the service */
  getCognitiveState: () => CognitiveState
}

/**
 * Are two cognitive snapshots equivalent as far as a RENDER is concerned?
 *
 * `StreamingService.getCognitiveState()` builds a fresh object AND a fresh
 * `events` array on every call, so reference equality is never true — which is
 * precisely why the poll below used to re-render on every tick, changed or not.
 *
 * Compare the fields a render consumes, and compare the events BY REFERENCE: the
 * service copies the array but not the objects inside it, so the same event at
 * the same position means nothing changed.
 */
function cognitiveStateEqual(a: CognitiveState, b: CognitiveState): boolean {
  if (a === b) return true
  if (a.isActive !== b.isActive) return false
  if (a.executorStage !== b.executorStage) return false
  if (a.latestTrace !== b.latestTrace) return false
  if (a.events.length !== b.events.length) return false
  for (let i = 0; i < a.events.length; i++) {
    if (a.events[i] !== b.events[i]) return false
  }
  return true
}

export function useChatStreaming({
  agent,
  session,
  onMessageComplete,
  onStreamStart,
  onStreamError,
  onAddMessage,
  onUpdateMessage,
  onCognitiveEvent
}: UseChatStreamingOptions): UseChatStreamingReturn {
  // State from service
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingMessage, setStreamingMessage] = useState<ConversationMessage | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Cognitive state (synced from service)
  const [cognitiveState, setCognitiveState] = useState<CognitiveState>({
    events: [],
    latestTrace: null,
    isActive: false,
    executorStage: 'idle',
  })

  // Service instance (singleton per hook)
  const streamingServiceRef = useRef<StreamingService | null>(null)
  if (!streamingServiceRef.current) {
    streamingServiceRef.current = new StreamingService()
  }

  // Refs for callbacks
  const callbacksRef = useRef<StreamingCallbacks>({})
  callbacksRef.current = {
    onStreamStart: () => {
      setIsStreaming(true)
      setError(null)
      // Reset cognitive state on new stream
      setCognitiveState({
        events: [],
        latestTrace: null,
        isActive: false,
        executorStage: 'idle',
      })
      onStreamStart?.()
    },
    onStreamComplete: (message) => {
      setIsStreaming(false)
      setStreamingMessage(message)
      onMessageComplete?.(message)
    },
    onStreamError: (err) => {
      setIsStreaming(false)
      setError(err.message)
      onStreamError?.(err)
    },
    onAddMessage: (message, sessionId) => {
      setStreamingMessage(message)
      onAddMessage?.(message, sessionId)
    },
    onUpdateMessage: (messageId, content, metadata, sessionId) => {
      setStreamingMessage(prev => {
        if (!prev || prev.id !== messageId) return prev
        return { ...prev, content, ...(metadata ? { metadata } : {}) }
      })
      onUpdateMessage?.(messageId, content, metadata, sessionId)
    },
    onCognitiveEvent: (event) => {
      // Sync cognitive state from the service
      const state = streamingServiceRef.current?.getCognitiveState()
      if (state) {
        setCognitiveState(state)
      }
      // Forward to consumer
      onCognitiveEvent?.(event)
    }
  }

  // Sync service state to React state — WRITING ONLY WHAT ACTUALLY CHANGED.
  //
  // THE MEASURED BUG THIS FIXES. `getCognitiveState()` returns a new object and a
  // new `events` array on every call, so writing it straight into setState handed
  // React a fresh reference ten times a second and React re-rendered on every
  // tick whether or not anything had changed. This hook drives the whole
  // AgentInteraction page, so that re-rendered the chat textarea's owner ten
  // times a second — and a controlled textarea cannot paint a keystroke while the
  // main thread is busy, which is why typing stalled and then caught up.
  //
  // Measured on /agent-interaction, 10s idle window: 80 long tasks / 5268ms
  // blocked / 53% duty cycle before; 0 / 0ms with this interval's callbacks
  // disabled. The profile put 42.1% of the main thread in the DEV JSX runtime and
  // only 0.4% in the app's own code — the cost was never what the code does, it
  // was that it ran ten times a second.
  //
  // Returning `prev` is what makes React bail out: an unchanged value produces an
  // identical render anyway, so skipping the write is behaviour-preserving.
  useEffect(() => {
    if (!streamingServiceRef.current) return

    const interval = setInterval(() => {
      const svc = streamingServiceRef.current!
      const state = svc.getState()
      setIsStreaming(prev => (prev === state.isStreaming ? prev : state.isStreaming))
      setStreamingMessage(prev => (prev === state.streamingMessage ? prev : state.streamingMessage))
      setError(prev => (prev === state.error ? prev : state.error))

      // Also sync cognitive state periodically. The service always hands back a
      // fresh object, so this is where the reference churn came from.
      const next = svc.getCognitiveState()
      setCognitiveState(prev => (cognitiveStateEqual(prev, next) ? prev : next))
    }, 100)

    return () => clearInterval(interval)
  }, [])

  /**
   * Get a fresh snapshot of cognitive state from the service.
   */
  const getCognitiveState = useCallback((): CognitiveState => {
    return streamingServiceRef.current?.getCognitiveState() ?? {
      events: [],
      latestTrace: null,
      isActive: false,
      executorStage: 'idle',
    }
  }, [])

  /**
   * Start streaming
   */
  const handleStartStream = useCallback(async (
    content: string,
    overrideModel?: string,
    attachmentIds?: number[]
  ): Promise<void> => {
    if (!agent || !session) {
      setError('Please select an agent and session first')
      return
    }

    const agentWithOverride = overrideModel
      ? { ...agent, model: overrideModel }
      : agent

    await streamingServiceRef.current?.startStream(content, {
      agent: agentWithOverride,
      sessionId: session.id,  // Pass ID, service gets fresh session from store
      callbacks: callbacksRef.current,
      attachmentIds: attachmentIds
    })
  }, [agent, session])

  /**
   * Stop streaming
   */
  const handleStopStream = useCallback(() => {
    streamingServiceRef.current?.stopStream()
  }, [])

  return {
    isStreaming,
    streamingMessage,
    error,
    startStream: handleStartStream,
    stopStream: handleStopStream,
    sendMessage: handleStartStream,
    cognitiveState,
    getCognitiveState,
  }
}

export default useChatStreaming
