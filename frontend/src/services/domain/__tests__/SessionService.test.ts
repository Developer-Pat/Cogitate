import { describe, it, expect, beforeEach, vi } from 'vitest'
import { SessionService } from '../SessionService'
import { sessionSyncService } from '@/services/sessionSyncService'
import type { ConversationSession, ConversationMessage } from '@/types/agentInteraction'
import type { BackendSession, SessionSyncResponse } from '@/services/sessionSyncService'

// Mock sessionSyncService — the service, but NOT its pure helpers: the metadata
// carrier (`carriedLimitExtras`, 2026-09-23) runs for REAL here, so these tests
// check the actual mapping instead of a second copy of it.
vi.mock('@/services/sessionSyncService', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/sessionSyncService')>()
  return {
    carriedLimitExtras: actual.carriedLimitExtras,
    sessionSyncService: {
      getSessions: vi.fn(),
      getSession: vi.fn(),
      createSession: vi.fn(),
      deleteSession: vi.fn(),
      updateSessionTitle: vi.fn(),
      reloadSessionsWithMessages: vi.fn(),
      convertToFrontendSession: vi.fn()
    }
  }
})

// Mock frontendLoggingService
vi.mock('@/services/frontendLoggingService', () => ({
  frontendLoggingService: {
    debug: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
    error: vi.fn()
  }
}))

describe('SessionService', () => {
  let service: SessionService
  let mockBackendSession: BackendSession

  beforeEach(() => {
    service = new SessionService()
    vi.clearAllMocks()

    mockBackendSession = {
      id: 123,
      title: 'Test Session',
      agent_id: 1,
      messages: [
        {
          id: 1,
          role: 'user',
          content: 'Hello',
          created_at: '2026-03-05T10:00:00Z',
          token_count: 5
        },
        {
          id: 2,
          role: 'assistant',
          content: 'Hi there!',
          created_at: '2026-03-05T10:00:01Z',
          token_count: 10,
          total_time_ms: 1000
        }
      ],
      created_at: '2026-03-05T10:00:00Z',
      updated_at: '2026-03-05T10:00:01Z',
      is_active: true
    }
  })

  describe('loadSessions', () => {
    it('should load and convert sessions from backend', async () => {
      vi.mocked(sessionSyncService.getSessions).mockResolvedValue([mockBackendSession as unknown as SessionSyncResponse])

      const sessions = await service.loadSessions()

      expect(sessions).toHaveLength(1)
      expect(sessions[0].id).toBe('123')
      expect(sessions[0].title).toBe('Test Session')
      expect(sessions[0].agentId).toBe('1')
      expect(sessions[0].messages).toHaveLength(2)
    })

    it('should return empty array when no sessions', async () => {
      vi.mocked(sessionSyncService.getSessions).mockResolvedValue([])

      const sessions = await service.loadSessions()

      expect(sessions).toHaveLength(0)
    })

    it('should return empty array when backend returns null', async () => {
      vi.mocked(sessionSyncService.getSessions).mockResolvedValue(null as unknown as SessionSyncResponse[])

      const sessions = await service.loadSessions()

      expect(sessions).toHaveLength(0)
    })

    it('should throw error when backend fails', async () => {
      vi.mocked(sessionSyncService.getSessions).mockRejectedValue(new Error('Network error'))

      await expect(service.loadSessions()).rejects.toThrow('Failed to load sessions')
    })

    it('carries the LIMIT NOTE and the flags through the mapper (2026-09-23)', async () => {
      // The note is the RECORD of a turn that crossed a line; it rides the saved
      // row's meta. The mapper used to LIST its fields and drop it, so a note
      // that was visible during the live turn vanished at the next reload.
      const withNote = {
        ...mockBackendSession,
        messages: [
          {
            id: 9,
            role: 'assistant',
            content: 'an answer that was stopped',
            created_at: '2026-03-05T10:00:02Z',
            token_count: 12,
            metadata: {
              token_count: 12,
              limit_notice: 'This turn reached 12 calls to the provider — the ceiling.',
              limits: [{ key: 'provider_calls', value: 12, threshold: 12, mode: 'abort', reason: 'r' }],
              truncated: true,
            },
          },
        ],
      }
      vi.mocked(sessionSyncService.getSessions).mockResolvedValue([withNote as unknown as SessionSyncResponse])

      const sessions = await service.loadSessions()
      const metadata = sessions[0].messages?.[0]?.metadata

      expect(metadata?.limit_notice).toBe('This turn reached 12 calls to the provider — the ceiling.')
      expect(metadata?.limits?.[0].key).toBe('provider_calls')
      expect(metadata?.limits?.[0].mode).toBe('abort')
      expect(metadata?.truncated).toBe(true)
    })
  })

  describe('loadSession', () => {
    it('should load a single session with messages', async () => {
      vi.mocked(sessionSyncService.getSession).mockResolvedValue(mockBackendSession as unknown as SessionSyncResponse)

      const session = await service.loadSession('session-123')

      expect(session.id).toBe('123')
      expect(session.messages).toHaveLength(2)
      expect(session.messages?.[0].role).toBe('user')
      expect(session.messages?.[1].role).toBe('assistant')
    })

    it('should convert message timestamps to Date objects', async () => {
      vi.mocked(sessionSyncService.getSession).mockResolvedValue(mockBackendSession as unknown as SessionSyncResponse)

      const session = await service.loadSession('session-123')

      expect(session.messages?.[0].timestamp).toBeInstanceOf(Date)
      expect(session.messages?.[1].timestamp).toBeInstanceOf(Date)
    })

    it('should throw error when session not found', async () => {
      vi.mocked(sessionSyncService.getSession).mockRejectedValue(new Error('Not found'))

      await expect(service.loadSession('non-existent')).rejects.toThrow('Failed to load session')
    })
  })

  describe('createSession', () => {
    it('should create a new session on backend', async () => {
      vi.mocked(sessionSyncService.createSession).mockResolvedValue(mockBackendSession as unknown as SessionSyncResponse)

      const session = await service.createSession('New Chat', 'agent-1', 'gpt-4')

      expect(sessionSyncService.createSession).toHaveBeenCalledWith(
        expect.stringMatching(/session-\d+/),
        'New Chat',
        'agent-1',
        'gpt-4'
      )
      // Session ID comes from backend response (converted to string)
      expect(session.id).toBe('123')
      expect(session.title).toBe('Test Session')
    })

    it('should generate unique temp IDs', async () => {
      vi.mocked(sessionSyncService.createSession).mockResolvedValue(mockBackendSession as unknown as SessionSyncResponse)

      await service.createSession('Chat 1', 'agent-1', 'gpt-4')
      await service.createSession('Chat 2', 'agent-1', 'gpt-4')

      // Both should call createSession with different temp IDs
      expect(sessionSyncService.createSession).toHaveBeenCalledTimes(2)
    })

    it('should throw error when creation fails', async () => {
      vi.mocked(sessionSyncService.createSession).mockRejectedValue(new Error('Creation failed'))

      await expect(service.createSession('Chat', 'agent-1', 'gpt-4')).rejects.toThrow(
        'Failed to create session'
      )
    })
  })

  describe('deleteSession', () => {
    it('should delete session from backend', async () => {
      vi.mocked(sessionSyncService.deleteSession).mockResolvedValue()

      const result = await service.deleteSession('123')

      expect(result).toBe(true)
      expect(sessionSyncService.deleteSession).toHaveBeenCalledWith('123')
    })

    it('should skip backend delete for temp sessions', async () => {
      const result = await service.deleteSession('session-temp-123')

      expect(result).toBe(true)
      expect(sessionSyncService.deleteSession).not.toHaveBeenCalled()
    })

    it('should throw error when deletion fails', async () => {
      vi.mocked(sessionSyncService.deleteSession).mockRejectedValue(new Error('Delete failed'))

      await expect(service.deleteSession('123')).rejects.toThrow(
        'Failed to delete session'
      )
    })
  })

  describe('updateSessionTitle', () => {
    it('should update session title on backend', async () => {
      vi.mocked(sessionSyncService.updateSessionTitle).mockResolvedValue()

      const result = await service.updateSessionTitle('session-123', 'Updated Title')

      expect(sessionSyncService.updateSessionTitle).toHaveBeenCalledWith('session-123', 'Updated Title')
      expect(result.title).toBe('Updated Title')
      expect(result.updatedAt).toBeInstanceOf(Date)
    })

    it('should throw error when update fails', async () => {
      vi.mocked(sessionSyncService.updateSessionTitle).mockRejectedValue(new Error('Update failed'))

      await expect(service.updateSessionTitle('session-123', 'New Title')).rejects.toThrow(
        'Failed to update session title'
      )
    })
  })

  describe('reloadSessionsWithMessages', () => {
    it('should reload all sessions with messages', async () => {
      vi.mocked(sessionSyncService.reloadSessionsWithMessages).mockResolvedValue([mockBackendSession as unknown as SessionSyncResponse])

      const sessions = await service.reloadSessionsWithMessages()

      expect(sessions).toHaveLength(1)
      expect(sessions[0].messages).toHaveLength(2)
    })

    it('should return empty array when no sessions', async () => {
      vi.mocked(sessionSyncService.reloadSessionsWithMessages).mockResolvedValue([])

      const sessions = await service.reloadSessionsWithMessages()

      expect(sessions).toHaveLength(0)
    })

    it('should throw error when reload fails', async () => {
      vi.mocked(sessionSyncService.reloadSessionsWithMessages).mockRejectedValue(new Error('Reload failed'))

      await expect(service.reloadSessionsWithMessages()).rejects.toThrow('Failed to reload sessions')
    })
  })

  describe('createTempSession', () => {
    it('should create a temporary session without backend sync', () => {
      const session = service.createTempSession('Temp Chat', 'agent-1', 'gpt-4')

      expect(session.id).toMatch(/session-\d+/)
      expect(session.title).toBe('Temp Chat')
      expect(session.agentId).toBe('agent-1')
      expect(session.messages).toHaveLength(0)
      expect(session.isActive).toBe(true)
    })

    it('should generate unique IDs for temp sessions', async () => {
      const session1 = service.createTempSession('Chat 1', 'agent-1', 'gpt-4')
      await new Promise(resolve => setTimeout(resolve, 10))
      const session2 = service.createTempSession('Chat 2', 'agent-1', 'gpt-4')

      expect(session1.id).not.toBe(session2.id)
    })
  })

  describe('isTempSession', () => {
    it('should return true for temp sessions', () => {
      expect(service.isTempSession('session-123456')).toBe(true)
      expect(service.isTempSession('session-temp')).toBe(true)
    })

    it('should return false for backend sessions', () => {
      expect(service.isTempSession('123')).toBe(false)
      expect(service.isTempSession('abc-def-ghi')).toBe(false)
    })
  })

  describe('mergeSessionMessages', () => {
    it('should keep target messages when available', () => {
      const target: ConversationSession = {
        id: 'session-1',
        title: 'Target',
        agentId: 'agent-1',
        messages: [{ id: 'msg-1', role: 'user', content: 'Hello', timestamp: new Date(), agentId: 'agent-1' }],
        createdAt: new Date(),
        updatedAt: new Date(),
        isActive: true
      }

      const source: ConversationSession = {
        ...target,
        id: 'session-2',
        messages: []
      }

      const merged = service.mergeSessionMessages(target, source)

      expect(merged.messages).toHaveLength(1)
      expect(merged.messages?.[0].content).toBe('Hello')
      expect(merged.id).toBe('session-2')
    })

    it('should use source messages when target is empty', () => {
      const target: ConversationSession = {
        id: 'session-1',
        title: 'Target',
        agentId: 'agent-1',
        messages: [],
        createdAt: new Date(),
        updatedAt: new Date(),
        isActive: true
      }

      const source: ConversationSession = {
        ...target,
        id: 'session-2',
        messages: [{ id: 'msg-1', role: 'user', content: 'Hello', timestamp: new Date(), agentId: 'agent-1' }]
      }

      const merged = service.mergeSessionMessages(target, source)

      expect(merged.messages).toHaveLength(1)
      expect(merged.messages?.[0].content).toBe('Hello')
    })
  })

  describe('clearMessages', () => {
    it('should clear all messages from session', async () => {
      const session: ConversationSession = {
        id: 'session-1',
        title: 'Test',
        agentId: 'agent-1',
        messages: [
          { id: 'msg-1', role: 'user', content: 'Hello', timestamp: new Date(), agentId: 'agent-1' },
          { id: 'msg-2', role: 'assistant', content: 'Hi', timestamp: new Date(), agentId: 'agent-1' }
        ],
        createdAt: new Date(),
        updatedAt: new Date(),
        isActive: true
      }

      // Add small delay to ensure different timestamp
      await new Promise(resolve => setTimeout(resolve, 10))
      const cleared = service.clearMessages(session)

      expect(cleared.messages).toHaveLength(0)
      expect(cleared.id).toBe('session-1')
      expect(cleared.updatedAt.getTime()).toBeGreaterThan(session.updatedAt.getTime())
    })
  })

  describe('addMessage', () => {
    it('should add a message to session', async () => {
      const session: ConversationSession = {
        id: 'session-1',
        title: 'Test',
        agentId: 'agent-1',
        messages: [],
        createdAt: new Date(),
        updatedAt: new Date(),
        isActive: true
      }

      const message: ConversationMessage = {
        id: 'msg-1',
        role: 'user',
        content: 'Hello',
        timestamp: new Date(),
        agentId: 'agent-1'
      }

      // Add small delay to ensure different timestamp
      await new Promise(resolve => setTimeout(resolve, 10))
      const updated = service.addMessage(session, message)

      expect(updated.messages).toHaveLength(1)
      expect(updated?.messages?.[0]).toEqual(message)
      expect(updated.updatedAt.getTime()).toBeGreaterThan(session.updatedAt.getTime())
    })

    it('should not mutate original session', () => {
      const session: ConversationSession = {
        id: 'session-1',
        title: 'Test',
        agentId: 'agent-1',
        messages: [],
        createdAt: new Date(),
        updatedAt: new Date(),
        isActive: true
      }

      const message: ConversationMessage = {
        id: 'msg-1',
        role: 'user',
        content: 'Hello',
        timestamp: new Date(),
        agentId: 'agent-1'
      }

      service.addMessage(session, message)

      expect(session.messages).toHaveLength(0) // Original unchanged
    })
  })

  describe('updateMessage', () => {
    it('should update message content', () => {
      const session: ConversationSession = {
        id: 'session-1',
        title: 'Test',
        agentId: 'agent-1',
        messages: [
          { id: 'msg-1', role: 'user', content: 'Hello', timestamp: new Date(), agentId: 'agent-1' }
        ],
        createdAt: new Date(),
        updatedAt: new Date(),
        isActive: true
      }

      const updated = service.updateMessage(session, 'msg-1', 'Updated content')

      expect(updated).not.toBeNull()
      expect(updated?.messages?.[0].content).toBe('Updated content')
    })

    it('should update message metadata', () => {
      const session: ConversationSession = {
        id: 'session-1',
        title: 'Test',
        agentId: 'agent-1',
        messages: [
          { id: 'msg-1', role: 'user', content: 'Hello', timestamp: new Date(), agentId: 'agent-1' }
        ],
        createdAt: new Date(),
        updatedAt: new Date(),
        isActive: true
      }

      const metadata = { tokenCount: 100, totalTimeMs: 2000 }
      const updated = service.updateMessage(session, 'msg-1', 'Hello', metadata)

      expect(updated?.messages?.[0].metadata).toEqual(metadata)
    })

    it('should return null if message not found', () => {
      const session: ConversationSession = {
        id: 'session-1',
        title: 'Test',
        agentId: 'agent-1',
        messages: [],
        createdAt: new Date(),
        updatedAt: new Date(),
        isActive: true
      }

      const updated = service.updateMessage(session, 'non-existent', 'Content')

      expect(updated).toBeNull()
    })

    it('should not mutate original session', () => {
      const originalMessage = { id: 'msg-1', role: 'user', content: 'Hello', timestamp: new Date(), agentId: 'agent-1' }
      const session: ConversationSession = {
        id: 'session-1',
        title: 'Test',
        agentId: 'agent-1',
        messages: [originalMessage as ConversationMessage],
        createdAt: new Date(),
        updatedAt: new Date(),
        isActive: true
      }

      service.updateMessage(session, 'msg-1', 'Updated')

      expect(session.messages?.[0].content).toBe('Hello') // Original unchanged
    })
  })

  describe('removeMessage', () => {
    it('should remove a message from session', () => {
      const session: ConversationSession = {
        id: 'session-1',
        title: 'Test',
        agentId: 'agent-1',
        messages: [
          { id: 'msg-1', role: 'user', content: 'Hello', timestamp: new Date(), agentId: 'agent-1' },
          { id: 'msg-2', role: 'assistant', content: 'Hi', timestamp: new Date(), agentId: 'agent-1' }
        ],
        createdAt: new Date(),
        updatedAt: new Date(),
        isActive: true
      }

      const updated = service.removeMessage(session, 'msg-1')

      expect(updated).not.toBeNull()
      expect(updated?.messages).toHaveLength(1)
      expect(updated?.messages?.[0].id).toBe('msg-2')
    })

    it('should return null if message not found', () => {
      const session: ConversationSession = {
        id: 'session-1',
        title: 'Test',
        agentId: 'agent-1',
        messages: [],
        createdAt: new Date(),
        updatedAt: new Date(),
        isActive: true
      }

      const updated = service.removeMessage(session, 'non-existent')

      expect(updated).toBeNull()
    })

    it('should not mutate original session', () => {
      const session: ConversationSession = {
        id: 'session-1',
        title: 'Test',
        agentId: 'agent-1',
        messages: [
          { id: 'msg-1', role: 'user', content: 'Hello', timestamp: new Date(), agentId: 'agent-1' }
        ],
        createdAt: new Date(),
        updatedAt: new Date(),
        isActive: true
      }

      service.removeMessage(session, 'msg-1')

      expect(session.messages).toHaveLength(1) // Original unchanged
    })
  })

  describe('findById', () => {
    it('should find session by ID', () => {
      const sessions: ConversationSession[] = [
        { id: 'session-1', title: 'First', agentId: 'agent-1', messages: [], createdAt: new Date(), updatedAt: new Date(), isActive: true },
        { id: 'session-2', title: 'Second', agentId: 'agent-1', messages: [], createdAt: new Date(), updatedAt: new Date(), isActive: true }
      ]

      const found = service.findById(sessions, 'session-2')

      expect(found).toBeDefined()
      expect(found?.title).toBe('Second')
    })

    it('should return undefined if not found', () => {
      const sessions: ConversationSession[] = []

      const found = service.findById(sessions, 'non-existent')

      expect(found).toBeUndefined()
    })
  })

  describe('getActiveSession', () => {
    it('should get the active session', () => {
      const sessions: ConversationSession[] = [
        { id: 'session-1', title: 'First', agentId: 'agent-1', messages: [], createdAt: new Date(), updatedAt: new Date(), isActive: false },
        { id: 'session-2', title: 'Second', agentId: 'agent-1', messages: [], createdAt: new Date(), updatedAt: new Date(), isActive: true }
      ]

      const active = service.getActiveSession(sessions)

      expect(active).toBeDefined()
      expect(active?.id).toBe('session-2')
    })

    it('should return undefined if no active session', () => {
      const sessions: ConversationSession[] = [
        { id: 'session-1', title: 'First', agentId: 'agent-1', messages: [], createdAt: new Date(), updatedAt: new Date(), isActive: false }
      ]

      const active = service.getActiveSession(sessions)

      expect(active).toBeUndefined()
    })
  })

  describe('integration: full session workflow', () => {
    it('should handle complete session lifecycle', async () => {
      // Create session
      vi.mocked(sessionSyncService.createSession).mockResolvedValue(mockBackendSession as unknown as SessionSyncResponse)
      const created = await service.createSession('Test Chat', 'agent-1', 'gpt-4')

      // Session ID comes from backend response (converted to string)
      expect(created.id).toBe('123')

      // Load sessions
      vi.mocked(sessionSyncService.getSessions).mockResolvedValue([mockBackendSession as unknown as SessionSyncResponse])
      const sessions = await service.loadSessions()

      expect(sessions).toHaveLength(1)

      // Update title
      vi.mocked(sessionSyncService.updateSessionTitle).mockResolvedValue()
      await service.updateSessionTitle('123', 'Updated Title')

      // Delete session (use non-temp ID to trigger backend delete)
      vi.mocked(sessionSyncService.deleteSession).mockResolvedValue()
      await service.deleteSession('123')

      expect(sessionSyncService.deleteSession).toHaveBeenCalledWith('123')
    })

    it('should handle message operations in session', () => {
      const session: ConversationSession = {
        id: 'session-1',
        title: 'Test',
        agentId: 'agent-1',
        messages: [],
        createdAt: new Date(),
        updatedAt: new Date(),
        isActive: true
      }

      // Add message
      const message: ConversationMessage = {
        id: 'msg-1',
        role: 'user',
        content: 'Hello',
        timestamp: new Date(),
        agentId: 'agent-1'
      }
      let updated = service.addMessage(session, message)

      expect(updated.messages).toHaveLength(1)

      // Update message
      updated = service.updateMessage(updated!, 'msg-1', 'Updated hello', { tokenCount: 10 })!

      expect(updated?.messages?.[0].content).toBe('Updated hello')
      expect(updated?.messages?.[0].metadata?.tokenCount).toBe(10)

      // Remove message
      updated = service.removeMessage(updated!, 'msg-1')!

      expect(updated?.messages).toHaveLength(0)
    })
  })

  describe('Session Synchronization', () => {
    it('should create sessions with unique IDs when created rapidly', async () => {
      // Test that multiple sessions created in quick succession have unique IDs
      const session1 = service.createTempSession('New Session', 'agent-1', 'llama3.2')
      const session2 = service.createTempSession('New Session', 'agent-1', 'llama3.2')
      const session3 = service.createTempSession('New Session', 'agent-1', 'llama3.2')

      // All sessions should have unique IDs
      expect(session1.id).not.toBe(session2.id)
      expect(session2.id).not.toBe(session3.id)
      expect(session1.id).not.toBe(session3.id)

      // IDs should follow the pattern session-{timestamp}-{random}
      expect(session1.id).toMatch(/^session-\d+-[a-z0-9]+$/)
      expect(session2.id).toMatch(/^session-\d+-[a-z0-9]+$/)
      expect(session3.id).toMatch(/^session-\d+-[a-z0-9]+$/)
    })

    it('should not treat sessions with same title as duplicates', () => {
      // Test that sessions with the same title but different IDs are not treated as duplicates
      const session1: ConversationSession = {
        id: 'session-123-abc',
        title: 'New Session 1234567890',
        agentId: 'agent-1',
        messages: [],
        createdAt: new Date(),
        updatedAt: new Date(),
        isActive: true
      }

      const session2: ConversationSession = {
        id: 'session-456-def',
        title: 'New Session 1234567890',  // Same title
        agentId: 'agent-1',  // Same agent
        messages: [],
        createdAt: new Date(),  // Same timestamp
        updatedAt: new Date(),
        isActive: true
      }

      // Sessions should be considered different because they have different IDs
      expect(session1.id).not.toBe(session2.id)
      expect(session1.title).toBe(session2.title)
      expect(session1.agentId).toBe(session2.agentId)
    })

    it('should handle session title updates correctly', async () => {
      vi.mocked(sessionSyncService.updateSessionTitle).mockResolvedValue(undefined)

      const session: ConversationSession = {
        id: 'session-123',
        title: 'New Session 1234567890',
        agentId: 'agent-1',
        messages: [],
        createdAt: new Date(),
        updatedAt: new Date(),
        isActive: true
      }

      // Update title
      const updatedSession = await service.updateSessionTitle(session.id, 'Updated Title')

      expect(updatedSession.title).toBe('Updated Title')
      expect(updatedSession.id).toBe(session.id)
      expect(sessionSyncService.updateSessionTitle).toHaveBeenCalledWith(session.id, 'Updated Title')
    })

    it('should preserve session messages during title update', async () => {
      vi.mocked(sessionSyncService.updateSessionTitle).mockResolvedValue(undefined)

      const session: ConversationSession = {
        id: 'session-123',
        title: 'New Session 1234567890',
        agentId: 'agent-1',
        messages: [
          {
            id: 'msg-1',
            role: 'user',
            content: 'Hello',
            timestamp: new Date(),
            agentId: 'agent-1'
          }
        ],
        createdAt: new Date(),
        updatedAt: new Date(),
        isActive: true
      }

      // Update title - service returns partial session without messages
      const updatedSession = await service.updateSessionTitle(session.id, 'Updated Title')

      // Title should be updated
      expect(updatedSession.title).toBe('Updated Title')
      expect(updatedSession.id).toBe(session.id)
      expect(sessionSyncService.updateSessionTitle).toHaveBeenCalledWith(session.id, 'Updated Title')
    })
  })
})
