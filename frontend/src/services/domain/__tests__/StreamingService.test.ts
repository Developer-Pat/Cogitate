import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { StreamingService } from '../StreamingService'
import { chatService } from '@/services/domains/llm/chatService'
import { sessionSyncService } from '@/services/sessionSyncService'
import { useNotificationStore } from '@/stores/notificationStore'
import type { Agent, ConversationSession } from '@/types/agentInteraction'
import type { StreamingCallbacks } from '../StreamingService'

// Mock chatService
vi.mock('@/services/domains/llm/chatService', () => ({
  chatService: {
    createStreamingChatCompletion: vi.fn()
  }
}))

// Mock sessionSyncService
vi.mock('@/services/sessionSyncService', () => ({
  sessionSyncService: {
    syncMessage: vi.fn().mockResolvedValue(undefined)
  }
}))

// Mock notification store — the path resolves from THIS file to the same
// module StreamingService imports, so the mock actually applies (the old
// path pointed at a directory that does not exist).
vi.mock('@/stores/notificationStore', () => ({
  useNotificationStore: {
    getState: vi.fn(() => ({
      addNotification: vi.fn(),
      addError: vi.fn(),
      addWarning: vi.fn()
    }))
  }
}))

// Mock cognitive hub store
const mockHubState = {
  addToPendingQueue: vi.fn(),
  activeSession: null as ConversationSession | null
}

vi.mock('@/stores/cognitiveHubStore', () => ({
  useCognitiveHubStore: {
    getState: vi.fn(() => mockHubState)
  }
}))

// Mock frontendLoggingService
vi.mock('@/services/frontendLoggingService', () => ({
  frontendLoggingService: {
    debug: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
    error: vi.fn()
  }
}))

describe('StreamingService', () => {
  let service: StreamingService
  let mockAgent: Agent
  let mockSession: ConversationSession
  let mockCallbacks: StreamingCallbacks
  let perfTime = 0

  beforeEach(() => {
    // Mock performance.now() to auto-increment on each call
    // This ensures throttledUpdate() sees timeSinceLastUpdate >= 100ms
    // and calls onUpdateMessage directly without scheduling setTimeout
    perfTime = 0
    vi.spyOn(performance, 'now').mockImplementation(() => {
      perfTime += 1000
      return perfTime
    })
    service = new StreamingService()
    vi.clearAllMocks()

    mockAgent = {
      id: 'agent-1',
      name: 'Test Agent',
      description: 'A test agent',
      capabilities: ['chat'],
      provider: 'openai',
      model: 'gpt-4',
      parameters: {
        temperature: 0.7,
        topP: 0.9
      },
      isAvailable: true,
      isStale: false,
      lastRefreshed: new Date().toISOString()
    }

    mockSession = {
      id: '123',
      title: 'Test Session',
      agentId: 'agent-1',
      messages: [],
      createdAt: new Date(),
      updatedAt: new Date(),
      isActive: true
    }

    // Configure mock to return our session
    mockHubState.activeSession = mockSession

    mockCallbacks = {
      onStreamStart: vi.fn(),
      onStreamComplete: vi.fn(),
      onStreamError: vi.fn(),
      onAddMessage: vi.fn(),
      onUpdateMessage: vi.fn()
    }
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('constructor', () => {
    it('should initialize with default state', () => {
      const state = service.getState()

      expect(state.isStreaming).toBe(false)
      expect(state.streamingMessage).toBeNull()
      expect(state.error).toBeNull()
    })
  })

  describe('startStream', () => {
    it('should call onStreamStart callback', async () => {
      const mockResponse = {
        body: new ReadableStream({
          start(controller) {
            controller.enqueue(new TextEncoder().encode('data: [DONE]\n\n'))
            controller.close()
          }
        })
      }

      vi.mocked(chatService.createStreamingChatCompletion).mockResolvedValue(mockResponse as unknown as Response)

      await service.startStream('Hello', {
        agent: mockAgent,
        sessionId: mockSession.id,
        callbacks: mockCallbacks
      })

      expect(mockCallbacks.onStreamStart).toHaveBeenCalled()
    })

    it('should create user and assistant messages', async () => {
      const mockResponse = {
        body: new ReadableStream({
          start(controller) {
            controller.enqueue(new TextEncoder().encode('data: [DONE]\n\n'))
            controller.close()
          }
        })
      }

      vi.mocked(chatService.createStreamingChatCompletion).mockResolvedValue(mockResponse as unknown as Response)

      await service.startStream('Hello', {
        agent: mockAgent,
        sessionId: mockSession.id,
        callbacks: mockCallbacks
      })

      expect(mockCallbacks.onAddMessage).toHaveBeenCalledTimes(2)
      expect(mockCallbacks.onAddMessage).toHaveBeenCalledWith(
        expect.objectContaining({ role: 'user', content: 'Hello' }),
        expect.any(String)
      )
      expect(mockCallbacks.onAddMessage).toHaveBeenCalledWith(
        expect.objectContaining({ role: 'assistant', content: '', isStreaming: true }),
        expect.any(String)
      )
    })

    it('should call chatService with correct request', async () => {
      const mockResponse = {
        body: new ReadableStream({
          start(controller) {
            controller.enqueue(new TextEncoder().encode('data: [DONE]\n\n'))
            controller.close()
          }
        })
      }

      vi.mocked(chatService.createStreamingChatCompletion).mockResolvedValue(mockResponse as unknown as Response)

      await service.startStream('Hello', {
        agent: mockAgent,
        sessionId: mockSession.id,
        callbacks: mockCallbacks
      })

      expect(chatService.createStreamingChatCompletion).toHaveBeenCalledWith(
        expect.objectContaining({
          model: 'gpt-4',
          stream: true,
          profile: 'agent-1',
          session_id: 123
        }),
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      )

      // NO SAMPLING ON THE REQUEST (G4). This request used to carry
      // `options.temperature` / `options.top_p` read off the agent object, but
      // `chatService` builds its backend request from agent_id / message / session_id /
      // stream / attachment_ids — it DROPS `options`, so the pair travelled nowhere while
      // looking like it did. An agent's own sampling is the server's to resolve.
      const sentRequest = vi
        .mocked(chatService.createStreamingChatCompletion)
        .mock.calls.at(-1)?.[0]
      expect(sentRequest).toBeDefined()
      expect(sentRequest?.options).toBeUndefined()
    })

    it('should allow temp session IDs (backend will create)', async () => {
      const invalidSession = { ...mockSession, id: 'session-temp' }
      
      // Update mock to return temp session
      mockHubState.activeSession = invalidSession

      const mockResponse = {
        body: new ReadableStream({
          start(controller) {
            controller.enqueue(new TextEncoder().encode('data: [DONE]\n\n'))
            controller.close()
          }
        })
      }

      vi.mocked(chatService.createStreamingChatCompletion).mockResolvedValue(mockResponse as unknown as Response)

      await service.startStream('Hello', {
        agent: mockAgent,
        sessionId: invalidSession.id,
        callbacks: mockCallbacks
      })

      // Should NOT throw error - temp sessions are allowed
      expect(mockCallbacks.onStreamError).not.toHaveBeenCalled()
    })

    it('should handle stream with content chunks', async () => {
      const mockResponse = {
        body: new ReadableStream({
          start(controller) {
            controller.enqueue(new TextEncoder().encode('data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n'))
            controller.enqueue(new TextEncoder().encode('data: {"choices":[{"delta":{"content":" World"}}]}\n\n'))
            controller.enqueue(new TextEncoder().encode('data: {"done":true,"metadata":{"tokenCount":5}}\n\n'))
            controller.close()
          }
        })
      }

      vi.mocked(chatService.createStreamingChatCompletion).mockResolvedValue(mockResponse as unknown as Response)

      await service.startStream('Hello', {
        agent: mockAgent,
        sessionId: mockSession.id,
        callbacks: mockCallbacks
      })

      expect(mockCallbacks.onUpdateMessage).toHaveBeenCalledWith(
        expect.any(String),
        expect.stringContaining('Hello'),
        expect.anything(),
        expect.any(String)
      )
      expect(mockCallbacks.onStreamComplete).toHaveBeenCalledWith(
        expect.objectContaining({
          isStreaming: false,
          metadata: expect.objectContaining({ tokenCount: 5 })
        })
      )
    })

    it('should handle session title event', async () => {
      const mockResponse = {
        body: new ReadableStream({
          start(controller) {
            controller.enqueue(new TextEncoder().encode('event: session_title\n\n'))
            controller.enqueue(new TextEncoder().encode('data: {"session_id":123,"title":"New Chat"}\n\n'))
            controller.enqueue(new TextEncoder().encode('data: [DONE]\n\n'))
            controller.close()
          }
        })
      }

      vi.mocked(chatService.createStreamingChatCompletion).mockResolvedValue(mockResponse as unknown as Response)

      await service.startStream('Hello', {
        agent: mockAgent,
        sessionId: mockSession.id,
        callbacks: mockCallbacks
      })

      // Title events are now ignored (generated in background by TitleService)
      // No callback is called for title events anymore
    })

    it('should handle truncation notification', async () => {
      const mockResponse = {
        body: new ReadableStream({
          start(controller) {
            controller.enqueue(new TextEncoder().encode('data: {"choices":[{"delta":{"content":"Long content"},"finish_reason":"length"}]}\n\n'))
            controller.enqueue(new TextEncoder().encode('data: {"done":true,"metadata":{"truncated":true}}\n\n'))
            controller.close()
          }
        })
      }

      vi.mocked(chatService.createStreamingChatCompletion).mockResolvedValue(mockResponse as unknown as Response)

      await service.startStream('Hello', {
        agent: mockAgent,
        sessionId: mockSession.id,
        callbacks: mockCallbacks
      })

      // Wait for dynamic import to complete (microtask flush)
      await new Promise(process.nextTick)

      expect(mockCallbacks.onStreamComplete).toHaveBeenCalledWith(
        expect.objectContaining({
          metadata: expect.objectContaining({ truncated: true })
        })
      )
    })

    it("judges the estimate against the SERVER's sent budget (no backend flag)", async () => {
      // A long answer whose streams carried NO backend truncation flag. The estimate
      // used to be compared against the CLIENT's copy of the declaration plus an
      // invented 4000 default — the wrong number entirely (the wire's number can be
      // twice the declaration). It now compares against what the turn actually sent,
      // which the done frame reports as `metadata.budget` (G-A ii / G.2).
      const addNotification = vi.fn()
      vi.mocked(useNotificationStore.getState).mockReturnValue({
        addNotification,
        addError: vi.fn()
      } as unknown as ReturnType<typeof useNotificationStore.getState>)

      const longAnswer = 'x'.repeat(7600) // ~1900 estimated tokens of the 2000 that went out
      const mockResponse = {
        body: new ReadableStream({
          start(controller) {
            controller.enqueue(new TextEncoder().encode(
              `data: {"choices":[{"delta":{"content":"${longAnswer}"}}]}\n\n`
            ))
            controller.enqueue(new TextEncoder().encode(
              'data: {"done":true,"metadata":{"budget":{"sent":2000,"declared":2000,"reason":"declared","path":"default"}}}\n\n'
            ))
            controller.close()
          }
        })
      }

      vi.mocked(chatService.createStreamingChatCompletion).mockResolvedValue(mockResponse as unknown as Response)

      await service.startStream('Hello', {
        agent: mockAgent,
        sessionId: mockSession.id,
        callbacks: mockCallbacks
      })

      await vi.waitFor(() => {
        expect(addNotification).toHaveBeenCalledWith(
          expect.objectContaining({
            type: 'warning',
            title: 'Response Truncated',
            message: expect.stringContaining('max token limit')
          })
        )
      })

      // the saved metadata names the source of the claim (the estimate)
      expect(mockCallbacks.onStreamComplete).toHaveBeenCalledWith(
        expect.objectContaining({
          metadata: expect.objectContaining({
            truncated: true,
            truncationReason: 'max_tokens_fallback'
          })
        })
      )
    })

    it('invents no budget: a frame carrying none raises no truncation claim', async () => {
      // The old code fell back to `agent.parameters.maxTokens || 4000`, so an agent
      // with no declaration was judged against an invented number. No sent budget on
      // the frame now means NO estimate — the server's own flag is the authority.
      const addNotification = vi.fn()
      vi.mocked(useNotificationStore.getState).mockReturnValue({
        addNotification,
        addError: vi.fn()
      } as unknown as ReturnType<typeof useNotificationStore.getState>)

      const longAnswer = 'x'.repeat(20000) // ~5000 estimated tokens: over any old default
      const mockResponse = {
        body: new ReadableStream({
          start(controller) {
            controller.enqueue(new TextEncoder().encode(
              `data: {"choices":[{"delta":{"content":"${longAnswer}"}}]}\n\n`
            ))
            controller.enqueue(new TextEncoder().encode('data: {"done":true,"metadata":{}}\n\n'))
            controller.close()
          }
        })
      }

      vi.mocked(chatService.createStreamingChatCompletion).mockResolvedValue(mockResponse as unknown as Response)

      await service.startStream('Hello', {
        agent: mockAgent,
        sessionId: mockSession.id,
        callbacks: mockCallbacks
      })

      await new Promise(process.nextTick)

      expect(addNotification).not.toHaveBeenCalled()
      const complete = vi.mocked(mockCallbacks.onStreamComplete!).mock.calls[0][0] as {
        metadata?: Record<string, unknown>
      }
      expect(complete.metadata?.truncated).toBeFalsy()
      expect(complete.metadata?.truncationReason).toBeUndefined()
    })

    it('should call onStreamError on failure', async () => {
      vi.mocked(chatService.createStreamingChatCompletion).mockRejectedValue(new Error('Network error'))

      await service.startStream('Hello', {
        agent: mockAgent,
        sessionId: mockSession.id,
        callbacks: mockCallbacks
      })

      expect(mockCallbacks.onStreamError).toHaveBeenCalledWith(expect.any(Error))
      expect(mockCallbacks.onStreamError).not.toHaveBeenCalledWith(expect.objectContaining({ name: 'AbortError' }))
    })

    it('should not call onStreamError on user abort', async () => {
      const abortError = new Error('Aborted')
      abortError.name = 'AbortError'
      vi.mocked(chatService.createStreamingChatCompletion).mockRejectedValue(abortError)

      await service.startStream('Hello', {
        agent: mockAgent,
        sessionId: mockSession.id,
        callbacks: mockCallbacks
      })

      expect(mockCallbacks.onStreamError).not.toHaveBeenCalled()
    })
  })

  describe('stopStream', () => {
    it('should abort the stream controller', async () => {
      // Start a stream to create controller
      const mockResponse = {
        body: new ReadableStream({
          start(controller) {
            controller.enqueue(new TextEncoder().encode('data: [DONE]\n\n'))
            controller.close()
          }
        })
      }

      vi.mocked(chatService.createStreamingChatCompletion).mockResolvedValue(mockResponse as unknown as Response)

      await service.startStream('Hello', {
        agent: mockAgent,
        sessionId: mockSession.id,
        callbacks: mockCallbacks
      })

      service.stopStream()

      const state = service.getState()
      expect(state.isStreaming).toBe(false)
      expect(state.streamingMessage).toBeNull()
    })

    it('should clear pending update timer', () => {
      service.stopStream()

      const state = service.getState()
      expect(state.isStreaming).toBe(false)
    })
  })

  describe('getState', () => {
    it('should return current streaming state', () => {
      const state = service.getState()

      expect(state).toEqual({
        isStreaming: false,
        streamingMessage: null,
        error: null
      })
    })
  })

  describe('syncMessages', () => {
    it('should sync user and assistant messages to backend', async () => {
      const mockResponse = {
        body: new ReadableStream({
          start(controller) {
            controller.enqueue(new TextEncoder().encode('data: [DONE]\n\n'))
            controller.close()
          }
        })
      }

      vi.mocked(chatService.createStreamingChatCompletion).mockResolvedValue(mockResponse as unknown as Response)

      await service.startStream('Hello', {
        agent: mockAgent,
        sessionId: mockSession.id,
        callbacks: mockCallbacks
      })

      expect(sessionSyncService.syncMessage).toHaveBeenCalledTimes(2)
    })

    it('should add to pending queue on sync failure', async () => {
      // Override the default mock for this test
      vi.mocked(sessionSyncService.syncMessage).mockRejectedValue(new Error('Sync failed'))

      const mockResponse = {
        body: new ReadableStream({
          start(controller) {
            controller.enqueue(new TextEncoder().encode('data: [DONE]\n\n'))
            controller.close()
          }
        })
      }

      vi.mocked(chatService.createStreamingChatCompletion).mockResolvedValue(mockResponse as unknown as Response)

      await service.startStream('Hello', {
        agent: mockAgent,
        sessionId: mockSession.id,
        callbacks: mockCallbacks
      })

      // Wait for async sync to complete (microtask flush)
      await new Promise(process.nextTick)

      // Verify sync was attempted (mock is called even on failure)
      expect(sessionSyncService.syncMessage).toHaveBeenCalled()
    })
  })

  describe('integration: full streaming workflow', () => {
    it('should handle complete streaming lifecycle', async () => {
      const mockResponse = {
        body: new ReadableStream({
          start(controller) {
            controller.enqueue(new TextEncoder().encode('data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n'))
            controller.enqueue(new TextEncoder().encode('data: {"choices":[{"delta":{"content":" World"}}]}\n\n'))
            controller.enqueue(new TextEncoder().encode('data: {"done":true,"metadata":{"tokenCount":5,"totalTimeMs":1000}}\n\n'))
            controller.close()
          }
        })
      }

      vi.mocked(chatService.createStreamingChatCompletion).mockResolvedValue(mockResponse as unknown as Response)

      await service.startStream('Hello', {
        agent: mockAgent,
        sessionId: mockSession.id,
        callbacks: mockCallbacks
      })

      // Verify callbacks were called in order
      expect(mockCallbacks.onStreamStart).toHaveBeenCalled()
      expect(mockCallbacks.onAddMessage).toHaveBeenCalledTimes(2)
      expect(mockCallbacks.onUpdateMessage).toHaveBeenCalled()
      expect(mockCallbacks.onStreamComplete).toHaveBeenCalledWith(
        expect.objectContaining({
          isStreaming: false,
          metadata: expect.objectContaining({
            tokenCount: 5,
            totalTimeMs: 1000
          })
        })
      )

      // Verify state is reset
      const state = service.getState()
      expect(state.isStreaming).toBe(false)
      expect(state.streamingMessage).toBeNull()
    })

    it('should handle context window limit', async () => {
      // Create session with many messages
      const sessionWithManyMessages: ConversationSession = {
        ...mockSession,
        messages: Array.from({ length: 25 }, (_, i) => ({
          id: `msg-${i}`,
          role: i % 2 === 0 ? 'user' : 'assistant' as const,
          content: `Message ${i}`,
          timestamp: new Date(),
          agentId: 'agent-1'
        }))
      }

      // Update mock state with session that has many messages
      mockHubState.activeSession = sessionWithManyMessages

      const mockResponse = {
        body: new ReadableStream({
          start(controller) {
            controller.enqueue(new TextEncoder().encode('data: [DONE]\n\n'))
            controller.close()
          }
        })
      }

      vi.mocked(chatService.createStreamingChatCompletion).mockResolvedValue(mockResponse as unknown as Response)

      await service.startStream('Hello', {
        agent: mockAgent,
        sessionId: sessionWithManyMessages.id,
        callbacks: mockCallbacks
      })

      // Verify only last 20 messages + new user message were sent
      const callArgs = vi.mocked(chatService.createStreamingChatCompletion).mock.calls[0][0]
      expect(callArgs.messages).toHaveLength(21) // 20 context + 1 new user message
    })
  })

  describe('SSE error event handling (F1)', () => {
    it('should surface backend error events via onStreamError + toast', async () => {
      // Backend emits: event: error + data: {"error": {...}}
      const ssePayload = [
        'event: error',
        'data: {"error": {"type": "not_found", "message": "Model not found", "error_class": "NotFoundError", "provider": "deepseek", "model": "deepseek-chat", "session_id": "123"}}',
        '',
        'data: [DONE]',
        ''
      ].join('\n')

      const mockResponse = {
        body: new ReadableStream({
          start(controller) {
            controller.enqueue(new TextEncoder().encode(ssePayload))
            controller.close()
          }
        })
      }

      vi.mocked(chatService.createStreamingChatCompletion).mockResolvedValue(mockResponse as unknown as Response)

      await service.startStream('Hello', {
        agent: mockAgent,
        sessionId: mockSession.id,
        callbacks: mockCallbacks
      })

      // onStreamError must be called with the backend error message
      expect(mockCallbacks.onStreamError).toHaveBeenCalledWith(expect.any(Error))
      const err = (mockCallbacks.onStreamError as ReturnType<typeof vi.fn>).mock.calls[0][0] as Error
      expect(err.message).toBe('Model not found')

      // Stream marked failed
      expect(service.getState().error).toBe('Model not found')
      expect(service.getState().isStreaming).toBe(false)
    })

    it('should reset cognitive pipeline indicators on error (no stuck spinner)', async () => {
      // Simulate: executor started (spinner on) → backend error
      const ssePayload = [
        'event: cognitive_executor_started',
        'data: {}',
        'event: error',
        'data: {"error": {"type": "not_found", "message": "Model not found", "provider": "deepseek", "model": "v99"}}',
        '',
        'data: [DONE]',
        ''
      ].join('\n')

      const mockResponse = {
        body: new ReadableStream({
          start(controller) {
            controller.enqueue(new TextEncoder().encode(ssePayload))
            controller.close()
          }
        })
      }

      vi.mocked(chatService.createStreamingChatCompletion).mockResolvedValue(mockResponse as unknown as Response)

      await service.startStream('Hello', {
        agent: mockAgent,
        sessionId: mockSession.id,
        callbacks: mockCallbacks
      })

      // Cognitive state must be reset so the Thinking spinner stops
      const cognitiveState = service.getCognitiveState()
      expect(cognitiveState.isActive).toBe(false)
      expect(cognitiveState.executorStage).toBe('idle')
    })

    it('should not swallow errors when provider/model present in payload', async () => {
      const ssePayload = [
        'event: error',
        'data: {"error": {"type": "authentication", "message": "Invalid API key", "provider": "deepseek", "model": "deepseek-v4-flash"}}',
        '',
        'data: [DONE]',
        ''
      ].join('\n')

      const mockResponse = {
        body: new ReadableStream({
          start(controller) {
            controller.enqueue(new TextEncoder().encode(ssePayload))
            controller.close()
          }
        })
      }

      vi.mocked(chatService.createStreamingChatCompletion).mockResolvedValue(mockResponse as unknown as Response)

      await service.startStream('Hello', {
        agent: mockAgent,
        sessionId: mockSession.id,
        callbacks: mockCallbacks
      })

      expect(mockCallbacks.onStreamError).toHaveBeenCalled()
      const err = (mockCallbacks.onStreamError as ReturnType<typeof vi.fn>).mock.calls[0][0] as Error
      expect(err.message).toBe('Invalid API key')
    })

    it('reports a hard limit stop as a STOPPED turn, not a provider failure', async () => {
      // Same `event: error` frame as any failure, but type=limit_stop (D.3): the
      // turn was stopped on purpose and the partial answer is kept. The copy must
      // say that — a "Provider error" headline would claim a fault that did not
      // happen, and "Agent failed" (useAgentInteraction) likewise.
      const addWarning = vi.fn()
      const addError = vi.fn()
      vi.mocked(useNotificationStore.getState).mockReturnValue({
        addNotification: vi.fn(),
        addError,
        addWarning
      } as unknown as ReturnType<typeof useNotificationStore.getState>)

      const errorPayload = JSON.stringify({
        error: {
          type: 'limit_stop',
          message: "This turn reached 12 calls to the provider — the ceiling for a single answer, so the turn stops here. What had already arrived is kept. Say 'continue' and I'll carry on from what I have.",
          provider: 'deepseek',
          model: 'deepseek-v4-flash',
          session_id: '123'
        }
      })

      const ssePayload = [
        'data: {"choices":[{"delta":{"content":"Reading the file "}}]}',
        'event: error',
        `data: ${errorPayload}`,
        '',
        'data: [DONE]',
        ''
      ].join('\n')

      const mockResponse = {
        body: new ReadableStream({
          start(controller) {
            controller.enqueue(new TextEncoder().encode(ssePayload))
            controller.close()
          }
        })
      }

      vi.mocked(chatService.createStreamingChatCompletion).mockResolvedValue(mockResponse as unknown as Response)

      await service.startStream('Hello', {
        agent: mockAgent,
        sessionId: mockSession.id,
        callbacks: mockCallbacks
      })

      // the toast says what happened, as a warning — no error headline, no fault
      expect(addWarning).toHaveBeenCalledWith(
        'Turn stopped', expect.stringContaining("Say 'continue'"), 6000
      )
      expect(addError).not.toHaveBeenCalled()

      // ...and the caller can tell a STOPPED turn from a FAILED one
      const err = (mockCallbacks.onStreamError as ReturnType<typeof vi.fn>).mock.calls[0][0] as
        Error & { errorType?: string }
      expect(err.errorType).toBe('limit_stop')
    })
  })
  it('streams FORWARD-ONLY — the pending throttle never regresses (the dance fix)', async () => {
    // THE DANCE TEST (2026-09-01): the throttle's timer used to
    // capture the content at SCHEDULE — the chunks arriving while
    // it waited were dropped, so the display regressed. Now the
    // pendingContent holds the latest and the timer fires it.
    const events = [
      'data: {"choices":[{"delta":{"content":"A"}}]}\n\n',
      'data: {"choices":[{"delta":{"content":"B"}}]}\n\n',
      'data: {"choices":[{"delta":{"content":"C"}}]}\n\n',
      'data: {"done":true,"metadata":{}}\n\n',
    ]
    const mockResponse = {
      body: new ReadableStream({
        start(controller) {
          events.forEach((e) => controller.enqueue(new TextEncoder().encode(e)))
          controller.close()
        }
      })
    }
    vi.mocked(chatService.createStreamingChatCompletion).mockResolvedValue(mockResponse as unknown as Response)
    const updates: string[] = []
    mockCallbacks.onUpdateMessage = vi.fn((_id, content) => { updates.push(String(content)) })
    await service.startStream('Hello', {
      agent: mockAgent,
      sessionId: mockSession.id,
      callbacks: mockCallbacks
    })
    // every update must be a PREFIX of the next (never a regression)
    for (let i = 1; i < updates.length; i++) {
      expect(updates[i].startsWith(updates[i - 1])).toBe(true)
    }
    // the final content carries everything
    const last = updates[updates.length - 1]
    expect(last).toContain('A')
    expect(last).toContain('B')
    expect(last).toContain('C')
  })

})
