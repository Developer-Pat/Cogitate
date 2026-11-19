import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { SessionsService } from '../SessionsService'
import { sessionSyncService } from '@/services/sessionSyncService'
import { useCognitiveHubStore } from '@/stores/cognitiveHubStore'
import type { ConversationSession } from '@/types/agentInteraction'
import type { SessionSyncResponse } from '@/services/sessionSyncService'

// Mock sessionSyncService
vi.mock('@/services/sessionSyncService', () => ({
  sessionSyncService: {
    getSessions: vi.fn(),
    createSession: vi.fn(),
    deleteSession: vi.fn(),
    updateSessionTitle: vi.fn()
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

// Mock traceService
vi.mock('../TraceService', () => ({
  traceService: {
    trace: vi.fn()
  }
}))

describe('SessionsService', () => {
  let service: SessionsService
  let mockSession: ConversationSession

  beforeEach(() => {
    vi.clearAllMocks()
    // Reset Zustand store between tests to prevent state leakage from persist middleware
    useCognitiveHubStore.getState().setSessions([])
    useCognitiveHubStore.getState().setActiveSession(null)
    service = new SessionsService()

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
            totalTimeMs: 1000,
            tokensPerSecond: 10
          }
        }
      ],
      createdAt: new Date('2026-03-05T10:00:00Z'),
      updatedAt: new Date('2026-03-05T10:00:01Z'),
      isActive: false
    }
  })

  afterEach(() => {
    service.destroy()
    // Clean up Zustand store after each test
    useCognitiveHubStore.getState().setSessions([])
    useCognitiveHubStore.getState().setActiveSession(null)
  })

  describe('getSessions', () => {
    it('should return empty array initially', () => {
      const sessions = service.getSessions()
      expect(sessions).toEqual([])
    })

    it('should return cached sessions after adding', () => {
      service.addSession(mockSession)
      const sessions = service.getSessions()
      expect(sessions).toHaveLength(1)
      expect(sessions[0].id).toBe('session-123')
    })

    it('should return a copy not the original reference', () => {
      service.addSession(mockSession)
      const sessions1 = service.getSessions()
      const sessions2 = service.getSessions()
      expect(sessions1).toEqual(sessions2)
      expect(sessions1).not.toBe(sessions2)
    })
  })

  describe('getSession', () => {
    it('should return null for non-existent session', () => {
      const session = service.getSession('non-existent')
      expect(session).toBeNull()
    })

    it('should return session by id', () => {
      service.addSession(mockSession)
      const session = service.getSession('session-123')
      expect(session).not.toBeNull()
      expect(session?.id).toBe('session-123')
      expect(session?.title).toBe('Test Session')
    })
  })

  describe('getCurrentSession', () => {
    it('should return null when no active session', () => {
      service.addSession(mockSession)
      const current = service.getCurrentSession()
      expect(current).toBeNull()
    })

    it('should return active session', () => {
      const activeSession: ConversationSession = {
        ...mockSession,
        id: 'active-session',
        isActive: true
      }
      service.addSession(activeSession)
      const current = service.getCurrentSession()
      expect(current).not.toBeNull()
      expect(current?.id).toBe('active-session')
      expect(current?.isActive).toBe(true)
    })
  })

  describe('subscribe', () => {
    it('should call subscriber immediately with current state', () => {
      const callback = vi.fn()
      service.addSession(mockSession)
      service.subscribe(callback)
      expect(callback).toHaveBeenCalledTimes(1)
      expect(callback).toHaveBeenCalledWith([mockSession])
    })

    it('should notify subscriber on session add', () => {
      const callback = vi.fn()
      service.subscribe(callback)
      vi.clearAllMocks()

      service.addSession(mockSession)
      expect(callback).toHaveBeenCalledTimes(1)
      expect(callback).toHaveBeenCalledWith([mockSession])
    })

    it('should notify subscriber on session update', () => {
      const callback = vi.fn()
      service.addSession(mockSession)
      service.subscribe(callback)
      vi.clearAllMocks()

      service.updateSession('session-123', { title: 'Updated Title' })
      expect(callback).toHaveBeenCalledTimes(1)
      const updatedSessions = callback.mock.calls[0][0]
      expect(updatedSessions[0].title).toBe('Updated Title')
    })

    it('should notify subscriber on session remove', () => {
      const callback = vi.fn()
      service.addSession(mockSession)
      service.subscribe(callback)
      vi.clearAllMocks()

      service.removeSession('session-123')
      expect(callback).toHaveBeenCalledTimes(1)
      expect(callback).toHaveBeenCalledWith([])
    })

    it('should unsubscribe correctly', () => {
      const callback = vi.fn()
      const unsubscribe = service.subscribe(callback)
      vi.clearAllMocks()

      unsubscribe()
      service.addSession(mockSession)
      expect(callback).not.toHaveBeenCalled()
    })

    it('should allow multiple subscribers', () => {
      const callback1 = vi.fn()
      const callback2 = vi.fn()
      service.subscribe(callback1)
      service.subscribe(callback2)
      vi.clearAllMocks()

      service.addSession(mockSession)
      expect(callback1).toHaveBeenCalledTimes(1)
      expect(callback2).toHaveBeenCalledTimes(1)
    })
  })

  describe('addSession', () => {
    it('should add session to cache', () => {
      service.addSession(mockSession)
      const sessions = service.getSessions()
      expect(sessions).toHaveLength(1)
      expect(sessions[0]).toEqual(mockSession)
    })

    it('should add session to beginning of array', () => {
      const session2: ConversationSession = {
        ...mockSession,
        id: 'session-2'
      }
      service.addSession(session2)
      service.addSession(mockSession)
      const sessions = service.getSessions()
      expect(sessions[0].id).toBe('session-123')
      expect(sessions[1].id).toBe('session-2')
    })
  })

  describe('updateSession', () => {
    it('should update existing session', () => {
      service.addSession(mockSession)
      service.updateSession('session-123', { title: 'New Title', isActive: true })
      const updated = service.getSession('session-123')
      expect(updated?.title).toBe('New Title')
      expect(updated?.isActive).toBe(true)
    })

    it('should not update non-existent session', () => {
      service.updateSession('non-existent', { title: 'New Title' })
      const sessions = service.getSessions()
      expect(sessions).toHaveLength(0)
    })

    it('should preserve unchanged fields', () => {
      service.addSession(mockSession)
      service.updateSession('session-123', { title: 'New Title' })
      const updated = service.getSession('session-123')
      expect(updated?.agentId).toBe('agent-1')
      expect(updated?.messages).toHaveLength(2)
    })
  })

  describe('removeSession', () => {
    it('should remove session from cache', () => {
      service.addSession(mockSession)
      service.removeSession('session-123')
      const sessions = service.getSessions()
      expect(sessions).toHaveLength(0)
    })

    it('should not remove other sessions', () => {
      const session2: ConversationSession = {
        ...mockSession,
        id: 'session-2'
      }
      service.addSession(mockSession)
      service.addSession(session2)
      service.removeSession('session-123')
      const sessions = service.getSessions()
      expect(sessions).toHaveLength(1)
      expect(sessions[0].id).toBe('session-2')
    })
  })

  describe('setActiveSession', () => {
    it('should set session as active', () => {
      service.addSession(mockSession)
      service.setActiveSession('session-123')
      const session = service.getSession('session-123')
      expect(session?.isActive).toBe(true)
    })

    it('should deactivate other sessions', () => {
      const session2: ConversationSession = {
        ...mockSession,
        id: 'session-2',
        isActive: true
      }
      service.addSession(mockSession)
      service.addSession(session2)
      service.setActiveSession('session-123')
      
      const session1 = service.getSession('session-123')
      const session2Updated = service.getSession('session-2')
      expect(session1?.isActive).toBe(true)
      expect(session2Updated?.isActive).toBe(false)
    })
  })

  describe('clearAll', () => {
    it('should remove all sessions', () => {
      service.addSession(mockSession)
      service.addSession({ ...mockSession, id: 'session-2' })
      service.clearAll()
      const sessions = service.getSessions()
      expect(sessions).toHaveLength(0)
    })

    it('should notify subscribers', () => {
      const callback = vi.fn()
      service.subscribe(callback)
      service.addSession(mockSession)
      vi.clearAllMocks()

      service.clearAll()
      expect(callback).toHaveBeenCalledTimes(1)
      expect(callback).toHaveBeenCalledWith([])
    })
  })

  describe('loadFromBackend', () => {
    it('should load sessions from backend', async () => {
      const mockBackendSessions = [{
        id: 'backend-1',
        title: 'Backend Session',
        agent_id: 'agent-1',
        messages: [],
        created: Date.now(),
        updated: Date.now()
      }]
      vi.mocked(sessionSyncService.getSessions).mockResolvedValue(mockBackendSessions as unknown as SessionSyncResponse[])

      await service.loadFromBackend()
      const sessions = service.getSessions()
      expect(sessions).toHaveLength(1)
      expect(sessions[0].id).toBe('backend-1')
    })

    it('should notify subscribers after loading', async () => {
      const callback = vi.fn()
      service.subscribe(callback)
      vi.clearAllMocks()

      vi.mocked(sessionSyncService.getSessions).mockResolvedValue([])
      await service.loadFromBackend()
      expect(callback).toHaveBeenCalledTimes(1)
    })

    it('should throw error if backend fails', async () => {
      vi.mocked(sessionSyncService.getSessions).mockRejectedValue(new Error('Backend error'))
      await expect(service.loadFromBackend()).rejects.toThrow('Backend error')
    })

    it('should prevent concurrent loads', async () => {
      vi.mocked(sessionSyncService.getSessions).mockImplementation(
        () => new Promise(resolve => setTimeout(() => resolve([]), 100))
      )
      
      // Start two loads concurrently
      const load1 = service.loadFromBackend()
      const load2 = service.loadFromBackend()
      
      await Promise.all([load1, load2])
      // Should only call backend once due to isLoading guard
      expect(sessionSyncService.getSessions).toHaveBeenCalledTimes(1)
    })
  })

  describe('getStatus', () => {
    it('should return correct status', () => {
      service.addSession(mockSession)
      const callback = vi.fn()
      service.subscribe(callback)

      const status = service.getStatus()
      expect(status.sessionCount).toBe(1)
      expect(status.subscriberCount).toBe(1)
      expect(status.isLoading).toBe(false)
    })
  })

  describe('background sync (disabled)', () => {
    it('should NOT start background sync on construction (feature disabled)', () => {
      vi.useFakeTimers()
      const newService = new SessionsService()
      
      const loadSpy = vi.spyOn(newService, 'loadFromBackend')
      vi.advanceTimersByTime(30000)
      
      // Background sync is disabled by design — no automatic sync on construction
      expect(loadSpy).not.toHaveBeenCalled()
      
      newService.destroy()
      vi.useRealTimers()
    })

    it('should stop background sync on destroy (no-op when disabled)', () => {
      vi.useFakeTimers()
      const newService = new SessionsService()
      const loadSpy = vi.spyOn(newService, 'loadFromBackend')
      
      newService.destroy()
      vi.advanceTimersByTime(30000)
      
      expect(loadSpy).not.toHaveBeenCalled()
      vi.useRealTimers()
    })
  })
})
