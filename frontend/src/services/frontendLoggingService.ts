import type { LogEntry, ApiResponse } from '../types'
import { globalLogStore } from './logStoreInstance'
import { logsService } from './logsService'
import { loggingConfigService } from './domain/LoggingConfigService'

// Global flag to prevent error spam
declare global {
  interface Window {
    __cogitateBackendLogErrorShown?: boolean
  }
}

/**
 * Log levels for frontend logging
 */

// LOCAL-TIME STAMP (2026-09-06): the log files (app.log via the backend
// logger, the test-spread helper) all stamp LOCAL time — the frontend
// writer was the lone UTC one (toISOString), so its rows read 5 hours in
// the future and mis-sorted against the backend rows in the merged feed.
function localStamp(): string {
  const d = new Date()
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}
export type LogLevel = 'debug' | 'info' | 'warning' | 'error' | 'critical'

// ── THE TRANSPORT (2026-09-12, the log flood's third cause) ───────────────
// Every log row used to be its own POST, raced against a 3-second timeout. In
// the 2026-09-11 incident 2148 of the last 3000 HTTP requests were
// POST /api/v1/logs/frontend — 72% of all traffic — against 14 chat streams.
// The level floor cut the VOLUME; this fixes the SHAPE, which is
// what let a chatty logger starve the stream it was supposed to help debug.
//
// Rows queue and ship in batches through /logs/frontend/batch — an endpoint
// that has existed all along and was never called. Flush on whichever comes
// first: 50 rows, or 2 seconds. Payloads go to sendBatchLogsToBackend DIRECTLY
// rather than sendBatchLogs, because the latter also writes the in-memory
// store and sendLog has already done that — using it would double-count.
const BACKEND_QUEUE_MAX = 50
const BACKEND_FLUSH_MS = 2000

type BackendLogPayload = {
  timestamp: string
  level: string
  source: string
  message: string
  context?: Record<string, unknown>
  user_agent?: string
  url?: string
  session_id?: string
}

let backendQueue: BackendLogPayload[] = []
let backendFlushTimer: ReturnType<typeof setTimeout> | null = null

/** Queue a row for the backend. Never throws — logging must not break a caller. */
export function enqueueForBackend(entry: BackendLogPayload): void {
  try {
    if (!loggingConfigService.isBackendLoggingEnabled()) return
    backendQueue.push(entry)
    if (backendQueue.length >= BACKEND_QUEUE_MAX) {
      void flushBackendQueue()
      return
    }
    if (backendFlushTimer === null) {
      backendFlushTimer = setTimeout(() => {
        void flushBackendQueue()
      }, BACKEND_FLUSH_MS)
    }
  } catch {
    // best-effort; the in-memory store already has the row
  }
}

/** Ship whatever is queued. Exported so a page-hide or a test can force it. */
export async function flushBackendQueue(): Promise<void> {
  if (backendFlushTimer !== null) {
    clearTimeout(backendFlushTimer)
    backendFlushTimer = null
  }
  if (backendQueue.length === 0) return
  const batch = backendQueue
  backendQueue = []
  try {
    await (logsService.sendBatchLogsToBackend as unknown as (
      logs: BackendLogPayload[],
    ) => Promise<unknown>)(batch)
  } catch {
    // Silently ignore: backend logging is best-effort, localStorage is the
    // reliable store (the service's own contract).
  }
}

// Don't lose the tail when the tab goes away — and a hidden tab is exactly
// when the queue would otherwise sit unflushed.
if (typeof window !== 'undefined') {
  window.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') void flushBackendQueue()
  })
  window.addEventListener('beforeunload', () => {
    void flushBackendQueue()
  })
}



// ── THE LOG FLOOD GATE (2026-09-11, the streaming-performance incident) ──
// Every debug() call shipped a POST to /api/v1/logs/frontend, and the
// streaming path logs on EVERY chunk callback — two rows per update,
// thousands per turn. The backend spent its time appending to a log file
// that had reached 164 MB, so the stream starved, the UI crawled, and turns
// ended on the empty-message guard ("Bob keeps dying"). Measured: 2148 of
// the last 3000 HTTP requests were POST /logs/frontend — 72% of all traffic.
//
// The service's own rate limiter was COMMENTED OUT with the note "DISABLE
// RATE LIMITING FOR DEBUGGING - ALL LOGS SHOULD BE VISIBLE" and never
// restored. This floor is the second lock on the same door: debug rows are
// development noise, not diagnosis. Raise MIN_LOG_LEVEL to 'warning' if the
// volume ever matters again.
const LOG_RANK: Record<LogLevel, number> = {
  debug: 10, info: 20, warning: 30, error: 40, critical: 50,
}
export const MIN_LOG_LEVEL: LogLevel = 'info'
const MIN_LOG_RANK = LOG_RANK[MIN_LOG_LEVEL]

/**
 * Frontend log entry structure
 */
export interface FrontendLogEntry {
  timestamp: string
  level: LogLevel
  source: string
  message: string
  context?: Record<string, unknown>
  userAgent?: string
  url?: string
  sessionId?: string
  traceId?: string
}

/**
 * Rate limiting configuration
 */
interface RateLimitConfig {
  maxLogsPerSecond: number        // Max logs per second before throttling
  maxIdenticalLogs: number        // Max identical logs before deduplication
  windowMs: number                // Time window for rate limiting (ms)
  dedupeWindowMs: number          // Time window for deduplication (ms)
}

const DEFAULT_RATE_LIMIT: RateLimitConfig = {
  maxLogsPerSecond: 10,
  maxIdenticalLogs: 3,
  windowMs: 1000,
  dedupeWindowMs: 5000
}

/**
 * Rate limiting state
 */
interface RateLimitState {
  recentLogs: number[]                    // Timestamps of recent logs
  identicalCounts: Map<string, {count: number, lastTime: number, suppressed: boolean}>
  suppressionWarnings: Set<string>        // Track which suppressions we've warned about
}

const rateLimitState: RateLimitState = {
  recentLogs: [],
  identicalCounts: new Map(),
  suppressionWarnings: new Set()
}

/**
 * The dedupe key: same source + same message is the same row.
 */
function getLogKey(entry: FrontendLogEntry): string {
  return `${entry.source}::${entry.message}`
}

/**
 * Should this row go out? RESTORED 2026-09-12 — the companion functions were
 * deleted when the call site was commented out, so this is a reimplementation
 * against the existing DEFAULT_RATE_LIMIT config, not an uncomment.
 *
 * It enforces ONLY the identical-repetition rule (maxIdenticalLogs within
 * dedupeWindowMs). The config's other half — maxLogsPerSecond — is deliberately
 * NOT enforced here any more: it suppresses DISTINCT rows during a burst, and
 * that is precisely the "ALL LOGS SHOULD BE VISIBLE" complaint that got the
 * limiter disabled in the first place. A burst of distinct rows is no longer a
 * problem since the transport batches them, so enforcing it would now be a pure
 * loss. `recentLogs` is kept ticking for the summary, not for a gate.
 *
 * What this DOES catch is the pattern that actually hurt: thousands of
 * IDENTICAL rows from one call site. The flood's worst offender, "Calling
 * updateMessage" on every chunk, was exactly that.
 */
function shouldSendLog(entry: FrontendLogEntry): { allowed: boolean; count: number } {
  const now = Date.now()
  const key = getLogKey(entry)

  const seen = rateLimitState.identicalCounts.get(key)
  if (seen && now - seen.lastTime > DEFAULT_RATE_LIMIT.dedupeWindowMs) {
    rateLimitState.identicalCounts.delete(key) // the window expired
  }

  const current = rateLimitState.identicalCounts.get(key) ?? {
    count: 0,
    lastTime: now,
    suppressed: false,
  }
  current.count += 1
  current.lastTime = now
  rateLimitState.identicalCounts.set(key, current)

  // keep the activity window ticking (inspectable, not a gate)
  rateLimitState.recentLogs = rateLimitState.recentLogs.filter(
    (t) => now - t < DEFAULT_RATE_LIMIT.windowMs,
  )
  rateLimitState.recentLogs.push(now)

  if (current.count > DEFAULT_RATE_LIMIT.maxIdenticalLogs) {
    current.suppressed = true
    return { allowed: false, count: current.count }
  }
  return { allowed: true, count: current.count }
}

/**
 * Get suppression summary for debugging
 */
export function getLogSuppressionSummary(): Record<string, number> {
  const summary: Record<string, number> = {}
  rateLimitState.identicalCounts.forEach((data, key) => {
    if (data.suppressed || data.count > DEFAULT_RATE_LIMIT.maxIdenticalLogs) {
      summary[key] = data.count
    }
  })
  return summary
}

/**
 * Frontend Logging Service
 * Captures frontend errors, interactions, and timing issues
 * Sends them to backend for persistent storage while maintaining
 * in-memory store as cache/fallback
 */
export const frontendLoggingService = {
  /**
   * Send a log entry to backend and in-memory store
   * Includes rate limiting and deduplication to prevent log flooding
   */
  async sendLog(entry: FrontendLogEntry, options?: {skipRateLimit?: boolean}) {
    // THE FLOOR (2026-09-11): one gate at the single funnel, so every caller
    // — present and future — is covered rather than each method needing to
    // remember. Critical paths can still bypass by calling sendLog directly
    // with a level at or above the floor.
    if (LOG_RANK[entry.level] < MIN_LOG_RANK) {
      return {
        data: { id: 'below-level' },
        status: 200,
        timestamp: localStamp(),
      }
    }

    // THE RATE LIMITER — RESTORED 2026-09-12.
    // It was commented out with "DISABLE RATE LIMITING FOR DEBUGGING - ALL LOGS
    // SHOULD BE VISIBLE" and never put back: the 18-day-gap shape, a diagnostic
    // left switched on. It also could not have worked as written — the parameter
    // is `_options` and the block referenced `options`, so uncommenting it alone
    // would have thrown. Renamed to `options` and restored.
    //
    // It is NOT redundant with the two fixes above. Three different jobs:
    //   the FLOOR  cuts a LEVEL       — debug volume
    //   the QUEUE  cuts the REQUESTS  — transport shape
    //   this limiter cuts REPETITION  — the same row, again and again
    // The flood's worst offender, "Calling updateMessage" logged on every chunk,
    // was thousands of IDENTICAL rows: exactly what maxIdenticalLogs (3) exists
    // for. Neither the floor nor the queue would have touched it.
    //
    // The original objection — "ALL LOGS SHOULD BE VISIBLE" — was fair: a
    // suppressor that hides rows silently IS a silent failure. So the warning
    // stays console.warn (never sendLog — that would recurse into itself), and
    // getLogSuppressionSummary() is exported so the count stays inspectable.
    if (!options?.skipRateLimit) {
      const check = shouldSendLog(entry)
      if (!check.allowed) {
        // One warning per unique message, not per suppression.
        if (!rateLimitState.suppressionWarnings.has(getLogKey(entry))) {
          console.warn(
            `[LogRateLimit] Suppressing repeated log: ${entry.source} - ${entry.message}`,
          )
          rateLimitState.suppressionWarnings.add(getLogKey(entry))
        }
        return {
          data: { id: 'suppressed', suppressedCount: check.count },
          status: 200,
          timestamp: localStamp(),
        }
      }
    }

    try {
      // Sanitize context to prevent circular references and oversized data
      const sanitizeContext = (ctx?: Record<string, unknown>): Record<string, unknown> => {
        if (!ctx) return {}
        try {
          // Limit context size and remove problematic values
          const sanitized: Record<string, unknown> = {}
          for (const [key, value] of Object.entries(ctx)) {
            if (value === undefined || typeof value === 'function') continue
            // Stringify objects but limit size
            if (typeof value === 'object' && value !== null) {
              const str = JSON.stringify(value)
              if (str && str.length < 1000) {
                sanitized[key] = value
              }
            } else {
              sanitized[key] = value
            }
          }
          return sanitized
        } catch {
          return {}
        }
      }

      // Create log entry with browser context
      const logEntry: LogEntry = {
        id: '', // Will be replaced by backend ID
        timestamp: entry.timestamp || localStamp(),
        level: entry.level,
        source: entry.source,
        message: entry.message,
        context: sanitizeContext({
          ...entry.context,
          userAgent: entry.userAgent || navigator.userAgent,
          url: entry.url || window.location.href
        })
      }

      // Add to in-memory store immediately (for instant UI update)
      globalLogStore.addLog(logEntry)

      // Send to the backend through the QUEUE (see enqueueForBackend).
      // This was one POST per row, raced against a 3-second timeout — the
      // transport shape behind the 2026-09-11 flood. The in-memory store
      // above already ran, so the UI is instant regardless.
      enqueueForBackend({
        timestamp: logEntry.timestamp,
        level: logEntry.level,
        source: logEntry.source,
        message: logEntry.message,
        context: logEntry.context,
        user_agent: logEntry.context?.userAgent as string | undefined,
        url: logEntry.context?.url as string | undefined,
        session_id: entry.sessionId
      });

      return {
        data: { id: logEntry.id },
        status: 200,
        timestamp: new Date().toISOString()
      }
    } catch {
      return {
        data: { id: 'local-' + Date.now() },
        status: 500,
        timestamp: localStamp(),
        error: {
          code: 'logging_service_error',
          message: 'Failed to log entry'
        }
      }
    }
  },

  /**
   * Send batch logs to backend and in-memory store
   */
  async sendBatchLogs(entries: FrontendLogEntry[]) {
    try {
      let count = 0
      const backendEntries: Array<{
        timestamp: string
        level: string
        source: string
        message: string
        context?: Record<string, unknown>
        user_agent?: string
        url?: string
        session_id?: string
        trace_id?: string
      }> = []

      for (const entry of entries) {
        const logEntry: LogEntry = {
          id: '',
          timestamp: entry.timestamp || new Date().toISOString(),
          level: entry.level,
          source: entry.source,
          message: entry.message,
          context: {
            ...entry.context,
            userAgent: entry.userAgent || navigator.userAgent,
            url: entry.url || window.location.href
          }
        }
        globalLogStore.addLog(logEntry)
        count++

        backendEntries.push({
          timestamp: logEntry.timestamp,
          level: logEntry.level,
          source: logEntry.source,
          message: logEntry.message,
          context: logEntry.context,
          user_agent: logEntry.context?.userAgent as string | undefined,
          url: logEntry.context?.url as string | undefined,
          session_id: entry.sessionId
        })
      }

      // Send batch to backend asynchronously
      (logsService.sendBatchLogsToBackend as (logs: Array<{
        timestamp: string;
        level: string;
        source: string;
        message: string;
        context?: Record<string, unknown>;
        user_agent?: string;
        url?: string;
        session_id?: string;
      }>) => Promise<ApiResponse<{ sent: number; failed: number }>>)?.(backendEntries.map(e => ({
        ...e,
        user_agent: e.user_agent as string | undefined,
        url: e.url as string | undefined
      }))).catch((err: unknown) =>
        console.error('Failed to send batch logs to backend:', err)
      )

      return {
        data: { count },
        status: 200,
        timestamp: new Date().toISOString()
      }
    } catch (error) {
      console.error('Failed to log batch entries:', error)
      return {
        data: { count: 0 },
        status: 500,
        timestamp: localStamp(),
        error: {
          code: 'logging_service_error',
          message: 'Failed to log batch entries'
        }
      }
    }
  },

  /**
   * Log a debug message (rate-limited)
   */
  debug(source: string, message: string, context?: Record<string, unknown>) {
    this.sendLog({
      timestamp: new Date().toISOString(),
      level: 'debug',
      source,
      message,
      context
    }).catch(err => console.error('Failed to log debug:', err))
  },

  /**
   * Log an info message (rate-limited)
   */
  info(source: string, message: string, context?: Record<string, unknown>) {
    this.sendLog({
      timestamp: new Date().toISOString(),
      level: 'info',
      source,
      message,
      context
    }).catch(err => console.error('Failed to log info:', err))
  },

  /**
   * Log a warning message (rate-limited)
   */
  warning(source: string, message: string, context?: Record<string, unknown>) {
    this.sendLog({
      timestamp: new Date().toISOString(),
      level: 'warning',
      source,
      message,
      context
    }).catch(err => console.error('Failed to log warning:', err))
  },

  /** The warn alias (the FirstRunRedirect's usage — 2026-08-25). */
  warn(source: string, message: string, context?: Record<string, unknown>) {
    return this.warning(source, message, context)
  },

  /**
   * Log an error message with stack trace (NOT rate-limited)
   */
  error(source: string, message: string, error?: Error | unknown, context?: Record<string, unknown>) {
    const errorContext = {
      ...context,
      errorMessage: error instanceof Error ? error.message : String(error),
      errorStack: error instanceof Error ? error.stack : undefined
    }

    this.sendLog({
      timestamp: new Date().toISOString(),
      level: 'error',
      source,
      message,
      context: errorContext
    }, {skipRateLimit: true}).catch(err => console.error('Failed to log error:', err))
  },

  /**
   * Log a critical error (NOT rate-limited)
   */
  critical(source: string, message: string, error?: Error | unknown, context?: Record<string, unknown>) {
    const errorContext = {
      ...context,
      errorMessage: error instanceof Error ? error.message : String(error),
      errorStack: error instanceof Error ? error.stack : undefined
    }

    this.sendLog({
      timestamp: new Date().toISOString(),
      level: 'critical',
      source,
      message,
      context: errorContext
    }, {skipRateLimit: true}).catch(err => console.error('Failed to log critical:', err))
  },

  /**
   * Log message sync timing and issues
   */
  logMessageSync(
    sessionId: string,
    messageId: string,
    role: 'user' | 'assistant',
    status: 'started' | 'success' | 'failed' | 'retry',
    duration?: number,
    error?: Error | unknown
  ) {
    const context: Record<string, unknown> = {
      sessionId,
      messageId,
      role,
      status,
      duration
    }

    if (error) {
      context.errorMessage = error instanceof Error ? error.message : String(error)
      context.errorStack = error instanceof Error ? error.stack : undefined
    }

    const level = status === 'failed' ? 'error' : status === 'retry' ? 'warning' : 'info'
    const message = `Message sync ${status}: ${role} message ${messageId}`

    this.sendLog({
      timestamp: new Date().toISOString(),
      level,
      source: 'MessageSync',
      message,
      context
    }).catch(err => console.error('Failed to log message sync:', err))
  },

  /**
   * Log streaming performance metrics
   */
  logStreamingMetrics(
    sessionId: string,
    messageId: string,
    metrics: {
      totalCharacters: number
      totalStreamTime: number
      charactersPerSecond: number
      estimatedTokensPerSecond: number
      timeToFirstChunk?: number
    }
  ) {
    this.sendLog({
      timestamp: new Date().toISOString(),
      level: 'info',
      source: 'StreamingPerformance',
      message: `Streaming completed for message ${messageId}`,
      context: {
        sessionId,
        messageId,
        ...metrics
      }
    }).catch(err => console.error('Failed to log streaming metrics:', err))
  },

  /**
   * Log state update timing issues
   */
  logStateUpdateTiming(
    source: string,
    operation: string,
    duration: number,
    context?: Record<string, unknown>
  ) {
    const level = duration > 1000 ? 'warning' : 'info'
    this.sendLog({
      timestamp: new Date().toISOString(),
      level,
      source: `StateUpdate:${source}`,
      message: `${operation} took ${duration}ms`,
      context: {
        duration,
        ...context
      }
    }).catch(err => console.error('Failed to log state update timing:', err))
  }
}

