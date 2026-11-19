/**
 * ErrorTrackingService - Centralized error tracking and management
 *
 * Purpose:
 * - Single source of truth for error state
 * - Real-time error tracking from backend
 * - Error resolution and management
 * - Reactive updates via subscriber pattern
 *
 * Benefits:
 * - No stale error data (components get current data)
 * - Centralized error management
 * - Easy to debug (all error access goes through service)
 * - Decoupled from React/Zustand
 */

import { apiClient } from '../apiClient'
import { frontendLoggingService } from '../frontendLoggingService'


export type ErrorSeverity = 'low' | 'medium' | 'high' | 'critical'
export type ErrorType = 'error' | 'warning' | 'info'
export type ErrorStatus = 'active' | 'resolved' | 'ignored'

export interface ErrorEntry {
  id: string
  type: ErrorType
  message: string
  stackTrace?: string
  timestamp: string
  source: string
  severity: ErrorSeverity
  context?: Record<string, unknown>
  status: ErrorStatus
  resolvedAt?: string
  resolvedBy?: string
}

export interface ErrorFilters {
  type?: ErrorType | ErrorType[]
  severity?: ErrorSeverity | ErrorSeverity[]
  status?: ErrorStatus | ErrorStatus[]
  source?: string
  search?: string
  from?: string
  to?: string
}

export interface ErrorStats {
  total: number
  byType: Record<ErrorType, number>
  bySeverity: Record<ErrorSeverity, number>
  byStatus: Record<ErrorStatus, number>
  bySource: Record<string, number>
  last24Hours: number
  trend: 'up' | 'down' | 'stable'
}

/** Response shape from GET /api/v1/debug/errors */
interface ErrorListResponse {
  errors: ErrorEntry[]
}

/** Response shape from POST /api/v1/debug/errors */
interface ErrorCreateResponse {
  data: ErrorEntry
}

/** Response shape from GET /api/v1/debug/errors/stats */
interface ErrorStatsResponse {
  data: ErrorStats
}

type ErrorSubscriber = (errors: ErrorEntry[]) => void

export class ErrorTrackingService {
  private errors: ErrorEntry[] = []
  private subscribers: Set<ErrorSubscriber> = new Set()
  private isLoading: boolean = false
  private lastSyncTime: Date | null = null
  private syncInterval: ReturnType<typeof setInterval> | null = null
  private basePath = '/api/v1/debug/errors'

  constructor() {
    // Start background sync
    this.startBackgroundSync()
    // traceService.trace('ErrorTrackingService', 'initialized', {}, ['lifecycle', 'sync'])
  }

  /**
   * Get all errors from cache
   */
  getErrors(filters?: ErrorFilters): ErrorEntry[] {
    let filtered = [...this.errors]

    if (filters) {
      if (filters.type) {
        const types = Array.isArray(filters.type) ? filters.type : [filters.type]
        filtered = filtered.filter(e => types.includes(e.type))
      }
      if (filters.severity) {
        const severities = Array.isArray(filters.severity) ? filters.severity : [filters.severity]
        filtered = filtered.filter(e => severities.includes(e.severity))
      }
      if (filters.status) {
        const statuses = Array.isArray(filters.status) ? filters.status : [filters.status]
        filtered = filtered.filter(e => statuses.includes(e.status))
      }
      if (filters.source) {
        filtered = filtered.filter(e => e.source.includes(filters.source!))
      }
      if (filters.search) {
        filtered = filtered.filter(e => 
          e.message.toLowerCase().includes(filters.search!.toLowerCase())
        )
      }
    }

    return filtered
  }

  /**
   * Get single error from cache by ID
   */
  getError(errorId: string): ErrorEntry | null {
    return this.errors.find(e => e.id === errorId) || null
  }

  /**
   * Subscribe to error changes
   *
   * @param callback - Function called when errors change
   * @returns Unsubscribe function
   */
  subscribe(callback: ErrorSubscriber): () => void {
    this.subscribers.add(callback)
    // Immediately call with current state
    callback(this.errors)
    // Return unsubscribe function
    return () => this.subscribers.delete(callback)
  }

  /**
   * Notify all subscribers of error changes
   */
  private notifySubscribers(): void {
    // traceService.trace('ErrorTrackingService', 'notifiedSubscribers', {
      // subscriberCount: this.subscribers.size,
      // errorCount: this.errors.length
    // }, ['state-change'])
    this.subscribers.forEach(cb => cb(this.errors))
  }

  /**
   * Load errors from backend and update cache
   */
  async loadFromBackend(filters?: ErrorFilters): Promise<void> {
    if (this.isLoading) {
      // traceService.trace('ErrorTrackingService', 'loadFromBackend:already loading', {}, ['sync'])
      return
    }

    this.isLoading = true

    try {
      // Build query params
      const params = new URLSearchParams()
      if (filters) {
        if (filters.type) params.append('type', Array.isArray(filters.type) ? filters.type.join(',') : filters.type)
        if (filters.severity) params.append('severity', Array.isArray(filters.severity) ? filters.severity.join(',') : filters.severity)
        if (filters.status) params.append('status', Array.isArray(filters.status) ? filters.status.join(',') : filters.status)
        if (filters.source) params.append('source', filters.source)
        if (filters.search) params.append('search', filters.search)
        if (filters.from) params.append('from', filters.from)
        if (filters.to) params.append('to', filters.to)
      }

      const response = await apiClient.get<ErrorListResponse>(`${this.basePath}?${params.toString()}`)

      this.errors = response.data?.errors || []
      this.lastSyncTime = new Date()
      this.notifySubscribers()

      // traceService.trace('ErrorTrackingService', 'loadFromBackend:success', {
        // count: this.errors.length,
        // syncTime: this.lastSyncTime.toISOString()
      // }, ['lifecycle', 'api-call', 'sync'])

      // TODO: Re-enable when debugging is needed - clogs logs
      // frontendLoggingService.info('ErrorTrackingService', 'Errors loaded from backend', {
      //   count: this.errors.length
      // })
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error)
      frontendLoggingService.error('ErrorTrackingService', 'Failed to load errors from backend', {
        error: errorMessage
      })

      // traceService.trace('ErrorTrackingService', 'loadFromBackend:error', {
        // error: errorMessage
      // }, ['error'])

      throw error
    } finally {
      this.isLoading = false
    }
  }

  /**
   * Mark error as resolved
   */
  async resolveError(errorId: string): Promise<void> {
    try {
      frontendLoggingService.info('ErrorTrackingService', 'Resolving error', {
        errorId
      })

      await apiClient.post(`${this.basePath}/${errorId}/resolve`)

      // Update cache
      this.errors = this.errors.map(e =>
        e.id === errorId ? { ...e, status: 'resolved', resolvedAt: new Date().toISOString() } : e
      )
      this.notifySubscribers()

      frontendLoggingService.info('ErrorTrackingService', 'Error resolved', {
        errorId
      })
    } catch (error) {
      frontendLoggingService.error('ErrorTrackingService', `Failed to resolve error ${errorId}`, error)
      const message = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || `Failed to resolve error ${errorId}`
      throw new Error(message)
    }
  }

  /**
   * Ignore/remove error
   */
  async ignoreError(errorId: string): Promise<void> {
    try {
      frontendLoggingService.info('ErrorTrackingService', 'Ignoring error', {
        errorId
      })

      await apiClient.delete(`${this.basePath}/${errorId}`)

      // Remove from cache
      this.errors = this.errors.filter(e => e.id !== errorId)
      this.notifySubscribers()

      frontendLoggingService.info('ErrorTrackingService', 'Error ignored', {
        errorId
      })
    } catch (error) {
      frontendLoggingService.error('ErrorTrackingService', `Failed to ignore error ${errorId}`, error)
      const message = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || `Failed to ignore error ${errorId}`
      throw new Error(message)
    }
  }

  /**
   * Report new error
   */
  async reportError(error: Omit<ErrorEntry, 'id' | 'status'>): Promise<ErrorEntry> {
    try {
      frontendLoggingService.info('ErrorTrackingService', 'Reporting error', {
        type: error.type,
        source: error.source,
        message: error.message.substring(0, 100)
      })

      const response = await apiClient.post<ErrorCreateResponse>(this.basePath, error)

      if (!response.data?.data) {
        throw new Error('Failed to report error')
      }

      const newError = response.data.data
      this.errors = [newError, ...this.errors]
      this.notifySubscribers()

      frontendLoggingService.info('ErrorTrackingService', 'Error reported', {
        errorId: newError.id
      })

      return newError
    } catch (error) {
      frontendLoggingService.error('ErrorTrackingService', 'Failed to report error', error)
      const message = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to report error'
      throw new Error(message)
    }
  }

  /**
   * Get error statistics
   */
  async getErrorStats(): Promise<ErrorStats> {
    try {
      const response = await apiClient.get<ErrorStatsResponse>(`${this.basePath}/stats`)
      return response.data?.data || {
        total: 0,
        byType: { error: 0, warning: 0, info: 0 },
        bySeverity: { low: 0, medium: 0, high: 0, critical: 0 },
        byStatus: { active: 0, resolved: 0, ignored: 0 },
        bySource: {},
        last24Hours: 0,
        trend: 'stable' as const
      }
    } catch (error) {
      frontendLoggingService.error('ErrorTrackingService', 'Failed to fetch error stats', error)
      return {
        total: 0,
        byType: { error: 0, warning: 0, info: 0 },
        bySeverity: { low: 0, medium: 0, high: 0, critical: 0 },
        byStatus: { active: 0, resolved: 0, ignored: 0 },
        bySource: {},
        last24Hours: 0,
        trend: 'stable' as const
      }
    }
  }

  /**
   * Clear resolved errors
   */
  async clearResolved(): Promise<void> {
    try {
      frontendLoggingService.info('ErrorTrackingService', 'Clearing resolved errors')

      await apiClient.delete(`${this.basePath}/resolved`)

      // Remove resolved from cache
      this.errors = this.errors.filter(e => e.status !== 'resolved')
      this.notifySubscribers()

      frontendLoggingService.info('ErrorTrackingService', 'Resolved errors cleared')
    } catch (error) {
      frontendLoggingService.error('ErrorTrackingService', 'Failed to clear resolved errors', error)
      const message = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to clear resolved errors'
      throw new Error(message)
    }
  }

  /**
   * Clear all errors from cache
   */
  clearAll(): void {
    this.errors = []
    this.notifySubscribers()

    // traceService.trace('ErrorTrackingService', 'clearAll', {}, ['state-change'])
  }

  /**
   * Start background sync with backend
   * Syncs every 30 seconds to keep cache fresh
   */
  private startBackgroundSync(): void {
    this.syncInterval = setInterval(async () => {
      // traceService.trace('ErrorTrackingService', 'background sync:started', {}, ['sync'])
      await this.loadFromBackend()
      // traceService.trace('ErrorTrackingService', 'background sync:completed', {}, ['sync'])
    }, 30000) // Sync every 30 seconds

    // traceService.trace('ErrorTrackingService', 'background sync:initialized', {
      // intervalMs: 30000
    // }, ['sync'])
  }

  /**
   * Stop background sync
   * Call this when unmounting to prevent memory leaks
   */
  stopBackgroundSync(): void {
    if (this.syncInterval) {
      clearInterval(this.syncInterval)
      this.syncInterval = null

      // traceService.trace('ErrorTrackingService', 'background sync:stopped', {}, ['sync'])
    }
  }

  /**
   * Cleanup - stop background sync and clear subscribers
   */
  destroy(): void {
    this.stopBackgroundSync()
    this.subscribers.clear()

    // traceService.trace('ErrorTrackingService', 'destroyed', {}, ['lifecycle'])
  }

  /**
   * Get service status
   */
  getStatus(): {
    errorCount: number
    subscriberCount: number
    isLoading: boolean
    lastSyncTime: Date | null
  } {
    return {
      errorCount: this.errors.length,
      subscriberCount: this.subscribers.size,
      isLoading: this.isLoading,
      lastSyncTime: this.lastSyncTime
    }
  }
}

// Export singleton instance
export const errorTrackingService = new ErrorTrackingService()
