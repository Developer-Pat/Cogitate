/**
 * LiveMonitoringService - Real-time activity monitoring via WebSocket
 *
 * Purpose:
 * - Stream real-time events from backend
 * - Track monitoring metrics
 * - Manage WebSocket connection
 * - Reactive updates via subscriber pattern
 *
 * Benefits:
 * - Real-time visibility into system activity
 * - Centralized monitoring management
 * - WebSocket-based (efficient, low latency)
 * - Decoupled from React/Zustand
 */

import { apiClient } from '../apiClient'
import { API_BASE_URL } from '../apiClient'
import { frontendLoggingService } from '../frontendLoggingService'


export type ActivityEventType = 'request' | 'response' | 'error' | 'system' | 'info'

export interface ActivityEvent {
  id: string
  type: ActivityEventType
  timestamp: string
  source: string
  message: string
  metadata?: Record<string, unknown>
  severity?: 'low' | 'medium' | 'high'
  duration?: number
}

export interface MonitoringMetrics {
  requestsPerSecond: number
  errorsPerSecond: number
  activeConnections: number
  networkThroughput: {
    in: number
    out: number
  }
  avgResponseTime: number
  successRate: number
  timestamp: string
}

export interface MonitoringStats {
  totalEvents: number
  eventsByType: Record<ActivityEventType, number>
  peakRPS: number
  peakErrors: number
  uptime: number
  lastEventAt?: string
}

type EventSubscriber = (event: ActivityEvent) => void
type MetricsSubscriber = (metrics: MonitoringMetrics) => void

export class LiveMonitoringService {
  private events: ActivityEvent[] = []
  private metrics: MonitoringMetrics | null = null
  private subscribers: Set<EventSubscriber> = new Set()
  private metricsSubscribers: Set<MetricsSubscriber> = new Set()
  private ws: WebSocket | null = null
  private isRunning: boolean = false
  private reconnectAttempts: number = 0
  private maxReconnectAttempts: number = 5
  private reconnectDelay: number = 3000
  private metricsInterval: ReturnType<typeof setInterval> | null = null
  private eventsPath = '/api/v1/monitoring/events'
  private metricsPath = '/api/v1/monitoring/metrics'
  private wsUrl: string
  private baseUrl = API_BASE_URL

  constructor() {
    // Build WebSocket URL pointing to backend (not frontend dev server)
    const protocol = this.baseUrl.startsWith('https') ? 'wss:' : 'ws:'
    // Extract host from baseUrl (e.g., 'http://localhost:8000' -> 'localhost:8000')
    const host = this.baseUrl.replace('http://', '').replace('https://', '')
    this.wsUrl = `${protocol}//${host}/api/v1/monitoring/stream`

    // traceService.trace('LiveMonitoringService', 'initialized', {
      // wsUrl: this.wsUrl,
      // baseUrl: this.baseUrl
    // })
  }

  /**
   * Start monitoring (connect WebSocket)
   */
  start(): void {
    if (this.isRunning) {
      // traceService.trace('LiveMonitoringService', 'start: already running, skipping')
      return
    }

    this.isRunning = true
    this.connectWebSocket()
    this.startMetricsPolling()

    frontendLoggingService.info('LiveMonitoringService', 'Monitoring started')
    // traceService.trace('LiveMonitoringService', 'monitoring started')
  }

  /**
   * Stop monitoring (disconnect WebSocket)
   */
  stop(): void {
    this.isRunning = false
    this.disconnectWebSocket()
    this.stopMetricsPolling()

    frontendLoggingService.info('LiveMonitoringService', 'Monitoring stopped')
    // traceService.trace('LiveMonitoringService', 'monitoring stopped')
  }

  /**
   * Get recent events from cache
   */
  getRecentEvents(limit: number = 100): ActivityEvent[] {
    return this.events.slice(0, limit)
  }

  /**
   * Get current metrics
   */
  getCurrentMetrics(): MonitoringMetrics | null {
    return this.metrics
  }

  /**
   * Subscribe to events
   */
  subscribe(callback: EventSubscriber): () => void {
    this.subscribers.add(callback)
    // Immediately call with recent events
    this.events.slice(0, 10).forEach(callback)
    // Return unsubscribe function
    return () => this.subscribers.delete(callback)
  }

  /**
   * Subscribe to metrics
   */
  subscribeToMetrics(callback: MetricsSubscriber): () => void {
    this.metricsSubscribers.add(callback)
    // Immediately call with current metrics if available
    if (this.metrics) {
      callback(this.metrics)
    }
    // Return unsubscribe function
    return () => this.metricsSubscribers.delete(callback)
  }

  /**
   * Notify event subscribers
   */
  private notifySubscribers(event: ActivityEvent): void {
    // traceService.trace('LiveMonitoringService', 'notifying subscribers', {
      // subscriberCount: this.subscribers.size,
      // eventType: event.type
    // })
    this.subscribers.forEach(cb => cb(event))
  }

  /**
   * Notify metrics subscribers
   */
  private notifyMetricsSubscribers(): void {
    if (!this.metrics) return

    // traceService.trace('LiveMonitoringService', 'notifying metrics subscribers', {
      // subscriberCount: this.metricsSubscribers.size
    // })
    this.metricsSubscribers.forEach(cb => cb(this.metrics!))
  }

  /**
   * Connect to WebSocket
   */
  private connectWebSocket(): void {
    try {
      this.ws = new WebSocket(this.wsUrl)

      this.ws.onopen = () => {
        frontendLoggingService.info('LiveMonitoringService', 'WebSocket connected')
        // traceService.trace('LiveMonitoringService', 'WebSocket connected')
        this.reconnectAttempts = 0
      }

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          
          if (data.type === 'event') {
            const activityEvent: ActivityEvent = {
              id: data.id || `event-${Date.now()}`,
              type: data.event_type || data.type || 'info',
              timestamp: data.timestamp || new Date().toISOString(),
              source: data.source || 'unknown',
              message: data.message || '',
              metadata: data.metadata,
              severity: data.severity,
              duration: data.duration
            }

            // Add to events cache (keep last 500)
            this.events = [activityEvent, ...this.events].slice(0, 500)
            this.notifySubscribers(activityEvent)
          } else if (data.type === 'metrics') {
            this.metrics = data.metrics
            this.notifyMetricsSubscribers()
          }
        } catch (error) {
          frontendLoggingService.error('LiveMonitoringService', 'Failed to parse WebSocket message', error)
        }
      }

      this.ws.onerror = (error) => {
        frontendLoggingService.error('LiveMonitoringService', 'WebSocket error', error)
        // traceService.trace('LiveMonitoringService', 'WebSocket error')
      }

      this.ws.onclose = () => {
        frontendLoggingService.warning('LiveMonitoringService', 'WebSocket disconnected')
        // traceService.trace('LiveMonitoringService', 'WebSocket disconnected')

        // Attempt reconnect if still running
        if (this.isRunning && this.reconnectAttempts < this.maxReconnectAttempts) {
          this.reconnectAttempts++
          frontendLoggingService.info('LiveMonitoringService', `Reconnecting (${this.reconnectAttempts}/${this.maxReconnectAttempts})`)
          
          setTimeout(() => {
            if (this.isRunning) {
              this.connectWebSocket()
            }
          }, this.reconnectDelay * this.reconnectAttempts)
        } else if (this.isRunning) {
          frontendLoggingService.error('LiveMonitoringService', 'Max reconnect attempts reached')
        }
      }
    } catch (error) {
      frontendLoggingService.error('LiveMonitoringService', 'Failed to connect WebSocket', error)
      // traceService.trace('LiveMonitoringService', 'WebSocket connection failed', {
        // error: error instanceof Error ? error.message : String(error)
      // })
    }
  }

  /**
   * Disconnect WebSocket
   */
  private disconnectWebSocket(): void {
    if (this.ws) {
      this.ws.close()
      this.ws = null
      // traceService.trace('LiveMonitoringService', 'WebSocket disconnected')
    }
  }

  /**
   * Load recent events from backend (fallback if WebSocket unavailable)
   */
  async loadRecentEvents(limit: number = 100): Promise<void> {
    try {
      const response = await apiClient.get<{ events?: ActivityEvent[] }>(`${this.eventsPath}?limit=${limit}`)
      this.events = response.data?.events || (response.data as ActivityEvent[]) || []
      // traceService.trace('LiveMonitoringService', 'recent events loaded', {
        // count: this.events.length
      // })
    } catch (error) {
      frontendLoggingService.error('LiveMonitoringService', 'Failed to load recent events', error)
      // Use mock data if backend unavailable
      this.setMockEvents()
    }
  }

  /**
   * Load current metrics from backend
   */
  async loadMetrics(): Promise<void> {
    try {
      const response = await apiClient.get<{ metrics?: MonitoringMetrics }>(this.metricsPath)
      this.metrics = response.data?.metrics || (response.data as MonitoringMetrics) || null
      this.notifyMetricsSubscribers()
      // traceService.trace('LiveMonitoringService', 'metrics loaded')
    } catch (error) {
      frontendLoggingService.error('LiveMonitoringService', 'Failed to load metrics', error)
      // Use mock metrics if backend unavailable
      this.setMockMetrics()
    }
  }

  /**
   * Clear event history
   */
  async clearEvents(): Promise<void> {
    try {
      await apiClient.delete(this.eventsPath)
      this.events = []
      frontendLoggingService.info('LiveMonitoringService', 'Events cleared')
    } catch {
      // Clear local events even if backend fails
      this.events = []
      frontendLoggingService.warning('LiveMonitoringService', 'Events cleared (local only)')
    }
  }

  /**
   * Get monitoring stats
   */
  async getStats(): Promise<MonitoringStats> {
    try {
      const response = await apiClient.get<MonitoringStats>('/api/v1/monitoring/stats')
      return response.data || {
        totalEvents: 0,
        eventsByType: { request: 0, response: 0, error: 0, system: 0, info: 0 },
        peakRPS: 0,
        peakErrors: 0,
        uptime: 0
      }
    } catch (error) {
      frontendLoggingService.error('LiveMonitoringService', 'Failed to fetch stats', error)
      return {
        totalEvents: this.events.length,
        eventsByType: this.countEventsByType(),
        peakRPS: 0,
        peakErrors: 0,
        uptime: 0
      }
    }
  }

  /**
   * Count events by type
   */
  private countEventsByType(): Record<ActivityEventType, number> {
    return this.events.reduce((acc, event) => {
      acc[event.type] = (acc[event.type] || 0) + 1
      return acc
    }, {} as Record<ActivityEventType, number>)
  }

  /**
   * Set mock events (fallback when backend unavailable)
   */
  private setMockEvents(): void {
    const now = new Date().toISOString()
    this.events = [
      {
        id: 'mock-1',
        type: 'info',
        timestamp: now,
        source: 'LiveMonitoringService',
        message: 'Monitoring service initialized (mock mode - backend unavailable)'
      }
    ]
  }

  /**
   * Set mock metrics (fallback when backend unavailable)
   */
  private setMockMetrics(): void {
    this.metrics = {
      requestsPerSecond: 0,
      errorsPerSecond: 0,
      activeConnections: 0,
      networkThroughput: { in: 0, out: 0 },
      avgResponseTime: 0,
      successRate: 100,
      timestamp: new Date().toISOString()
    }
  }

  /**
   * Start metrics polling
   */
  private startMetricsPolling(): void {
    this.metricsInterval = setInterval(async () => {
      await this.loadMetrics().catch(() => {}) // Silently fail
    }, 5000) // Poll every 5 seconds

    // traceService.trace('LiveMonitoringService', 'metrics polling started', {
      // intervalMs: 5000
    // })
  }

  /**
   * Stop metrics polling
   */
  private stopMetricsPolling(): void {
    if (this.metricsInterval) {
      clearInterval(this.metricsInterval)
      this.metricsInterval = null

      // traceService.trace('LiveMonitoringService', 'metrics polling stopped')
    }
  }

  /**
   * Cleanup - disconnect and clear subscribers
   */
  destroy(): void {
    this.stop()
    this.subscribers.clear()
    this.metricsSubscribers.clear()
    this.events = []
    this.metrics = null

    // traceService.trace('LiveMonitoringService', 'service destroyed')
  }

  /**
   * Get service status
   */
  getStatus(): {
    isRunning: boolean
    eventCount: number
    hasWebSocket: boolean
    subscriberCount: number
    metricsSubscriberCount: number
    reconnectAttempts: number
  } {
    return {
      isRunning: this.isRunning,
      eventCount: this.events.length,
      hasWebSocket: this.ws !== null && this.ws.readyState === WebSocket.OPEN,
      subscriberCount: this.subscribers.size,
      metricsSubscriberCount: this.metricsSubscribers.size,
      reconnectAttempts: this.reconnectAttempts
    }
  }
}

// Export singleton instance
export const liveMonitoringService = new LiveMonitoringService()
