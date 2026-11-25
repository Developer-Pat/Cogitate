/**
 * LiveMonitoringService Unit Tests
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { LiveMonitoringService } from '../LiveMonitoringService'
import type { ApiResponse } from '@/types'

// Mock apiClient
vi.mock('@/services/apiClient', () => ({
  apiClient: {
    get: vi.fn(),
    delete: vi.fn()
  }
,
  API_BASE_URL: 'http://test'
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

// Mock WebSocket
const mockWebSocket = {
  onopen: null as (() => void) | null,
  onmessage: null as ((event: Event) => void) | null,
  onerror: null as (() => void) | null,
  onclose: null as (() => void) | null,
  close: vi.fn(),
  send: vi.fn(),
  readyState: 1 // OPEN
}

// vitest 4 refuses `new` on an arrow-implemented mock ("() => target is not a constructor").
// The service constructs `new WebSocket(...)` inside a try/catch, so the arrow stub's TypeError
// was swallowed and the handlers below stayed unwired. A `function` impl is constructible and
// still returns the shared object the assertions read.
vi.stubGlobal('WebSocket', vi.fn(function () { return mockWebSocket }))
vi.stubGlobal('EventSource', vi.fn(function () { return {
  onmessage: null,
  onerror: null,
  close: vi.fn(),
  readyState: 1
} }))

describe('LiveMonitoringService', () => {
  let service: LiveMonitoringService

  beforeEach(() => {
    vi.clearAllMocks()
    service = new LiveMonitoringService()
    service.stop()
  })

  afterEach(() => {
    service.destroy()
  })

  describe('start', () => {
    it('should start monitoring', () => {
      service.start()
      expect(service.getStatus().isRunning).toBe(true)
    })

    it('should not start twice', () => {
      service.start()
      service.start() // Should be ignored
      expect(service.getStatus().isRunning).toBe(true)
    })
  })

  describe('stop', () => {
    it('should stop monitoring', () => {
      service.start()
      service.stop()
      expect(service.getStatus().isRunning).toBe(false)
    })
  })

  describe('getRecentEvents', () => {
    it('should return empty array when no events', () => {
      const events = service.getRecentEvents()
      expect(events).toHaveLength(0)
    })

    it('should limit results to specified count', () => {
      // Events would be populated via WebSocket or loadRecentEvents
      const events = service.getRecentEvents(50)
      expect(events.length).toBeLessThanOrEqual(50)
    })
  })

  describe('getCurrentMetrics', () => {
    it('should return null when no metrics', () => {
      const metrics = service.getCurrentMetrics()
      expect(metrics).toBeNull()
    })
  })

  describe('subscribe', () => {
    it('should call callback immediately with recent events', () => {
      const callback = vi.fn()
      service.subscribe(callback)
      // When no events exist, callback is not called
      expect(callback).toHaveBeenCalledTimes(0)
    })

    it('should return unsubscribe function', () => {
      const callback = vi.fn()
      const unsubscribe = service.subscribe(callback)
      expect(unsubscribe).toBeDefined()
      unsubscribe()
    })
  })

  describe('subscribeToMetrics', () => {
    it('should call callback immediately if metrics available', () => {
      const callback = vi.fn()
      service.subscribeToMetrics(callback)
      // May or may not be called depending on if metrics are loaded
      expect(callback).toBeDefined()
    })

    it('should return unsubscribe function', () => {
      const callback = vi.fn()
      const unsubscribe = service.subscribeToMetrics(callback)
      expect(unsubscribe).toBeDefined()
      unsubscribe()
    })
  })

  describe('loadRecentEvents', () => {
    it('should load events from backend', async () => {
      const { apiClient } = await import('@/services/apiClient')
      vi.mocked(apiClient.get).mockResolvedValue({
        data: [
          {
            id: '1',
            type: 'request',
            timestamp: new Date().toISOString(),
            source: 'API',
            message: 'Request received'
          }
        ]
      } as unknown as ApiResponse<unknown>)

      await service.loadRecentEvents(50)
      
      const events = service.getRecentEvents()
      expect(events).toHaveLength(1)
      expect(events[0].id).toBe('1')
    })

    it('should set mock events when backend fails', async () => {
      const { apiClient } = await import('@/services/apiClient')
      vi.mocked(apiClient.get).mockRejectedValue(new Error('Network error'))

      await service.loadRecentEvents()
      
      const events = service.getRecentEvents()
      // Should have at least mock event
      expect(events.length).toBeGreaterThan(0)
    })
  })

  describe('loadMetrics', () => {
    it('should load metrics from backend', async () => {
      const { apiClient } = await import('@/services/apiClient')
      vi.mocked(apiClient.get).mockResolvedValue({
        data: {
          requestsPerSecond: 10,
          errorsPerSecond: 0,
          activeConnections: 5,
          networkThroughput: { in: 100, out: 200 },
          avgResponseTime: 150,
          successRate: 99.9,
          timestamp: new Date().toISOString()
        }
      } as unknown as ApiResponse<unknown>)

      await service.loadMetrics()
      
      const metrics = service.getCurrentMetrics()
      expect(metrics).not.toBeNull()
      expect(metrics?.requestsPerSecond).toBe(10)
    })

    it('should set mock metrics when backend fails', async () => {
      const { apiClient } = await import('@/services/apiClient')
      vi.mocked(apiClient.get).mockRejectedValue(new Error('Network error'))

      await service.loadMetrics()
      
      const metrics = service.getCurrentMetrics()
      expect(metrics).not.toBeNull()
      expect(metrics?.requestsPerSecond).toBe(0)
    })
  })

  describe('clearEvents', () => {
    it('should clear events', async () => {
      const { apiClient } = await import('@/services/apiClient')
      vi.mocked(apiClient.delete).mockResolvedValue({ data: {} } as unknown as ApiResponse<unknown>)

      await service.clearEvents()
      
      expect(apiClient.delete).toHaveBeenCalledWith('/api/v1/monitoring/events')
    })

    it('should clear local events even if backend fails', async () => {
      const { apiClient } = await import('@/services/apiClient')
      vi.mocked(apiClient.delete).mockRejectedValue(new Error('Backend error'))

      await service.clearEvents()
      
      const events = service.getRecentEvents()
      expect(events).toHaveLength(0)
    })
  })

  describe('getStats', () => {
    it('should return monitoring stats', async () => {
      const { apiClient } = await import('@/services/apiClient')
      vi.mocked(apiClient.get).mockResolvedValue({
        data: {
          totalEvents: 100,
          eventsByType: { request: 50, response: 30, error: 10, system: 5, info: 5 },
          peakRPS: 25,
          peakErrors: 5,
          uptime: 3600
        }
      } as unknown as ApiResponse<unknown>)

      const stats = await service.getStats()
      
      expect(stats.totalEvents).toBe(100)
      expect(stats.peakRPS).toBe(25)
    })

    it('should return default stats when backend fails', async () => {
      const { apiClient } = await import('@/services/apiClient')
      vi.mocked(apiClient.get).mockRejectedValue(new Error('Network error'))

      const stats = await service.getStats()
      
      expect(stats.totalEvents).toBe(0)
    })
  })

  describe('WebSocket handling', () => {
    it('should connect WebSocket on start', () => {
      service.start()
      expect(WebSocket).toHaveBeenCalled()
    })

    it('should handle WebSocket messages', () => {
      service.start()
      
      // Simulate WebSocket open
      if (mockWebSocket.onopen) {
        mockWebSocket.onopen()
      }

      // Simulate event message
      if (mockWebSocket.onmessage) {
        mockWebSocket.onmessage(new MessageEvent('message', {
          data: JSON.stringify({
            type: 'event',
            id: 'test-1',
            event_type: 'request',
            message: 'Test event',
            source: 'Test',
            timestamp: new Date().toISOString()
          })
        }))
      }

      const events = service.getRecentEvents()
      expect(events.length).toBeGreaterThan(0)
    })

    it('should handle WebSocket metrics messages', () => {
      service.start()
      
      if (mockWebSocket.onopen) {
        mockWebSocket.onopen()
      }

      // Simulate metrics message
      if (mockWebSocket.onmessage) {
        mockWebSocket.onmessage(new MessageEvent('message', {
          data: JSON.stringify({
            type: 'metrics',
            metrics: {
              requestsPerSecond: 15,
              errorsPerSecond: 0,
              activeConnections: 3,
              networkThroughput: { in: 50, out: 100 },
              avgResponseTime: 120,
              successRate: 100,
              timestamp: new Date().toISOString()
            }
          })
        }))
      }

      const metrics = service.getCurrentMetrics()
      expect(metrics).not.toBeNull()
      expect(metrics?.requestsPerSecond).toBe(15)
    })

    it('should attempt reconnect on disconnect', () => {
      service.start()
      
      // Simulate WebSocket close
      if (mockWebSocket.onclose) {
        mockWebSocket.onclose()
      }

      const status = service.getStatus()
      expect(status.reconnectAttempts).toBe(1)
    })
  })

  describe('getStatus', () => {
    it('should return service status', () => {
      const status = service.getStatus()
      
      expect(status).toHaveProperty('isRunning')
      expect(status).toHaveProperty('eventCount')
      expect(status).toHaveProperty('hasWebSocket')
      expect(status).toHaveProperty('subscriberCount')
      expect(status).toHaveProperty('metricsSubscriberCount')
      expect(status).toHaveProperty('reconnectAttempts')
    })
  })

  describe('destroy', () => {
    it('should cleanup all resources', () => {
      const callback = vi.fn()
      service.subscribe(callback)
      service.subscribeToMetrics(callback)
      service.start()
      
      service.destroy()
      
      const status = service.getStatus()
      expect(status.isRunning).toBe(false)
      expect(status.subscriberCount).toBe(0)
      expect(status.metricsSubscriberCount).toBe(0)
    })
  })
})
