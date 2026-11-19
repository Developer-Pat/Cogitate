/**
 * SystemDiagnosticsService - Real system diagnostics and health checks
 *
 * Purpose:
 * - Run system diagnostics and health checks
 * - Get real-time system metrics from backend
 * - Track diagnostic history
 * - Reactive updates via subscriber pattern
 *
 * Benefits:
 * - Real system data (not mock)
 * - Centralized diagnostics management
 * - Historical tracking
 * - Decoupled from React/Zustand
 */

import { apiClient } from '../apiClient'
import { frontendLoggingService } from '../frontendLoggingService'


/** Response shape from POST /api/v1/diagnostics/run */
interface DiagnosticsRunResponse {
  results: DiagnosticResult[]
}

/** Response shape from POST /api/v1/diagnostics/{id}/run */
interface DiagnosticRunResponse {
  data: DiagnosticResult
}

/** Response shape from GET /api/v1/diagnostics/metrics */
interface MetricsResponse {
  metrics: SystemMetric[]
}

/** Response shape from GET /api/v1/diagnostics/history */
interface HistoryResponse {
  history: DiagnosticHistory[]
}

/** Response shape from GET /api/v1/health */
interface HealthResponse {
  data: SystemHealth
}

export type DiagnosticStatus = 'pass' | 'fail' | 'warning'
export type MetricTrend = 'up' | 'down' | 'stable'

export interface SystemMetric {
  name: string
  value: number
  unit: string
  status: 'healthy' | 'warning' | 'critical'
  threshold: number
  trend: MetricTrend
  timestamp: string
}

export interface DiagnosticResult {
  id: string
  name: string
  status: DiagnosticStatus
  message: string
  timestamp: string
  details?: string
  metric?: {
    name: string
    value: number
    unit: string
    threshold: number
  }
  duration?: number
}

export interface DiagnosticHistory {
  id: string
  diagnosticId: string
  name: string
  status: DiagnosticStatus
  timestamp: string
  duration: number
}

export interface SystemHealth {
  overall: 'healthy' | 'degraded' | 'critical'
  services: {
    name: string
    status: 'healthy' | 'degraded' | 'unhealthy'
    message?: string
  }[]
  resources: {
    cpu: number
    memory: number
    disk: number
    network: number
  }
  timestamp: string
}

type MetricSubscriber = (metrics: SystemMetric[]) => void
type DiagnosticSubscriber = (results: DiagnosticResult[]) => void

export class SystemDiagnosticsService {
  private metrics: SystemMetric[] = []
  private diagnostics: DiagnosticResult[] = []
  private metricSubscribers: Set<MetricSubscriber> = new Set()
  private diagnosticSubscribers: Set<DiagnosticSubscriber> = new Set()
  private isLoading: boolean = false
  private lastSyncTime: Date | null = null
  private metricsInterval: ReturnType<typeof setInterval> | null = null
  private metricsPath = '/api/v1/diagnostics/metrics'
  private diagnosticsPath = '/api/v1/diagnostics'

  constructor() {
    // Start background metrics sync
    this.startMetricsSync()
    // traceService.trace('SystemDiagnosticsService', 'initialized', {}, ['lifecycle', 'sync'])
  }

  /**
   * Get current system metrics from cache
   */
  getMetrics(): SystemMetric[] {
    return [...this.metrics]
  }

  /**
   * Get diagnostic results from cache
   */
  getDiagnostics(): DiagnosticResult[] {
    return [...this.diagnostics]
  }

  /**
   * Subscribe to metric updates
   */
  subscribeToMetrics(callback: MetricSubscriber): () => void {
    this.metricSubscribers.add(callback)
    // Immediately call with current state
    callback(this.metrics)
    // Return unsubscribe function
    return () => this.metricSubscribers.delete(callback)
  }

  /**
   * Subscribe to diagnostic updates
   */
  subscribeToDiagnostics(callback: DiagnosticSubscriber): () => void {
    this.diagnosticSubscribers.add(callback)
    // Immediately call with current state
    callback(this.diagnostics)
    // Return unsubscribe function
    return () => this.diagnosticSubscribers.delete(callback)
  }

  /**
   * Notify metric subscribers
   */
  private notifyMetricSubscribers(): void {
    // traceService.trace('SystemDiagnosticsService', 'metrics:notified', {
      // subscriberCount: this.metricSubscribers.size,
      // metricCount: this.metrics.length
    // }, ['state-change'])
    this.metricSubscribers.forEach(cb => cb(this.metrics))
  }

  /**
   * Notify diagnostic subscribers
   */
  private notifyDiagnosticSubscribers(): void {
    // traceService.trace('SystemDiagnosticsService', 'diagnostics:notified', {
      // subscriberCount: this.diagnosticSubscribers.size,
      // diagnosticCount: this.diagnostics.length
    // }, ['state-change'])
    this.diagnosticSubscribers.forEach(cb => cb(this.diagnostics))
  }

  /**
   * Run all diagnostics
   */
  async runDiagnostics(): Promise<DiagnosticResult[]> {
    if (this.isLoading) {
      // traceService.trace('SystemDiagnosticsService', 'runDiagnostics:already running', {}, ['sync'])
      return this.diagnostics
    }

    this.isLoading = true

    try {
      frontendLoggingService.info('SystemDiagnosticsService', 'Running all diagnostics')

      const response = await apiClient.post<DiagnosticsRunResponse>(`${this.diagnosticsPath}/run`)

      this.diagnostics = response.data?.results || []
      this.notifyDiagnosticSubscribers()

      frontendLoggingService.info('SystemDiagnosticsService', 'Diagnostics completed', {
        count: this.diagnostics.length,
        passed: this.diagnostics.filter(d => d.status === 'pass').length,
        failed: this.diagnostics.filter(d => d.status === 'fail').length,
        warnings: this.diagnostics.filter(d => d.status === 'warning').length
      })

      // traceService.trace('SystemDiagnosticsService', 'runDiagnostics:success', {
        // count: this.diagnostics.length
      // }, ['lifecycle', 'api-call'])

      return this.diagnostics
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error)
      frontendLoggingService.error('SystemDiagnosticsService', 'Failed to run diagnostics', {
        error: errorMessage
      })

      // traceService.trace('SystemDiagnosticsService', 'runDiagnostics:error', {
        // error: errorMessage
      // }, ['error'])

      throw error
    } finally {
      this.isLoading = false
    }
  }

  /**
   * Run specific diagnostic
   */
  async runDiagnostic(diagnosticId: string): Promise<DiagnosticResult> {
    try {
      frontendLoggingService.info('SystemDiagnosticsService', 'Running diagnostic', {
        diagnosticId
      })

      const response = await apiClient.post<DiagnosticRunResponse>(`${this.diagnosticsPath}/${diagnosticId}/run`)

      const result = response.data?.data as DiagnosticResult

      // Update cache
      this.diagnostics = this.diagnostics.filter(d => d.id !== diagnosticId)
      this.diagnostics.push(result)
      this.notifyDiagnosticSubscribers()

      frontendLoggingService.info('SystemDiagnosticsService', 'Diagnostic completed', {
        diagnosticId,
        status: result.status
      })

      return result
    } catch (error) {
      frontendLoggingService.error('SystemDiagnosticsService', `Failed to run diagnostic ${diagnosticId}`, error)
      const message = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || `Failed to run diagnostic ${diagnosticId}`
      throw new Error(message)
    }
  }

  /**
   * Get system metrics from backend
   */
  async loadMetrics(): Promise<void> {
    try {
      const response = await apiClient.get<MetricsResponse>(this.metricsPath)

      this.metrics = response.data?.metrics || []
      this.lastSyncTime = new Date()
      this.notifyMetricSubscribers()

      // traceService.trace('SystemDiagnosticsService', 'loadMetrics:success', {
        // count: this.metrics.length
      // }, ['lifecycle', 'api-call', 'sync'])
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error)
      frontendLoggingService.error('SystemDiagnosticsService', 'Failed to load metrics', {
        error: errorMessage
      })

      // traceService.trace('SystemDiagnosticsService', 'loadMetrics:error', {
        // error: errorMessage
      // }, ['error'])

      throw error
    }
  }

  /**
   * Get diagnostic history
   */
  async getDiagnosticHistory(): Promise<DiagnosticHistory[]> {
    try {
      const response = await apiClient.get<HistoryResponse>(`${this.diagnosticsPath}/history`)
      return response.data?.history || []
    } catch (error) {
      frontendLoggingService.error('SystemDiagnosticsService', 'Failed to fetch diagnostic history', error)
      return []
    }
  }

  /**
   * Get system health status
   */
  async getSystemHealth(): Promise<SystemHealth> {
    try {
      const response = await apiClient.get<HealthResponse>('/api/v1/health')
      return response.data?.data || {
        overall: 'healthy',
        services: [],
        resources: { cpu: 0, memory: 0, disk: 0, network: 0 },
        timestamp: new Date().toISOString()
      }
    } catch (error) {
      frontendLoggingService.error('SystemDiagnosticsService', 'Failed to fetch system health', error)
      return {
        overall: 'critical',
        services: [],
        resources: { cpu: 0, memory: 0, disk: 0, network: 0 },
        timestamp: new Date().toISOString()
      }
    }
  }

  /**
   * Clear all metrics from cache
   */
  clearMetrics(): void {
    this.metrics = []
    this.notifyMetricSubscribers()

    // traceService.trace('SystemDiagnosticsService', 'clearMetrics', {}, ['state-change'])
  }

  /**
   * Clear all diagnostics from cache
   */
  clearDiagnostics(): void {
    this.diagnostics = []
    this.notifyDiagnosticSubscribers()

    // traceService.trace('SystemDiagnosticsService', 'clearDiagnostics', {}, ['state-change'])
  }

  /**
   * Start background metrics sync
   * Syncs every 10 seconds to keep metrics fresh
   */
  private startMetricsSync(): void {
    this.metricsInterval = setInterval(async () => {
      // traceService.trace('SystemDiagnosticsService', 'background sync:started', {}, ['sync'])
      await this.loadMetrics().catch(() => {}) // Silently fail to avoid noise
      // traceService.trace('SystemDiagnosticsService', 'background sync:completed', {}, ['sync'])
    }, 10000) // Sync every 10 seconds

    // traceService.trace('SystemDiagnosticsService', 'background sync:initialized', {
      // intervalMs: 10000
    // }, ['sync'])
  }

  /**
   * Stop background metrics sync
   */
  stopMetricsSync(): void {
    if (this.metricsInterval) {
      clearInterval(this.metricsInterval)
      this.metricsInterval = null

      // traceService.trace('SystemDiagnosticsService', 'background sync:stopped', {}, ['sync'])
    }
  }

  /**
   * Cleanup - stop sync and clear subscribers
   */
  destroy(): void {
    this.stopMetricsSync()
    this.metricSubscribers.clear()
    this.diagnosticSubscribers.clear()

    // traceService.trace('SystemDiagnosticsService', 'destroyed', {}, ['lifecycle'])
  }

  /**
   * Get service status
   */
  getStatus(): {
    metricCount: number
    diagnosticCount: number
    metricSubscriberCount: number
    diagnosticSubscriberCount: number
    isLoading: boolean
    lastSyncTime: Date | null
  } {
    return {
      metricCount: this.metrics.length,
      diagnosticCount: this.diagnostics.length,
      metricSubscriberCount: this.metricSubscribers.size,
      diagnosticSubscriberCount: this.diagnosticSubscribers.size,
      isLoading: this.isLoading,
      lastSyncTime: this.lastSyncTime
    }
  }
}

// Export singleton instance
export const systemDiagnosticsService = new SystemDiagnosticsService()
