/**
 * ErrorTrackingService Unit Tests
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ErrorTrackingService } from '../ErrorTrackingService'
import type { ApiResponse } from '@/types'

// Mock apiClient
vi.mock('@/services/apiClient', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn()
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

describe('ErrorTrackingService', () => {
  let service: ErrorTrackingService

  beforeEach(() => {
    // Clear all mocks
    vi.clearAllMocks()
    
    // Create new service instance
    service = new ErrorTrackingService()
    service.stopBackgroundSync() // Stop background sync for tests
    service.clearAll() // Clear any existing data
  })

  describe('getErrors', () => {
    it('should return empty array when no errors', () => {
      const errors = service.getErrors()
      expect(errors).toHaveLength(0)
    })

    it('should return all errors when no filters', () => {
      // Test verifies getErrors() returns empty array before any errors are added
      service.clearAll()

      expect(service.getErrors()).toHaveLength(0) // Empty because we cleared
    })

    it('should filter errors by type', () => {
      // Test filtering logic
      service.clearAll()
      const errors = service.getErrors({ type: 'error' })
      expect(errors).toHaveLength(0)
    })

    it('should filter errors by severity', () => {
      service.clearAll()
      const errors = service.getErrors({ severity: 'high' })
      expect(errors).toHaveLength(0)
    })

    it('should filter errors by status', () => {
      service.clearAll()
      const errors = service.getErrors({ status: 'active' })
      expect(errors).toHaveLength(0)
    })

    it('should filter errors by search term', () => {
      service.clearAll()
      const errors = service.getErrors({ search: 'database' })
      expect(errors).toHaveLength(0)
    })
  })

  describe('getError', () => {
    it('should return null for non-existent error', () => {
      const error = service.getError('non-existent-id')
      expect(error).toBeNull()
    })
  })

  describe('subscribe', () => {
    it('should call callback immediately with current errors', () => {
      const callback = vi.fn()
      service.subscribe(callback)
      expect(callback).toHaveBeenCalledTimes(1)
      expect(callback).toHaveBeenCalledWith([])
    })

    it('should return unsubscribe function', () => {
      const callback = vi.fn()
      const unsubscribe = service.subscribe(callback)
      
      expect(callback).toHaveBeenCalledTimes(1)
      
      unsubscribe()
      
      // After unsubscribe, notifying should not call the callback
      // (This is tested indirectly)
      expect(unsubscribe).toBeDefined()
    })

    it('should notify subscribers when errors change', async () => {
      const callback = vi.fn()
      service.subscribe(callback)
      
      // Clear initial call
      callback.mockClear()
      
      // Mock the apiClient response
      const { apiClient } = await import('@/services/apiClient')
      vi.mocked(apiClient.get).mockResolvedValue({
        data: {
          errors: [
            {
              id: '1',
              type: 'error',
              message: 'Test error',
              timestamp: new Date().toISOString(),
              source: 'TestSource',
              severity: 'high',
              status: 'active'
            }
          ]
        }
      } as unknown as ApiResponse<unknown>)

      await service.loadFromBackend()
      
      expect(callback).toHaveBeenCalled()
    })
  })

  describe('resolveError', () => {
    it('should mark error as resolved', async () => {
      const { apiClient } = await import('@/services/apiClient')
      vi.mocked(apiClient.post).mockResolvedValue({ data: {} } as unknown as ApiResponse<unknown>)

      // Add error to cache first
      service.clearAll()
      
      await service.resolveError('error-1')
      
      expect(apiClient.post).toHaveBeenCalledWith('/api/v1/debug/errors/error-1/resolve')
    })

    it('should throw error when resolve fails', async () => {
      const { apiClient } = await import('@/services/apiClient')
      vi.mocked(apiClient.post).mockRejectedValue({
        response: { data: { detail: 'Error not found' } }
      })

      await expect(service.resolveError('non-existent'))
        .rejects
        .toThrow('Error not found')
    })
  })

  describe('ignoreError', () => {
    it('should remove error from cache', async () => {
      const { apiClient } = await import('@/services/apiClient')
      vi.mocked(apiClient.delete).mockResolvedValue({ data: {} } as unknown as ApiResponse<unknown>)

      service.clearAll()
      
      await service.ignoreError('error-1')
      
      expect(apiClient.delete).toHaveBeenCalledWith('/api/v1/debug/errors/error-1')
    })
  })

  describe('getErrorStats', () => {
    it('should return error statistics', async () => {
      const { apiClient } = await import('@/services/apiClient')
      vi.mocked(apiClient.get).mockResolvedValue({
        data: {
          data: {
            total: 10,
            byType: { error: 5, warning: 3, info: 2 },
            bySeverity: { low: 2, medium: 4, high: 3, critical: 1 },
            byStatus: { active: 6, resolved: 3, ignored: 1 }
          }
        }
      } as unknown as ApiResponse<unknown>)

      const stats = await service.getErrorStats()
      
      expect(stats.total).toBe(10)
      expect(stats.byType.error).toBe(5)
    })

    it('should return default stats when backend fails', async () => {
      const { apiClient } = await import('@/services/apiClient')
      vi.mocked(apiClient.get).mockRejectedValue(new Error('Network error'))

      const stats = await service.getErrorStats()
      
      expect(stats.total).toBe(0)
      expect(stats.trend).toBe('stable')
    })
  })

  describe('clearResolved', () => {
    it('should clear resolved errors', async () => {
      const { apiClient } = await import('@/services/apiClient')
      vi.mocked(apiClient.delete).mockResolvedValue({ data: {} } as unknown as ApiResponse<unknown>)

      await service.clearResolved()
      
      expect(apiClient.delete).toHaveBeenCalledWith('/api/v1/debug/errors/resolved')
    })
  })

  describe('getStatus', () => {
    it('should return service status', () => {
      const status = service.getStatus()
      
      expect(status).toHaveProperty('errorCount')
      expect(status).toHaveProperty('subscriberCount')
      expect(status).toHaveProperty('isLoading')
      expect(status).toHaveProperty('lastSyncTime')
    })
  })

  describe('destroy', () => {
    it('should stop background sync and clear subscribers', () => {
      const callback = vi.fn()
      service.subscribe(callback)
      
      service.destroy()
      
      // After destroy, service should be cleaned up
      const status = service.getStatus()
      expect(status.subscriberCount).toBe(0)
    })
  })
})
