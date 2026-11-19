/**
 * LogManagementService - Enhanced log management
 *
 * Purpose:
 * - Extended log management on top of existing logsService
 * - Frontend log clearing
 * - Log streaming (SSE)
 * - Log sources and levels summary
 * - Reactive updates via subscriber pattern
 *
 * Benefits:
 * - Enhanced functionality beyond basic logsService
 * - Real-time log streaming
 * - Centralized log state management
 * - Decoupled from React/Zustand
 */

import { apiClient } from '../apiClient'
import { API_BASE_URL } from '../apiClient'
import { frontendLoggingService } from '../frontendLoggingService'

import { logsService } from '../domains/system/logsService'
import type { LogEntry, LogFilter } from '@/types'

export interface LogStats {
  total: number
  byLevel: Record<string, number>
  bySource: Record<string, number>
  recentActivity: number
  frontendLogs: number
  backendLogs: number
  last24Hours: number
  trend: 'up' | 'down' | 'stable'
}

export interface LogSource {
  name: string
  count: number
  lastActivity?: string
}

export interface LevelSummary {
  level: string
  count: number
  percentage: number
}

/** Response shape for GET /api/v1/logs/file/recent */
interface FileRecentResponse {
  items: LogEntry[]
  total: number
  file: string
}

/** Response shape for GET /api/v1/logs/export */
interface LogExportResponse {
  size: number
  blob?: Blob
}

/** Response shape for GET /api/v1/logs/stats */
interface LogStatsResponse {
  total: number
  by_level?: Record<string, number>
  byLevel?: Record<string, number>
  by_source?: Record<string, number>
  bySource?: Record<string, number>
  recent_activity?: number
  recentActivity?: number
  frontend_logs?: number
  frontendLogs?: number
  backend_logs?: number
  backendLogs?: number
  last_24_hours?: number
  trend?: 'up' | 'down' | 'stable'
}

/** Response shape for GET /api/v1/logs/sources */
interface LogSourceItem {
  value?: string
  name?: string
  count: number
  last_activity?: string
}

/** Shape of an API error response with nested detail */
interface ApiErrorResponse {
  response?: {
    data?: {
      detail?: string
    }
  }
}

type LogSubscriber = (logs: LogEntry[]) => void

export class LogManagementService {
  private recentLogs: LogEntry[] = []
  private subscribers: Set<LogSubscriber> = new Set()
  private isLoading: boolean = false
  private lastSyncTime: Date | null = null
  private syncInterval: ReturnType<typeof setInterval> | null = null
  private eventSource: EventSource | null = null
  private basePath = '/api/v1/logs'
  private baseUrl = API_BASE_URL

  constructor() {
    // Start background sync
    this.startBackgroundSync()
    // traceService.trace('LogManagementService', 'initialized', {}, ['lifecycle', 'sync'])
  }

  /**
   * Get recent logs from cache
   */
  getLogs(filters?: LogFilter, limit: number = 100): LogEntry[] {
    let filtered = [...this.recentLogs]

    if (filters) {
      if (filters.level) {
        const levels = Array.isArray(filters.level) ? filters.level : [filters.level]
        filtered = filtered.filter(log => levels.includes(log.level))
      }
      if (filters.source) {
        const sources = Array.isArray(filters.source) ? filters.source : [filters.source]
        filtered = filtered.filter(log =>
          sources.some(s => log.source.includes(s))
        )
      }
      if (filters.search) {
        filtered = filtered.filter(log =>
          log.message.toLowerCase().includes(filters.search!.toLowerCase())
        )
      }
    }

    return filtered.slice(0, limit)
  }

  /**
   * Subscribe to log changes
   */
  subscribe(callback: LogSubscriber): () => void {
    this.subscribers.add(callback)
    // Immediately call with current state
    callback(this.recentLogs)
    // Return unsubscribe function
    return () => this.subscribers.delete(callback)
  }

  /**
   * Notify subscribers of log changes
   */
  private notifySubscribers(): void {
    // traceService.trace('LogManagementService', 'notifying subscribers', {
      // subscriberCount: this.subscribers.size,
      // logCount: this.recentLogs.length
    // }, ['state-change'])
    this.subscribers.forEach(cb => cb(this.recentLogs))
  }

  /**
   * Add log to cache
   */
  addLog(log: LogEntry): void {
    this.recentLogs = [log, ...this.recentLogs].slice(0, 500) // Keep last 500
    this.notifySubscribers()
  }

  /**
   * Load recent logs from backend (reads from FILE endpoint)
   */
  async loadRecentLogs(limit: number = 100, _filters?: LogFilter): Promise<void> {
    if (this.isLoading) {
      // traceService.trace('LogManagementService', 'loadRecentLogs:already loading', {}, ['sync'])
      return
    }

    this.isLoading = true

    try {
      // Use file-based endpoint instead of database endpoint
      const response = await apiClient.get<FileRecentResponse>(`${this.basePath}/file/recent?n=${limit}`)

      // The file/recent endpoint returns { items: [...], total: N, file: "..." }
      // Extract the items array — assigning the whole response.data would set
      // recentLogs to an object instead of an array, causing empty display in LogViewer
      this.recentLogs = response.data?.items || []
      this.lastSyncTime = new Date()
      this.notifySubscribers()

      // traceService.trace('LogManagementService', 'loadRecentLogs:success', {
        // count: this.recentLogs.length
      // }, ['lifecycle', 'api-call', 'sync'])

      // TODO: Re-enable this log when debugging is needed - currently clogs logs.txt
      // frontendLoggingService.info('LogManagementService', 'Recent logs loaded', {
      //   count: this.recentLogs.length
      // })
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error)
      frontendLoggingService.error('LogManagementService', 'Failed to load recent logs', {
        error: errorMessage
      })

      // traceService.trace('LogManagementService', 'loadRecentLogs:error', {
        // error: errorMessage
      // }, ['error'])

      throw error
    } finally {
      this.isLoading = false
    }
  }

  /**
   * Get logs from backend with full filtering (uses logsService)
   */
  async getLogsFromBackend(filters?: LogFilter, page: number = 1, pageSize: number = 50) {
    return await logsService.getLogs(filters, page, pageSize)
  }

  /**
   * Export logs
   */
  async exportLogs(format: 'json' | 'csv' = 'json', filters?: LogFilter): Promise<Blob> {
    try {
      frontendLoggingService.info('LogManagementService', 'Exporting logs', {
        format,
        filters
      })

      const params = new URLSearchParams()
      params.append('format', format)
      if (filters) {
        if (filters.level) params.append('level', Array.isArray(filters.level) ? filters.level.join(',') : filters.level)
        if (filters.source) params.append('source', Array.isArray(filters.source) ? filters.source.join(',') : filters.source)
      }

      const response = await apiClient.get<LogExportResponse>(`${this.basePath}/export?${params.toString()}`, {})

      frontendLoggingService.info('LogManagementService', 'Logs exported', {
        format,
        size: response.data?.size
      })

      return response.data as unknown as Blob
    } catch (error) {
      frontendLoggingService.error('LogManagementService', 'Failed to export logs', error)
      throw error
    }
  }

  /**
   * Get log statistics
   */
  async getLogStats(): Promise<LogStats> {
    try {
      const response = await apiClient.get<LogStatsResponse>(`${this.basePath}/stats`)
      const data = response.data || ({} as LogStatsResponse)
      
      return {
        total: data.total || 0,
        byLevel: data.by_level || data.byLevel || {},
        bySource: data.by_source || data.bySource || {},
        recentActivity: data.recent_activity || data.recentActivity || 0,
        frontendLogs: data.frontend_logs || data.frontendLogs || 0,
        backendLogs: data.backend_logs || data.backendLogs || 0,
        last24Hours: data.last_24_hours || 0,
        trend: data.trend || 'stable'
      }
    } catch (error) {
      frontendLoggingService.error('LogManagementService', 'Failed to fetch log stats', error)
      return {
        total: 0,
        byLevel: {},
        bySource: {},
        recentActivity: 0,
        frontendLogs: 0,
        backendLogs: 0,
        last24Hours: 0,
        trend: 'stable' as const
      }
    }
  }

  /**
   * Get log sources
   */
  async getLogSources(): Promise<LogSource[]> {
    try {
      const response = await apiClient.get<LogSourceItem[]>(`${this.basePath}/sources`)
      return (response.data || []).map((s: LogSourceItem) => ({
        name: s.value || s.name || '',
        count: s.count,
        lastActivity: s.last_activity
      }))
    } catch (error) {
      frontendLoggingService.error('LogManagementService', 'Failed to fetch log sources', error)
      return []
    }
  }

  /**
   * Get level summary
   */
  async getLevelSummary(): Promise<LevelSummary[]> {
    try {
      const stats = await this.getLogStats()
      const total = stats.byLevel['debug'] + stats.byLevel['info'] +
                    stats.byLevel['warning'] + stats.byLevel['error'] +
                    stats.byLevel['critical'] || 1

      return Object.entries(stats.byLevel).map(([level, count]) => ({
        level,
        count,
        percentage: Math.round((count / total) * 100)
      }))
    } catch (error) {
      frontendLoggingService.error('LogManagementService', 'Failed to fetch level summary', error)
      return []
    }
  }

  /**
   * Clear frontend logs (deletes log file permanently)
   */
  async clearFrontendLogs(): Promise<void> {
    try {
      frontendLoggingService.info('LogManagementService', 'Clearing frontend logs (file deletion)')

      // Use new file-based endpoint (not database)
      await apiClient.delete(`${this.basePath}/file/clear?frontend=true&backend=false`)

      // Clear from cache
      this.recentLogs = []
      this.notifySubscribers()

      frontendLoggingService.info('LogManagementService', 'Frontend log file deleted')
    } catch (error) {
      frontendLoggingService.error('LogManagementService', 'Failed to clear frontend logs', error)
      const message = (error as ApiErrorResponse)?.response?.data?.detail || 'Failed to clear frontend logs'
      throw new Error(message)
    }
  }

  /**
   * Clear all logs (admin only - deletes both frontend and backend log files)
   */
  async clearAllLogs(olderThan?: string): Promise<void> {
    try {
      frontendLoggingService.warning('LogManagementService', 'Clearing all log files', {
        olderThan
      })

      // Use new file-based endpoint (delete both frontend and backend logs)
      await apiClient.delete(`${this.basePath}/file/clear?frontend=true&backend=true`)

      // Clear from cache
      this.recentLogs = []
      this.notifySubscribers()

      frontendLoggingService.warning('LogManagementService', 'All log files deleted')
    } catch (error) {
      frontendLoggingService.error('LogManagementService', 'Failed to clear all logs', error)
      const message = (error as ApiErrorResponse)?.response?.data?.detail || 'Failed to clear all logs'
      throw new Error(message)
    }
  }

  /**
   * Stream logs via SSE
   */
  streamLogs(callback: (log: LogEntry) => void): () => void {
    try {
      // Use full backend URL for SSE connection (not relative path to frontend dev server)
      const url = `${this.baseUrl}${this.basePath}/stream`
      this.eventSource = new EventSource(url)

      this.eventSource.onmessage = (event) => {
        try {
          const log: LogEntry = JSON.parse(event.data)
          this.recentLogs = [log, ...this.recentLogs].slice(0, 500)
          this.notifySubscribers()
          callback(log)
        } catch (error) {
          frontendLoggingService.error('LogManagementService', 'Failed to parse streamed log', error)
        }
      }

      this.eventSource.onerror = () => {
        frontendLoggingService.error('LogManagementService', 'SSE connection error')
        this.eventSource?.close()
      }

      frontendLoggingService.info('LogManagementService', 'Log streaming started')

      // Return unsubscribe function
      return () => {
        this.eventSource?.close()
        this.eventSource = null
        frontendLoggingService.info('LogManagementService', 'Log streaming stopped')
      }
    } catch (error) {
      frontendLoggingService.error('LogManagementService', 'Failed to start log streaming', error)
      return () => {}
    }
  }

  /**
   * Clear all logs from cache
   */
  clearAll(): void {
    this.recentLogs = []
    this.notifySubscribers()

    // traceService.trace('LogManagementService', 'all logs cleared from cache')
  }

  /**
   * Start background sync with backend
   * Syncs every 5 seconds to keep logs fresh
   */
  private startBackgroundSync(): void {
    this.syncInterval = setInterval(async () => {
      // traceService.trace('LogManagementService', 'background sync:started', {}, ['sync'])
      await this.loadRecentLogs(100).catch(() => {}) // Silently fail
      // traceService.trace('LogManagementService', 'background sync:completed', {}, ['sync'])
    }, 5000) // Sync every 5 seconds

    // traceService.trace('LogManagementService', 'background sync:initialized', {
      // intervalMs: 5000
    // }, ['sync'])
  }

  /**
   * Stop background sync
   */
  stopBackgroundSync(): void {
    if (this.syncInterval) {
      clearInterval(this.syncInterval)
      this.syncInterval = null

      // traceService.trace('LogManagementService', 'background sync:stopped', {}, ['sync'])
    }
  }

  /**
   * Stop SSE streaming
   */
  stopStreaming(): void {
    if (this.eventSource) {
      this.eventSource.close()
      this.eventSource = null
      // traceService.trace('LogManagementService', 'streaming:stopped', {}, ['sync'])
    }
  }

  /**
   * Cleanup - stop sync, streaming, and clear subscribers
   */
  destroy(): void {
    this.stopBackgroundSync()
    this.stopStreaming()
    this.subscribers.clear()
    this.recentLogs = []

    // traceService.trace('LogManagementService', 'destroyed', {}, ['lifecycle'])
  }

  /**
   * Get service status
   */
  getStatus(): {
    logCount: number
    subscriberCount: number
    isLoading: boolean
    lastSyncTime: Date | null
    isStreaming: boolean
  } {
    return {
      logCount: this.recentLogs.length,
      subscriberCount: this.subscribers.size,
      isLoading: this.isLoading,
      lastSyncTime: this.lastSyncTime,
      isStreaming: this.eventSource !== null && this.eventSource.readyState === EventSource.OPEN
    }
  }
}

// Export singleton instance
export const logManagementService = new LogManagementService()
