/**
 * SystemDiagnosticsService Unit Tests
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { SystemDiagnosticsService } from '../SystemDiagnosticsService'
import type { ApiResponse } from '@/types'

// Mock apiClient
vi.mock('@/services/apiClient', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn()
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

describe('SystemDiagnosticsService', () => {
  let service: SystemDiagnosticsService

  beforeEach(() => {
    vi.clearAllMocks()
    service = new SystemDiagnosticsService()
    service.stopMetricsSync()
    service.clearMetrics()
    service.clearDiagnostics()
  })

  describe('getMetrics', () => {
    it('should return empty array when no metrics', () => {
      const metrics = service.getMetrics()
      expect(metrics).toHaveLength(0)
    })

    it('should return cached metrics', () => {
      service.clearMetrics()
      const metrics = service.getMetrics()
      expect(metrics).toEqual([])
    })
  })

  describe('getDiagnostics', () => {
    it('should return empty array when no diagnostics', () => {
      const diagnostics = service.getDiagnostics()
      expect(diagnostics).toHaveLength(0)
    })
  })

  describe('subscribeToMetrics', () => {
    it('should call callback immediately with current metrics', () => {
      const callback = vi.fn()
      service.subscribeToMetrics(callback)
      expect(callback).toHaveBeenCalledTimes(1)
      expect(callback).toHaveBeenCalledWith([])
    })

    it('should return unsubscribe function', () => {
      const callback = vi.fn()
      const unsubscribe = service.subscribeToMetrics(callback)
      
      expect(callback).toHaveBeenCalledTimes(1)
      unsubscribe()
    })
  })

  describe('subscribeToDiagnostics', () => {
    it('should call callback immediately with current diagnostics', () => {
      const callback = vi.fn()
      service.subscribeToDiagnostics(callback)
      expect(callback).toHaveBeenCalledTimes(1)
      expect(callback).toHaveBeenCalledWith([])
    })
  })

  describe('runDiagnostics', () => {
    it('should run all diagnostics and update cache', async () => {
      const { apiClient } = await import('@/services/apiClient')
      vi.mocked(apiClient.post).mockResolvedValue({
        data: {
          results: [
            {
              id: '1',
              name: 'Database Check',
              status: 'pass' as const,
              message: 'Database connected',
              timestamp: new Date().toISOString()
            }
          ]
        }
      } as unknown as ApiResponse<unknown>)

      const results = await service.runDiagnostics()
      
      expect(results).toHaveLength(1)
      expect(apiClient.post).toHaveBeenCalledWith('/api/v1/diagnostics/run')
    })

    it('should throw error when diagnostics fail', async () => {
      const { apiClient } = await import('@/services/apiClient')
      vi.mocked(apiClient.post).mockRejectedValue(new Error('Diagnostics failed'))

      await expect(service.runDiagnostics())
        .rejects
        .toThrow('Diagnostics failed')
    })
  })

  describe('runDiagnostic', () => {
    it('should run specific diagnostic', async () => {
      const { apiClient } = await import('@/services/apiClient')
      vi.mocked(apiClient.post).mockResolvedValue({
        data: {
          data: {
            id: 'db-check',
            name: 'Database Check',
            status: 'pass' as const,
            message: 'OK',
            timestamp: new Date().toISOString()
          }
        }
      } as unknown as ApiResponse<unknown>)

      const result = await service.runDiagnostic('db-check')
      
      expect(result.id).toBe('db-check')
      expect(apiClient.post).toHaveBeenCalledWith('/api/v1/diagnostics/db-check/run')
    })
  })

  describe('loadMetrics', () => {
    it('should load metrics from backend', async () => {
      const { apiClient } = await import('@/services/apiClient')
      vi.mocked(apiClient.get).mockResolvedValue({
        data: {
          metrics: [
            {
              name: 'CPU Usage',
              value: 45,
              unit: '%',
              status: 'healthy' as const,
              threshold: 80,
              trend: 'stable' as const,
              timestamp: new Date().toISOString()
            }
          ]
        }
      } as unknown as ApiResponse<unknown>)

      await service.loadMetrics()
      
      const metrics = service.getMetrics()
      expect(metrics).toHaveLength(1)
      expect(metrics[0].name).toBe('CPU Usage')
    })

    it('should throw error when loading fails', async () => {
      const { apiClient } = await import('@/services/apiClient')
      vi.mocked(apiClient.get).mockRejectedValue(new Error('Network error'))

      await expect(service.loadMetrics())
        .rejects
        .toThrow('Network error')
    })
  })

  describe('getDiagnosticHistory', () => {
    it('should return diagnostic history', async () => {
      const { apiClient } = await import('@/services/apiClient')
      vi.mocked(apiClient.get).mockResolvedValue({
        data: {
          history: [
            {
              id: '1',
              diagnosticId: 'db-check',
              name: 'Database Check',
              status: 'pass' as const,
              timestamp: new Date().toISOString(),
              duration: 150
            }
          ]
        }
      } as unknown as ApiResponse<unknown>)

      const history = await service.getDiagnosticHistory()
      
      expect(history).toHaveLength(1)
    })

    it('should return empty array when backend fails', async () => {
      const { apiClient } = await import('@/services/apiClient')
      vi.mocked(apiClient.get).mockRejectedValue(new Error('Network error'))

      const history = await service.getDiagnosticHistory()
      
      expect(history).toHaveLength(0)
    })
  })

  describe('getSystemHealth', () => {
    it('should return system health status', async () => {
      const { apiClient } = await import('@/services/apiClient')
      vi.mocked(apiClient.get).mockResolvedValue({
        data: {
          data: {
            overall: 'healthy' as const,
            services: [
              { name: 'API', status: 'healthy' as const }
            ],
            resources: { cpu: 45, memory: 60, disk: 30, network: 10 },
            timestamp: new Date().toISOString()
          }
        }
      } as unknown as ApiResponse<unknown>)

      const health = await service.getSystemHealth()
      
      expect(health.overall).toBe('healthy')
      expect(health.resources.cpu).toBe(45)
    })

    it('should return critical health when backend fails', async () => {
      const { apiClient } = await import('@/services/apiClient')
      vi.mocked(apiClient.get).mockRejectedValue(new Error('Network error'))

      const health = await service.getSystemHealth()
      
      expect(health.overall).toBe('critical')
    })
  })

  describe('getStatus', () => {
    it('should return service status', () => {
      const status = service.getStatus()
      
      expect(status).toHaveProperty('metricCount')
      expect(status).toHaveProperty('diagnosticCount')
      expect(status).toHaveProperty('metricSubscriberCount')
      expect(status).toHaveProperty('diagnosticSubscriberCount')
      expect(status).toHaveProperty('isLoading')
      expect(status).toHaveProperty('lastSyncTime')
    })
  })

  describe('destroy', () => {
    it('should stop metrics sync and clear subscribers', () => {
      const callback = vi.fn()
      service.subscribeToMetrics(callback)
      service.subscribeToDiagnostics(callback)
      
      service.destroy()
      
      const status = service.getStatus()
      expect(status.metricSubscriberCount).toBe(0)
      expect(status.diagnosticSubscriberCount).toBe(0)
    })
  })
})
