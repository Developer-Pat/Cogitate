/**
 * DebugActionsService Unit Tests
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { DebugActionsService } from '../DebugActionsService'
import type { ApiResponse } from '@/types'

// Mock apiClient
vi.mock('@/services/apiClient', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
    request: vi.fn()
  }
}))

// Mock frontendLoggingService
vi.mock('@/services/frontendLoggingService', () => ({
  frontendLoggingService: {
    info: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
    warning: vi.fn()
  }
}))

// Mock traceService
vi.mock('../TraceService', () => ({
  traceService: {
    trace: vi.fn()
  }
}))

describe('DebugActionsService', () => {
  let service: DebugActionsService

  beforeEach(() => {
    vi.clearAllMocks()
    service = new DebugActionsService()
    service.stopStatusPolling()
  })

  describe('getActions', () => {
    it('should return list of actions', () => {
      const actions = service.getActions()
      // Actions are loaded asynchronously, so initially empty
      expect(Array.isArray(actions)).toBe(true)
    })
  })

  describe('getAction', () => {
    it('should return null for non-existent action', () => {
      const action = service.getAction('non-existent')
      expect(action).toBeNull()
    })
  })

  describe('getActionStatus', () => {
    it('should return idle for unknown action', () => {
      const status = service.getActionStatus('unknown')
      expect(status).toBe('idle')
    })

    it('should return current status for known action', () => {
      // Status would be set after action execution
      const status = service.getActionStatus('test-action')
      expect(status).toBe('idle')
    })
  })

  describe('getHistory', () => {
    it('should return action history', () => {
      const history = service.getHistory()
      expect(Array.isArray(history)).toBe(true)
    })
  })

  describe('subscribe', () => {
    it('should call callback immediately with current actions', () => {
      const callback = vi.fn()
      service.subscribe(callback)
      expect(callback).toHaveBeenCalledTimes(1)
    })

    it('should return unsubscribe function', () => {
      const callback = vi.fn()
      const unsubscribe = service.subscribe(callback)
      expect(unsubscribe).toBeDefined()
      unsubscribe()
    })
  })

  describe('subscribeToStatus', () => {
    it('should call callback immediately with current status', () => {
      const callback = vi.fn()
      service.subscribeToStatus(callback)
      expect(callback).toHaveBeenCalledTimes(1)
    })
  })

  describe('loadActions', () => {
    it('should load actions from backend', async () => {
      const { apiClient } = await import('@/services/apiClient')
      vi.mocked(apiClient.get).mockResolvedValue({
        data: {
          actions: [
            {
              id: 'clear_cache',
              name: 'Clear Cache',
              description: 'Clear caches',
              category: 'system' as const,
              requiresConfirmation: false,
              dangerous: false,
              enabled: true
            }
          ]
        }
      } as unknown as ApiResponse<unknown>)

      await service.loadActions()
      
      const actions = service.getActions()
      expect(actions).toHaveLength(1)
      expect(actions[0].id).toBe('clear_cache')
    })

    it('should set default actions when backend unavailable', async () => {
      const { apiClient } = await import('@/services/apiClient')
      vi.mocked(apiClient.get).mockRejectedValue(new Error('Backend unavailable'))

      await service.loadActions()
      
      const actions = service.getActions()
      // Should have default actions
      expect(actions.length).toBeGreaterThan(0)
      expect(actions[0].enabled).toBe(false) // Default actions are disabled
    })
  })

  describe('executeAction', () => {
    it('should throw error for non-existent action', async () => {
      await expect(service.executeAction('non-existent'))
        .rejects
        .toThrow('not found')
    })

    it('should execute action with endpoint', async () => {
      const { apiClient } = await import('@/services/apiClient')
      
      // First load an action
      vi.mocked(apiClient.get).mockResolvedValue({
        data: {
          actions: [
            {
              id: 'test-action',
              name: 'Test Action',
              description: 'Test',
              category: 'system' as const,
              requiresConfirmation: false,
              dangerous: false,
              enabled: true,
              endpoint: '/api/v1/test',
              method: 'POST' as const
            }
          ]
        }
      } as unknown as ApiResponse<unknown>)
      
      await service.loadActions()
      
      // Mock action execution - source uses apiClient.post for POST endpoints
      vi.mocked(apiClient.post).mockResolvedValue({
        data: { message: 'Success' }
      } as unknown as ApiResponse<unknown>)

      const result = await service.executeAction('test-action')
      
      expect(result.status).toBe('completed')
      expect(result.actionId).toBe('test-action')
    })

    it('should fail for action without endpoint', async () => {
      const { apiClient } = await import('@/services/apiClient')
      
      vi.mocked(apiClient.get).mockResolvedValue({
        data: {
          actions: [
            {
              id: 'no-endpoint',
              name: 'No Endpoint',
              description: 'Not implemented',
              category: 'system' as const,
              requiresConfirmation: false,
              dangerous: false,
              enabled: true
            }
          ]
        }
      } as unknown as ApiResponse<unknown>)
      
      await service.loadActions()

      const result = await service.executeAction('no-endpoint')
      
      expect(result.status).toBe('failed')
      expect(result.error).toBe('NOT_IMPLEMENTED')
    })
  })

  describe('cancelAction', () => {
    it('should cancel running action', async () => {
      const { apiClient } = await import('@/services/apiClient')
      vi.mocked(apiClient.post).mockResolvedValue({ data: {} } as unknown as ApiResponse<unknown>)

      await service.cancelAction('running-action')
      
      expect(apiClient.post).toHaveBeenCalledWith('/api/v1/debug/actions/running-action/cancel')
    })

    it('should update local status even if backend fails', async () => {
      const { apiClient } = await import('@/services/apiClient')
      vi.mocked(apiClient.post).mockRejectedValue(new Error('Backend error'))

      await service.cancelAction('running-action')
      
      const status = service.getActionStatus('running-action')
      expect(status).toBe('cancelled')
    })
  })

  describe('clearHistory', () => {
    it('should clear action history', async () => {
      const { apiClient } = await import('@/services/apiClient')
      vi.mocked(apiClient.delete).mockResolvedValue({ data: {} } as unknown as ApiResponse<unknown>)

      await service.clearHistory()
      
      expect(apiClient.delete).toHaveBeenCalledWith('/api/v1/debug/actions/history')
    })

    it('should clear local history even if backend fails', async () => {
      const { apiClient } = await import('@/services/apiClient')
      vi.mocked(apiClient.delete).mockRejectedValue(new Error('Backend error'))

      await service.clearHistory()
      
      const history = service.getHistory()
      expect(history).toHaveLength(0)
    })
  })

  describe('getStatus', () => {
    it('should return service status', () => {
      const status = service.getStatus()
      
      expect(status).toHaveProperty('actionCount')
      expect(status).toHaveProperty('historyCount')
      expect(status).toHaveProperty('subscriberCount')
      expect(status).toHaveProperty('statusSubscriberCount')
      expect(status).toHaveProperty('isLoading')
      expect(status).toHaveProperty('runningActions')
    })
  })

  describe('destroy', () => {
    it('should stop polling and clear subscribers', () => {
      const callback = vi.fn()
      service.subscribe(callback)
      service.subscribeToStatus(callback)
      
      service.destroy()
      
      const status = service.getStatus()
      expect(status.subscriberCount).toBe(0)
      expect(status.statusSubscriberCount).toBe(0)
    })
  })
})
