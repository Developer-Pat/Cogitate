/**
 * DebugActionsService - Execute debug operations safely
 *
 * Purpose:
 * - List available debug actions
 * - Execute debug operations
 * - Track action status and history
 * - Reactive updates via subscriber pattern
 *
 * Benefits:
 * - Centralized debug action management
 * - Real backend integration (not mock)
 * - Action history tracking
 * - Decoupled from React/Zustand
 */

import { apiClient } from '../apiClient'
import { frontendLoggingService } from '../frontendLoggingService'
import type { ApiResponse } from '@/types'


/** Response shape from GET /api/v1/debug/actions */
interface ActionsListResponse {
  actions: DebugAction[]
}

/** Response shape from GET /api/v1/debug/actions/history */
interface ActionHistoryResponse {
  history: ActionHistory[]
}

export type DebugActionCategory = 'system' | 'performance' | 'diagnostic' | 'maintenance'
export type DebugActionStatus = 'idle' | 'running' | 'completed' | 'failed' | 'cancelled'

export interface DebugAction {
  id: string
  name: string
  description: string
  category: DebugActionCategory
  requiresConfirmation: boolean
  dangerous: boolean
  endpoint?: string
  method?: 'POST' | 'DELETE' | 'PUT' | 'GET'
  enabled: boolean
}

export interface ActionResult {
  actionId: string
  actionName: string
  status: DebugActionStatus
  message: string
  output?: string
  error?: string
  startedAt: string
  completedAt?: string
  duration?: number
}

export interface ActionHistory {
  id: string
  actionId: string
  actionName: string
  status: DebugActionStatus
  executedAt: string
  executedBy?: string
  duration?: number
  result?: string
}

type ActionSubscriber = (actions: DebugAction[]) => void
type StatusSubscriber = (status: Record<string, DebugActionStatus>) => void

export class DebugActionsService {
  private actions: DebugAction[] = []
  private actionStatus: Record<string, DebugActionStatus> = {}
  private history: ActionHistory[] = []
  private subscribers: Set<ActionSubscriber> = new Set()
  private statusSubscribers: Set<StatusSubscriber> = new Set()
  private isLoading: boolean = false
  private statusPollingInterval: ReturnType<typeof setInterval> | null = null
  private basePath = '/api/v1/debug/actions'

  constructor() {
    // Load actions on init
    this.loadActions()
    // Start status polling for running actions
    this.startStatusPolling()
    // traceService.trace('DebugActionsService', 'initialized')
  }

  /**
   * Get all available debug actions
   */
  getActions(): DebugAction[] {
    return [...this.actions]
  }

  /**
   * Get action by ID
   */
  getAction(actionId: string): DebugAction | null {
    return this.actions.find(a => a.id === actionId) || null
  }

  /**
   * Get action status
   */
  getActionStatus(actionId: string): DebugActionStatus {
    return this.actionStatus[actionId] || 'idle'
  }

  /**
   * Get all action statuses
   */
  getAllStatuses(): Record<string, DebugActionStatus> {
    return { ...this.actionStatus }
  }

  /**
   * Get action history
   */
  getHistory(): ActionHistory[] {
    return [...this.history]
  }

  /**
   * Subscribe to action changes
   */
  subscribe(callback: ActionSubscriber): () => void {
    this.subscribers.add(callback)
    // Immediately call with current state
    callback(this.actions)
    // Return unsubscribe function
    return () => this.subscribers.delete(callback)
  }

  /**
   * Subscribe to status changes
   */
  subscribeToStatus(callback: StatusSubscriber): () => void {
    this.statusSubscribers.add(callback)
    // Immediately call with current state
    callback(this.actionStatus)
    // Return unsubscribe function
    return () => this.statusSubscribers.delete(callback)
  }

  /**
   * Notify action subscribers
   */
  private notifySubscribers(): void {
    // traceService.trace('DebugActionsService', 'notifying subscribers', {
      // subscriberCount: this.subscribers.size,
      // actionCount: this.actions.length
    // })
    this.subscribers.forEach(cb => cb(this.actions))
  }

  /**
   * Notify status subscribers
   */
  private notifyStatusSubscribers(): void {
    // traceService.trace('DebugActionsService', 'notifying status subscribers', {
      // subscriberCount: this.statusSubscribers.size
    // })
    this.statusSubscribers.forEach(cb => cb({ ...this.actionStatus }))
  }

  /**
   * Load available actions from backend
   */
  async loadActions(): Promise<void> {
    if (this.isLoading) {
      // traceService.trace('DebugActionsService', 'loadActions: already loading, skipping')
      return
    }

    this.isLoading = true

    try {
      const response = await apiClient.get<ActionsListResponse>(this.basePath)

      this.actions = response.data?.actions || []
      this.notifySubscribers()

      // traceService.trace('DebugActionsService', 'actions loaded', {
        // count: this.actions.length
      // })

      frontendLoggingService.info('DebugActionsService', 'Debug actions loaded', {
        count: this.actions.length
      })
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error)
      frontendLoggingService.error('DebugActionsService', 'Failed to load actions', {
        error: errorMessage
      })

      // traceService.trace('DebugActionsService', 'loadActions failed', {
        // error: errorMessage
      // })

      // Set default actions if backend unavailable
      this.setDefaultActions()
    } finally {
      this.isLoading = false
    }
  }

  /**
   * Set default actions when backend unavailable
   */
  private setDefaultActions(): void {
    this.actions = [
      {
        id: 'clear_cache',
        name: 'Clear Cache',
        description: 'Clear all application caches',
        category: 'system',
        requiresConfirmation: false,
        dangerous: false,
        enabled: false
      },
      {
        id: 'force_gc',
        name: 'Force Garbage Collection',
        description: 'Trigger manual garbage collection',
        category: 'performance',
        requiresConfirmation: false,
        dangerous: false,
        enabled: false
      },
      {
        id: 'reset_db_connections',
        name: 'Reset Database Connections',
        description: 'Reset all database connections',
        category: 'system',
        requiresConfirmation: true,
        dangerous: true,
        enabled: false
      },
      {
        id: 'generate_performance_report',
        name: 'Generate Performance Report',
        description: 'Create detailed performance analysis',
        category: 'performance',
        requiresConfirmation: false,
        dangerous: false,
        enabled: false
      },
      {
        id: 'run_health_check',
        name: 'Run Health Check',
        description: 'Execute comprehensive system health check',
        category: 'diagnostic',
        requiresConfirmation: false,
        dangerous: false,
        enabled: false
      },
      {
        id: 'flush_logs',
        name: 'Flush Logs',
        description: 'Clear all log buffers',
        category: 'maintenance',
        requiresConfirmation: true,
        dangerous: true,
        enabled: false
      },
      {
        id: 'restart_services',
        name: 'Restart Services',
        description: 'Gracefully restart all background services',
        category: 'system',
        requiresConfirmation: true,
        dangerous: true,
        enabled: false
      },
      {
        id: 'memory_dump',
        name: 'Memory Dump',
        description: 'Create memory usage snapshot',
        category: 'diagnostic',
        requiresConfirmation: false,
        dangerous: false,
        enabled: false
      }
    ]
    this.notifySubscribers()
  }

  /**
   * Execute a debug action
   */
  async executeAction(actionId: string): Promise<ActionResult> {
    const action = this.getAction(actionId)
    if (!action) {
      throw new Error(`Action ${actionId} not found`)
    }

    try {
      frontendLoggingService.info('DebugActionsService', 'Executing action', {
        actionId,
        actionName: action.name
      })

      // Update status to running
      this.actionStatus[actionId] = 'running'
      this.notifyStatusSubscribers()

      // If action has endpoint, call it
      if (action.endpoint) {
        const method = (action.method || 'POST').toUpperCase()
        let response: ApiResponse<Record<string, unknown>>
        if (method === 'GET') {
          response = await apiClient.get<Record<string, unknown>>(action.endpoint)
        } else if (method === 'DELETE') {
          response = await apiClient.delete<Record<string, unknown>>(action.endpoint)
        } else {
          response = await apiClient.post<Record<string, unknown>>(action.endpoint)
        }

        const data = response.data || {}
        const result: ActionResult = {
          actionId,
          actionName: action.name,
          status: 'completed',
          message: (data.message as string) || 'Action completed successfully',
          output: data.output as string | undefined,
          startedAt: new Date().toISOString(),
          completedAt: new Date().toISOString(),
          duration: data.duration as number | undefined
        }

        // Add to history
        this.addToHistory(result)

        // Update status
        this.actionStatus[actionId] = 'completed'
        this.notifyStatusSubscribers()

        frontendLoggingService.info('DebugActionsService', 'Action completed', {
          actionId,
          duration: result.duration
        })

        return result
      } else {
        // No endpoint - action not implemented
        const result: ActionResult = {
          actionId,
          actionName: action.name,
          status: 'failed',
          message: 'Action not implemented - backend endpoint not available',
          error: 'NOT_IMPLEMENTED',
          startedAt: new Date().toISOString(),
          completedAt: new Date().toISOString(),
          duration: 0
        }

        this.actionStatus[actionId] = 'failed'
        this.notifyStatusSubscribers()

        return result
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error)
      frontendLoggingService.error('DebugActionsService', `Failed to execute action ${actionId}`, {
        error: errorMessage
      })

      this.actionStatus[actionId] = 'failed'
      this.notifyStatusSubscribers()

      const result: ActionResult = {
        actionId,
        actionName: action.name,
        status: 'failed',
        message: `Action failed: ${errorMessage}`,
        error: errorMessage,
        startedAt: new Date().toISOString(),
        completedAt: new Date().toISOString(),
        duration: 0
      }

      this.addToHistory(result)

      return result
    }
  }

  /**
   * Get action status from backend
   */
  async getActionStatusFromBackend(actionId: string): Promise<DebugActionStatus> {
    try {
      const response = await apiClient.get<{ status: DebugActionStatus }>(`${this.basePath}/${actionId}/status`)
      const status = response.data?.status || 'idle'
      this.actionStatus[actionId] = status
      this.notifyStatusSubscribers()
      return status
    } catch {
      return this.actionStatus[actionId] || 'idle'
    }
  }

  /**
   * Cancel a running action
   */
  async cancelAction(actionId: string): Promise<void> {
    try {
      frontendLoggingService.info('DebugActionsService', 'Cancelling action', {
        actionId
      })

      await apiClient.post(`${this.basePath}/${actionId}/cancel`)

      this.actionStatus[actionId] = 'cancelled'
      this.notifyStatusSubscribers()

      frontendLoggingService.info('DebugActionsService', 'Action cancelled', {
        actionId
      })
    } catch (_error) {
      frontendLoggingService.error('DebugActionsService', `Failed to cancel action ${actionId}`, _error)
      // Still update local status
      this.actionStatus[actionId] = 'cancelled'
      this.notifyStatusSubscribers()
    }
  }

  /**
   * Add result to history
   */
  private addToHistory(result: ActionResult): void {
    const historyEntry: ActionHistory = {
      id: `${result.actionId}-${Date.now()}`,
      actionId: result.actionId,
      actionName: result.actionName,
      status: result.status,
      executedAt: result.startedAt,
      duration: result.duration,
      result: result.output || result.message
    }

    this.history = [historyEntry, ...this.history].slice(0, 50) // Keep last 50
  }

  /**
   * Load action history from backend
   */
  async loadHistory(): Promise<void> {
    try {
      const response = await apiClient.get<ActionHistoryResponse>(`${this.basePath}/history`)
      this.history = response.data?.history || []
    } catch {
      // Keep local history if backend unavailable
      // traceService.trace('DebugActionsService', 'loadHistory failed, using local history')
    }
  }

  /**
   * Clear action history
   */
  async clearHistory(): Promise<void> {
    try {
      await apiClient.delete(`${this.basePath}/history`)
      this.history = []
      frontendLoggingService.info('DebugActionsService', 'History cleared')
    } catch {
      // Clear local history even if backend fails
      this.history = []
      frontendLoggingService.warning('DebugActionsService', 'History cleared (local only)')
    }
  }

  /**
   * Start status polling for running actions
   */
  private startStatusPolling(): void {
    this.statusPollingInterval = setInterval(async () => {
      const runningActions = Object.entries(this.actionStatus)
        .filter(([_, status]) => status === 'running')
        .map(([id]) => id)

      if (runningActions.length > 0) {
        // traceService.trace('DebugActionsService', 'polling status for running actions', {
          // count: runningActions.length
        // })
        await Promise.all(
          runningActions.map(id => this.getActionStatusFromBackend(id).catch(() => {}))
        )
      }
    }, 2000) // Poll every 2 seconds

    // traceService.trace('DebugActionsService', 'status polling started', {
      // intervalMs: 2000
    // })
  }

  /**
   * Stop status polling
   */
  stopStatusPolling(): void {
    if (this.statusPollingInterval) {
      clearInterval(this.statusPollingInterval)
      this.statusPollingInterval = null

      // traceService.trace('DebugActionsService', 'status polling stopped')
    }
  }

  /**
   * Cleanup - stop polling and clear subscribers
   */
  destroy(): void {
    this.stopStatusPolling()
    this.subscribers.clear()
    this.statusSubscribers.clear()

    // traceService.trace('DebugActionsService', 'service destroyed')
  }

  /**
   * Get service status
   */
  getStatus(): {
    actionCount: number
    historyCount: number
    subscriberCount: number
    statusSubscriberCount: number
    isLoading: boolean
    runningActions: number
  } {
    return {
      actionCount: this.actions.length,
      historyCount: this.history.length,
      subscriberCount: this.subscribers.size,
      statusSubscriberCount: this.statusSubscribers.size,
      isLoading: this.isLoading,
      runningActions: Object.values(this.actionStatus).filter(s => s === 'running').length
    }
  }
}

// Export singleton instance
export const debugActionsService = new DebugActionsService()
