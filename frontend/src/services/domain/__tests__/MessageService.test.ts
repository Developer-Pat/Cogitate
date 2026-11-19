import { describe, it, expect, beforeEach, vi } from 'vitest'
import { MessageService } from '../MessageService'
import { sessionSyncService } from '@/services/sessionSyncService'
import type { ConversationSession, ConversationMessage } from '@/types/agentInteraction'

// Mock sessionSyncService
vi.mock('@/services/sessionSyncService', () => ({
  sessionSyncService: {
    deleteMessage: vi.fn()
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

describe('MessageService', () => {
  let service: MessageService
  let mockSession: ConversationSession

  beforeEach(() => {
    service = new MessageService()
    vi.clearAllMocks()

    mockSession = {
      id: 'session-1',
      title: 'Test Session',
      agentId: 'agent-1',
      messages: [
        {
          id: 'msg-1',
          role: 'user',
          content: 'Hello',
          timestamp: new Date('2026-03-05T10:00:00Z'),
          agentId: 'agent-1'
        },
        {
          id: 'msg-2',
          role: 'assistant',
          content: 'Hi there!',
          timestamp: new Date('2026-03-05T10:00:01Z'),
          agentId: 'agent-1'
        }
      ],
      createdAt: new Date('2026-03-05T10:00:00Z'),
      updatedAt: new Date('2026-03-05T10:00:01Z'),
      isActive: true
    }
  })

  describe('addMessageToSession', () => {
    it('should add a message to session messages', () => {
      const newMessage: ConversationMessage = {
        id: 'msg-3',
        role: 'user',
        content: 'New message',
        timestamp: new Date(),
        agentId: 'agent-1'
      }

      const updated = service.addMessageToSession(mockSession, newMessage)

      expect(updated.messages!).toHaveLength(3)
      expect(updated.messages![2]).toEqual(newMessage)
      expect(updated.updatedAt.getTime()).toBeGreaterThan(mockSession.updatedAt.getTime())
    })

    it('should handle session with no existing messages', () => {
      const emptySession: ConversationSession = {
        ...mockSession,
        messages: []
      }

      const newMessage: ConversationMessage = {
        id: 'msg-3',
        role: 'user',
        content: 'First message',
        timestamp: new Date(),
        agentId: 'agent-1'
      }

      const updated = service.addMessageToSession(emptySession, newMessage)

      expect(updated.messages!).toHaveLength(1)
      expect(updated.messages![0]).toEqual(newMessage)
    })

    it('should preserve existing messages', () => {
      const newMessage: ConversationMessage = {
        id: 'msg-3',
        role: 'assistant',
        content: 'Response',
        timestamp: new Date(),
        agentId: 'agent-1'
      }

      const updated = service.addMessageToSession(mockSession, newMessage)

      expect(updated.messages![0]).toEqual(mockSession.messages![0])
      expect(updated.messages![1]).toEqual(mockSession.messages![1])
      expect(updated.messages![2]).toEqual(newMessage)
    })
  })

  describe('updateMessageInSession', () => {
    it('should update message content', () => {
      const updated = service.updateMessageInSession(mockSession, 'msg-1', 'Updated content')

      expect(updated).not.toBeNull()
      expect(updated?.messages![0].content).toBe('Updated content')
      expect(updated?.messages![1].content).toBe('Hi there!')
      expect(updated?.updatedAt.getTime()).toBeGreaterThan(mockSession.updatedAt.getTime())
    })

    it('should update message metadata', () => {
      const metadata = { tokenCount: 100, totalTimeMs: 2000 }
      const updated = service.updateMessageInSession(mockSession, 'msg-1', 'Hello', metadata)

      expect(updated).not.toBeNull()
      expect(updated?.messages![0].content).toBe('Hello')
      expect(updated?.messages![0].metadata).toEqual(metadata)
    })

    it('should return null if message not found', () => {
      const updated = service.updateMessageInSession(mockSession, 'non-existent', 'Content')

      expect(updated).toBeNull()
    })

    it('should update streaming message with final content', () => {
      const streamingMessage: ConversationMessage = {
        id: 'msg-streaming',
        role: 'assistant',
        content: 'Partial',
        timestamp: new Date(),
        agentId: 'agent-1',
        isStreaming: true
      }

      const sessionWithStreaming: ConversationSession = {
        ...mockSession,
        messages: [...(mockSession.messages ?? []), streamingMessage]
      }

      const metadata = { tokenCount: 50, totalTimeMs: 1000, tokensPerSecond: 50 }
      const updated = service.updateMessageInSession(
        sessionWithStreaming,
        'msg-streaming',
        'Final content',
        metadata
      )

      expect(updated).not.toBeNull()
      expect(updated?.messages![2].content).toBe('Final content')
      expect(updated?.messages![2].metadata).toEqual(metadata)
      expect(updated?.messages![2].isStreaming).toBe(true) // isStreaming not changed by update
    })
  })

  describe('removeMessageFromSession', () => {
    it('should remove a message from session', () => {
      const updated = service.removeMessageFromSession(mockSession, 'msg-1')

      expect(updated).not.toBeNull()
      expect(updated?.messages).toHaveLength(1)
      expect(updated?.messages?.[0]?.id).toBe('msg-2')
    })

    it('should return null if message not found', () => {
      const updated = service.removeMessageFromSession(mockSession, 'non-existent')

      expect(updated).toBeNull()
    })

    it('should update timestamp after removal', () => {
      const updated = service.removeMessageFromSession(mockSession, 'msg-1')

      expect(updated?.updatedAt.getTime()).toBeGreaterThan(mockSession.updatedAt.getTime())
    })

    it('should handle removing last message', () => {
      const sessionWithOneMessage: ConversationSession = {
        ...mockSession,
        messages: [(mockSession.messages ?? [])[0]]
      }

      const updated = service.removeMessageFromSession(sessionWithOneMessage, 'msg-1')

      expect(updated).not.toBeNull()
      expect(updated?.messages).toHaveLength(0)
    })
  })

  describe('deleteMessage', () => {
    it('should delete message from backend', async () => {
      vi.mocked(sessionSyncService.deleteMessage).mockResolvedValue()

      await service.deleteMessage('session-1', 'msg-1')

      expect(sessionSyncService.deleteMessage).toHaveBeenCalledWith('session-1', 'msg-1')
    })

    it('should throw error if backend deletion fails', async () => {
      vi.mocked(sessionSyncService.deleteMessage).mockRejectedValue(new Error('Network error'))

      await expect(service.deleteMessage('session-1', 'msg-1')).rejects.toThrow(
        'Failed to delete message: Network error'
      )
    })
  })

  describe('createUserMessage', () => {
    it('should create a user message with correct structure', () => {
      const message = service.createUserMessage('Hello', 'agent-1')

      expect(message.role).toBe('user')
      expect(message.content).toBe('Hello')
      expect(message.agentId).toBe('agent-1')
      expect(message.id).toMatch(/msg-\d+-user/)
      expect(message.timestamp).toBeInstanceOf(Date)
    })

    it('should generate unique IDs for different messages', async () => {
      // Add small delay to ensure different timestamps
      const message1 = service.createUserMessage('First', 'agent-1')
      await new Promise(resolve => setTimeout(resolve, 10))
      const message2 = service.createUserMessage('Second', 'agent-1')

      expect(message1.id).not.toBe(message2.id)
    })
  })

  describe('createAssistantMessage', () => {
    it('should create an assistant message placeholder', () => {
      const message = service.createAssistantMessage('agent-1')

      expect(message.role).toBe('assistant')
      expect(message.content).toBe('')
      expect(message.agentId).toBe('agent-1')
      expect(message.isStreaming).toBe(true)
      expect(message.id).toMatch(/msg-\d+-assistant/)
    })

    it('should allow creating non-streaming message', () => {
      const message = service.createAssistantMessage('agent-1', false)

      expect(message.isStreaming).toBe(false)
    })
  })

  describe('finalizeStreamingMessage', () => {
    it('should finalize a streaming message with content and metadata', () => {
      const streamingMessage: ConversationMessage = {
        id: 'msg-streaming',
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        agentId: 'agent-1',
        isStreaming: true
      }

      const finalized = service.finalizeStreamingMessage(
        streamingMessage,
        'Hello World',
        1000,
        'gpt-4',
        'openai'
      )

      expect(finalized.content).toBe('Hello World')
      expect(finalized.isStreaming).toBe(false)
      expect(finalized.metadata?.tokenCount).toBe(3) // 12 chars / 4
      expect(finalized.metadata?.totalTimeMs).toBe(1000)
      expect(finalized.metadata?.model).toBe('gpt-4')
      expect(finalized.metadata?.provider).toBe('openai')
    })

    it('should mark message as truncated when specified', () => {
      const streamingMessage: ConversationMessage = {
        id: 'msg-streaming',
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        agentId: 'agent-1',
        isStreaming: true
      }

      const finalized = service.finalizeStreamingMessage(
        streamingMessage,
        'Long content',
        2000,
        'gpt-4',
        'openai',
        true
      )

      expect(finalized.metadata?.truncated).toBe(true)
    })

    it('should work without optional model and provider', () => {
      const streamingMessage: ConversationMessage = {
        id: 'msg-streaming',
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        agentId: 'agent-1',
        isStreaming: true
      }

      const finalized = service.finalizeStreamingMessage(streamingMessage, 'Content', 1500)

      expect(finalized.content).toBe('Content')
      expect(finalized.isStreaming).toBe(false)
      expect(finalized.metadata?.model).toBeUndefined()
      expect(finalized.metadata?.provider).toBeUndefined()
    })
  })

  describe('formatMessagesForLLM', () => {
    it('should format messages for LLM API', () => {
      const messages: ConversationMessage[] = [
        {
          id: 'msg-1',
          role: 'user',
          content: 'Hello',
          timestamp: new Date(),
          agentId: 'agent-1'
        },
        {
          id: 'msg-2',
          role: 'assistant',
          content: 'Hi there!',
          timestamp: new Date(),
          agentId: 'agent-1'
        }
      ]

      const formatted = service.formatMessagesForLLM(messages)

      expect(formatted).toHaveLength(2)
      expect(formatted[0]).toEqual({ role: 'user', content: 'Hello' })
      expect(formatted[1]).toEqual({ role: 'assistant', content: 'Hi there!' })
    })

    it('should filter out streaming messages', () => {
      const messages: ConversationMessage[] = [
        {
          id: 'msg-1',
          role: 'user',
          content: 'Hello',
          timestamp: new Date(),
          agentId: 'agent-1'
        },
        {
          id: 'msg-2',
          role: 'assistant',
          content: 'Streaming...',
          timestamp: new Date(),
          agentId: 'agent-1',
          isStreaming: true
        }
      ]

      const formatted = service.formatMessagesForLLM(messages)

      expect(formatted).toHaveLength(1)
      expect(formatted[0].role).toBe('user')
    })

    it('should limit number of messages to context window', () => {
      const messages: ConversationMessage[] = Array.from({ length: 25 }, (_, i) => ({
        id: `msg-${i}`,
        role: i % 2 === 0 ? 'user' : 'assistant' as const,
        content: `Message ${i}`,
        timestamp: new Date(),
        agentId: 'agent-1'
      }))

      const formatted = service.formatMessagesForLLM(messages, 20)

      expect(formatted).toHaveLength(20)
      expect(formatted[0].content).toBe('Message 5') // Starts from 5th message (25 - 20)
      expect(formatted[19].content).toBe('Message 24')
    })
  })

  describe('exportConversation', () => {
    it('should export conversation as JSON', () => {
      const exported = service.exportConversation(mockSession, 'json')
      const parsed = JSON.parse(exported)

      expect(parsed.title).toBe('Test Session')
      expect(parsed.agentId).toBe('agent-1')
      expect(parsed.messages).toHaveLength(2)
      expect(parsed.messages[0].role).toBe('user')
    })

    it('should export conversation as Markdown', () => {
      const exported = service.exportConversation(mockSession, 'markdown')

      expect(exported).toContain('# Test Session')
      expect(exported).toContain('**Agent:** agent-1')
      expect(exported).toContain('### USER')
      expect(exported).toContain('Hello')
      expect(exported).toContain('### ASSISTANT')
      expect(exported).toContain('Hi there!')
    })

    it('should export conversation as text', () => {
      const exported = service.exportConversation(mockSession, 'text')

      expect(exported).toContain('Conversation: Test Session')
      expect(exported).toContain('Agent: agent-1')
      expect(exported).toContain('[USER]')
      expect(exported).toContain('Hello')
      expect(exported).toContain('[ASSISTANT]')
      expect(exported).toContain('Hi there!')
    })

    it('should include metadata in markdown export when available', () => {
      const sessionWithMetadata: ConversationSession = {
        ...mockSession,
        messages: [
          {
            ...(mockSession.messages ?? [])[0],
            metadata: { tokenCount: 10, totalTimeMs: 500 }
          }
        ]
      }

      const exported = service.exportConversation(sessionWithMetadata, 'markdown')

      expect(exported).toContain('*Tokens: 10, Time: 500ms*')
    })
  })

  describe('integration: full message lifecycle', () => {
    it('should handle complete message workflow', () => {
      // Create user message
      const userMessage = service.createUserMessage('What is TypeScript?', 'agent-1')
      let session = service.addMessageToSession(mockSession, userMessage)

      expect(session.messages!).toHaveLength(3)

      // Create assistant streaming message
      const assistantMessage = service.createAssistantMessage('agent-1')
      session = service.addMessageToSession(session, assistantMessage)

      expect(session.messages!).toHaveLength(4)
      expect(session.messages![3].isStreaming).toBe(true)

      // Finalize streaming message
      const finalized = service.finalizeStreamingMessage(
        assistantMessage,
        'TypeScript is a typed superset of JavaScript',
        2500,
        'gpt-4',
        'openai'
      )

      // Update the message in session
      const updated = service.updateMessageInSession(
        session,
        assistantMessage.id,
        finalized.content,
        finalized.metadata as unknown as Record<string, unknown>
      )

      expect(updated).not.toBeNull()
      expect(updated?.messages![3].content).toBe('TypeScript is a typed superset of JavaScript')
      expect(updated?.messages![3].metadata?.tokenCount).toBe(11) // 44 chars / 4 = 11
      expect(updated?.messages![3].isStreaming).toBe(true) // isStreaming preserved in update
    })
  })
})
