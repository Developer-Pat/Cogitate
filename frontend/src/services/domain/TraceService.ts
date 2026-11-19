/**
 * TraceService - Flow tracing with sequence numbers and tags
 *
 * Minimal footprint tracing for debugging complex flows.
 * Each trace gets a unique sequence number for ordering.
 * Uses both Date.now() for absolute time and performance.now() for high-precision delta timing.
 *
 * Usage:
 // *   traceService.trace('ChatFlow', 'sendMessage', { contentLength: 100 }, ['lifecycle', 'user-action'])
 *
 * All traces are logged with [FLOW TRACE #N] prefix for easy filtering.
 */

import { frontendLoggingService } from '../frontendLoggingService'
import { loggingConfigService } from './LoggingConfigService'

export interface TraceContext {
  [key: string]: unknown
}

export type TraceTag =
  | 'lifecycle'
  | 'data'
  | 'api-call'
  | 'streaming'
  | 'error'
  | 'performance'
  | 'user-action'
  | 'state-change'
  | 'validation'
  | 'cache'
  | 'sync'

class TraceService {
  private sequence: number = 0
  private flowCounter: Map<string, number> = new Map()
  private startTime: number = 0

  constructor() {
    // Capture the start time for delta calculations
    this.startTime = typeof performance !== 'undefined' ? performance.now() : Date.now()
  }

  /**
   * Get next global sequence number
   */
  private getNextSequence(): number {
    return ++this.sequence
  }

  /**
   * Get counter for specific flow
   */
  private getFlowCounter(flow: string): number {
    const current = this.flowCounter.get(flow) || 0
    const next = current + 1
    this.flowCounter.set(flow, next)
    return next
  }

  /**
   * Get high-precision timestamp
   * @returns Object with both absolute and relative timestamps
   */
  private getTimestamps(): { absolute: number; relative: number } {
    const absolute = Date.now()
    const relative = typeof performance !== 'undefined' ? performance.now() - this.startTime : 0
    return { absolute, relative }
  }

  /**
   * Trace a flow event
   *
   * @param flow - Flow name (e.g., 'ChatFlow')
   * @param step - Step name (e.g., 'sendMessage')
   * @param context - Optional context data
   * @param tags - Optional tags for filtering (e.g., ['lifecycle', 'user-action'])
   */
  trace(flow: string, step: string, context: TraceContext = {}, tags: TraceTag[] = []): void {
    // Check if tracing is enabled at all
    if (!loggingConfigService.isTracingEnabled()) {
      return
    }

    // Check if should log based on config
    if (!loggingConfigService.shouldLog('FlowTrace', 'info')) {
      return
    }

    const traceId = `${flow}-${this.getFlowCounter(flow)}`
    const sequence = this.getNextSequence()
    const { absolute, relative } = this.getTimestamps()

    frontendLoggingService.info('FlowTrace', `[FLOW TRACE #${sequence}] ${flow}:${step}`, {
      traceId,
      sequence,
      flow,
      step,
      timestamp: absolute,
      perfTime: relative,  // High-precision time since service start (ms)
      tags,
      ...context
    })
  }

  /**
   * Reset counters (for testing)
   */
  reset(): void {
    this.sequence = 0
    this.flowCounter.clear()
    this.startTime = typeof performance !== 'undefined' ? performance.now() : Date.now()
  }
}

// Export singleton instance
export const traceService = new TraceService()
