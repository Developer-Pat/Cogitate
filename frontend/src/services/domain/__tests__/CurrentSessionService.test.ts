import { describe, it, expect, beforeEach, vi } from 'vitest'
import { CurrentSessionService } from '../CurrentSessionService'
import type { ConversationSession, Agent } from '@/types/agentInteraction'

// Mock traceService
vi.mock('../TraceService', () => ({
  traceService: {
    trace: vi.fn()
  }
}))

describe('CurrentSessionService', () => {
  let service: CurrentSessionService
  let mockSession: ConversationSession
  let mockAgent: Agent

  beforeEach(() => {
    vi.clearAllMocks()
    service = new CurrentSessionService()

    mockSession = {
      id: 'session-123',
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
          agentId: 'agent-1',
          metadata: {
            tokenCount: 10,
            totalTimeMs: 1000
          }
        }
      ],
      createdAt: new Date('2026-03-05T10:00:00Z'),
      updatedAt: new Date('2026-03-05T10:00:01Z'),
      isActive: true
    }

    mockAgent = {
      id: 'agent-1',
      name: 'Test Agent',
      description: 'A test agent',
      capabilities: ['chat', 'analysis'],
      provider: 'openai',
      model: 'gpt-4',
      parameters: {
        temperature: 0.7,
      },
      isAvailable: true
    }
  })

  describe('getCurrentSession', () => {
    it('should return null initially', () => {
      expect(service.getCurrentSession()).toBeNull()
    })

    it('should return current session after setting', () => {
      service.setCurrentSession(mockSession)
      expect(service.getCurrentSession()).toEqual(mockSession)
    })
  })

  describe('getCurrentAgent', () => {
    it('should return null initially', () => {
      expect(service.getCurrentAgent()).toBeNull()
    })

    it('should return current agent after setting', () => {
      service.setCurrentAgent(mockAgent)
      expect(service.getCurrentAgent()).toEqual(mockAgent)
    })
  })

  describe('getFirstMessage', () => {
    it('should return null when no session', () => {
      expect(service.getFirstMessage()).toBeNull()
    })

    it('should return null when session has no messages', () => {
      const emptySession: ConversationSession = {
        ...mockSession,
        messages: []
      }
      service.setCurrentSession(emptySession)
      expect(service.getFirstMessage()).toBeNull()
    })

    it('should return first message content', () => {
      service.setCurrentSession(mockSession)
      expect(service.getFirstMessage()).toBe('Hello')
    })
  })

  describe('getLastAssistantMessage', () => {
    it('should return null when no session', () => {
      expect(service.getLastAssistantMessage()).toBeNull()
    })

    it('should return null when no assistant messages', () => {
      const userOnlySession: ConversationSession = {
        ...mockSession,
        messages: [(mockSession.messages ?? [])[0]]
      }
      service.setCurrentSession(userOnlySession)
      expect(service.getLastAssistantMessage()).toBeNull()
    })

    it('should return last assistant message', () => {
      service.setCurrentSession(mockSession)
      const lastMsg = service.getLastAssistantMessage()
      expect(lastMsg).not.toBeNull()
      expect(lastMsg?.content).toBe('Hi there!')
      expect(lastMsg?.role).toBe('assistant')
    })

    it('should return the most recent assistant message', () => {
      const sessionWithMultipleAssistant: ConversationSession = {
        ...mockSession,
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
            content: 'First response',
            timestamp: new Date('2026-03-05T10:00:01Z'),
            agentId: 'agent-1'
          },
          {
            id: 'msg-3',
            role: 'user',
            content: 'Follow up',
            timestamp: new Date('2026-03-05T10:00:02Z'),
            agentId: 'agent-1'
          },
          {
            id: 'msg-4',
            role: 'assistant',
            content: 'Second response',
            timestamp: new Date('2026-03-05T10:00:03Z'),
            agentId: 'agent-1'
          }
        ]
      }
      service.setCurrentSession(sessionWithMultipleAssistant)
      const lastMsg = service.getLastAssistantMessage()
      expect(lastMsg?.content).toBe('Second response')
    })
  })

  describe('getMessages', () => {
    it('should return empty array when no session', () => {
      expect(service.getMessages()).toEqual([])
    })

    it('should return all messages', () => {
      service.setCurrentSession(mockSession)
      const messages = service.getMessages()
      expect(messages).toHaveLength(2)
      expect(messages[0].content).toBe('Hello')
      expect(messages[1].content).toBe('Hi there!')
    })
  })

  describe('getMessageCount', () => {
    it('should return 0 when no session', () => {
      expect(service.getMessageCount()).toBe(0)
    })

    it('should return message count', () => {
      service.setCurrentSession(mockSession)
      expect(service.getMessageCount()).toBe(2)
    })
  })

  describe('setCurrentSession', () => {
    it('should set the current session', () => {
      service.setCurrentSession(mockSession)
      expect(service.getCurrentSession()).toEqual(mockSession)
    })

    it('should notify subscribers', () => {
      const callback = vi.fn()
      service.subscribe(callback)
      vi.clearAllMocks()

      service.setCurrentSession(mockSession)
      expect(callback).toHaveBeenCalledTimes(1)
      expect(callback).toHaveBeenCalledWith({
        currentSession: mockSession,
        currentAgent: null
      })
    })

    it('should allow setting null', () => {
      service.setCurrentSession(mockSession)
      service.setCurrentSession(null)
      expect(service.getCurrentSession()).toBeNull()
    })
  })

  describe('setCurrentAgent', () => {
    it('should set the current agent', () => {
      service.setCurrentAgent(mockAgent)
      expect(service.getCurrentAgent()).toEqual(mockAgent)
    })

    it('should notify subscribers', () => {
      const callback = vi.fn()
      service.subscribe(callback)
      vi.clearAllMocks()

      service.setCurrentAgent(mockAgent)
      expect(callback).toHaveBeenCalledTimes(1)
      expect(callback).toHaveBeenCalledWith({
        currentSession: null,
        currentAgent: mockAgent
      })
    })

    it('should allow setting null', () => {
      service.setCurrentAgent(mockAgent)
      service.setCurrentAgent(null)
      expect(service.getCurrentAgent()).toBeNull()
    })
  })

  describe('setContext', () => {
    it('should set both session and agent', () => {
      service.setContext(mockSession, mockAgent)
      expect(service.getCurrentSession()).toEqual(mockSession)
      expect(service.getCurrentAgent()).toEqual(mockAgent)
    })

    it('should notify subscribers once', () => {
      const callback = vi.fn()
      service.subscribe(callback)
      vi.clearAllMocks()

      service.setContext(mockSession, mockAgent)
      expect(callback).toHaveBeenCalledTimes(1)
      expect(callback).toHaveBeenCalledWith({
        currentSession: mockSession,
        currentAgent: mockAgent
      })
    })

    it('should be more efficient than separate calls', () => {
      const callback = vi.fn()
      service.subscribe(callback)
      vi.clearAllMocks()

      // Using setContext - 1 notification
      service.setContext(mockSession, mockAgent)
      const contextNotifications = callback.mock.calls.length

      vi.clearAllMocks()
      // Using separate setters - 2 notifications
      service.setCurrentSession(null)
      service.setCurrentAgent(null)
      service.setCurrentSession(mockSession)
      service.setCurrentAgent(mockAgent)
      const separateNotifications = callback.mock.calls.length

      expect(contextNotifications).toBe(1)
      expect(separateNotifications).toBe(4)
    })
  })

  describe('subscribe', () => {
    it('should call subscriber immediately with current context', () => {
      const callback = vi.fn()
      service.setContext(mockSession, mockAgent)
      service.subscribe(callback)
      expect(callback).toHaveBeenCalledTimes(1)
      expect(callback).toHaveBeenCalledWith({
        currentSession: mockSession,
        currentAgent: mockAgent
      })
    })

    it('should notify on session change', () => {
      const callback = vi.fn()
      service.subscribe(callback)
      vi.clearAllMocks()

      service.setCurrentSession(mockSession)
      expect(callback).toHaveBeenCalledTimes(1)
    })

    it('should notify on agent change', () => {
      const callback = vi.fn()
      service.subscribe(callback)
      vi.clearAllMocks()

      service.setCurrentAgent(mockAgent)
      expect(callback).toHaveBeenCalledTimes(1)
    })

    it('should unsubscribe correctly', () => {
      const callback = vi.fn()
      const unsubscribe = service.subscribe(callback)
      vi.clearAllMocks()

      unsubscribe()
      service.setCurrentSession(mockSession)
      expect(callback).not.toHaveBeenCalled()
    })

    it('should support multiple subscribers', () => {
      const callback1 = vi.fn()
      const callback2 = vi.fn()
      service.subscribe(callback1)
      service.subscribe(callback2)
      vi.clearAllMocks()

      service.setCurrentSession(mockSession)
      expect(callback1).toHaveBeenCalledTimes(1)
      expect(callback2).toHaveBeenCalledTimes(1)
    })
  })

  describe('clearContext', () => {
    it('should clear both session and agent', () => {
      service.setContext(mockSession, mockAgent)
      service.clearContext()
      expect(service.getCurrentSession()).toBeNull()
      expect(service.getCurrentAgent()).toBeNull()
    })

    it('should notify subscribers', () => {
      const callback = vi.fn()
      service.subscribe(callback)
      service.setContext(mockSession, mockAgent)
      vi.clearAllMocks()

      service.clearContext()
      expect(callback).toHaveBeenCalledTimes(1)
      expect(callback).toHaveBeenCalledWith({
        currentSession: null,
        currentAgent: null
      })
    })
  })

  describe('getStatus', () => {
    it('should return correct status initially', () => {
      const status = service.getStatus()
      expect(status.hasSession).toBe(false)
      expect(status.hasAgent).toBe(false)
      expect(status.sessionId).toBeNull()
      expect(status.agentId).toBeNull()
      expect(status.subscriberCount).toBe(0)
    })

    it('should return correct status after setting context', () => {
      service.setContext(mockSession, mockAgent)
      const callback = vi.fn()
      service.subscribe(callback)

      const status = service.getStatus()
      expect(status.hasSession).toBe(true)
      expect(status.hasAgent).toBe(true)
      expect(status.sessionId).toBe('session-123')
      expect(status.agentId).toBe('agent-1')
      expect(status.subscriberCount).toBe(1)
    })
  })

  describe('destroy', () => {
    it('should clear context and subscribers', () => {
      const callback = vi.fn()
      service.subscribe(callback)
      service.setContext(mockSession, mockAgent)

      service.destroy()
      expect(service.getStatus().subscriberCount).toBe(0)
      expect(service.getStatus().hasSession).toBe(false)
      expect(service.getStatus().hasAgent).toBe(false)
    })
  })
})
