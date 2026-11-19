/**
 * HistoryService - Log analysis for historical insights
 *
 * Philosophy:
 * - History is derived from logs (single source of truth)
 * - No Zustand store dependency (pure log analysis)
 * - No persistence initially (compute on-demand)
 * - Pure function: logs → insights
 */

import { logsService } from '../logsService'
import { sessionsService } from './SessionsService'

import type { LogEntry, LogFilter } from '@/types'

/**
 * Format date for backend API compatibility
 * Python's fromisoformat() works best with ISO format without milliseconds
 */
function formatDateTimeForBackend(date: Date): string {
  // Convert to ISO string, remove milliseconds, replace 'Z' with '+00:00'
  return date.toISOString().replace(/\.\d{3}Z$/, '+00:00')
}

/**
 * Log histogram entry - frequency analysis of log messages
 */
export interface LogHistogram {
  message: string
  count: number
  firstSeen: Date
  lastSeen: Date
  sources: string[]
  levels: string[]
}

/**
 * Time range for filtering logs
 */
export interface TimeRange {
  from: Date
  to: Date
}

/**
 * Options for histogram generation
 */
export interface HistogramOptions {
  /** Time range to filter logs */
  timeRange?: TimeRange
  /** Minimum count threshold (filter out rare messages) */
  minCount?: number
  /** Group similar messages by pattern (future feature) */
  groupSimilar?: boolean
}

/**
 * Issue report - detected problems in logs
 */
export interface IssueReport {
  frequentErrors: LogHistogram[]
  spikes: LogHistogram[]
  timestamp: Date
}

/**
 * Message performance metrics
 */
export interface MessagePerformance {
  averageTokenCount: number
  averageDurationMs: number
  averageTokensPerSecond: number
  totalMessages: number
  fastestProvider: string
  fastestModel: string
}

/**
 * Message length distribution
 */
export interface MessageLengthDistribution {
  short: number      // < 100 chars
  medium: number     // 100-500 chars
  long: number       // 500-1000 chars
  veryLong: number   // > 1000 chars
}

/**
 * Provider/model performance stats
 */
export interface ProviderStats {
  provider: string
  model?: string
  messageCount: number
  avgTokenCount: number
  avgDurationMs: number
  avgTokensPerSecond: number
}

/**
 * Message analysis result
 */
export interface MessageAnalysis {
  performance: MessagePerformance
  distribution: MessageLengthDistribution
  providerStats: ProviderStats[]
  timeRange?: TimeRange
}

/**
 * Session analysis summary
 */
export interface SessionAnalysisSummary {
  sessionId: string
  title: string
  agentId: string
  messageCount: number
  totalTokens: number
  avgResponseTimeMs: number
  avgTokensPerSecond: number
  createdAt: Date
  updatedAt: Date
  duration: number // ms from first to last message
}

/**
 * Session analysis result
 */
export interface SessionAnalysisResult {
  sessions: SessionAnalysisSummary[]
  totalSessions: number
  totalMessages: number
  totalTokens: number
  avgMessagesPerSession: number
  avgTokensPerSession: number
  avgSessionDurationMs: number
  limit: number
}

class HistoryService {
  /**
   * Generate histogram of log message frequencies
   *
   * @param options - Filtering and grouping options
   * @returns Array of message counts, sorted by frequency
   */
  async getLogsHistogram(options?: HistogramOptions): Promise<LogHistogram[]> {
    // Fetch logs from backend
    const filters: LogFilter = {}

    if (options?.timeRange) {
      // Format dates for backend compatibility (Python fromisoformat)
      filters.from = formatDateTimeForBackend(options.timeRange.from)
      filters.to = formatDateTimeForBackend(options.timeRange.to)
    }

    // Get logs (page_size limited to 100 by backend, so fetch multiple pages if needed)
    const response = await logsService.getLogs(filters, 1, 100)
    const logs = response.data?.data || []

    // Group by message
    const histogram = new Map<string, LogHistogram>()

    for (const log of logs) {
      const message = log.message
      if (!histogram.has(message)) {
        histogram.set(message, {
          message,
          count: 0,
          firstSeen: new Date(log.timestamp),
          lastSeen: new Date(log.timestamp),
          sources: [],
          levels: []
        })
      }

      const entry = histogram.get(message)!
      entry.count++

      const logTime = new Date(log.timestamp)
      if (logTime < entry.firstSeen) {
        entry.firstSeen = logTime
      }
      if (logTime > entry.lastSeen) {
        entry.lastSeen = logTime
      }

      if (log.source && !entry.sources.includes(log.source)) {
        entry.sources.push(log.source)
      }
      if (log.level && !entry.levels.includes(log.level)) {
        entry.levels.push(log.level)
      }
    }

    // Convert to array, filter by minCount, and sort by frequency
    const result = Array.from(histogram.values())
      .filter(h => h.count >= (options?.minCount || 1))
      .sort((a, b) => b.count - a.count)

    return result
  }

  /**
   * Get most frequent log messages
   *
   * @param limit - Maximum number of messages to return
   * @returns Top messages by frequency
   */
  async getTopMessages(limit: number = 20): Promise<LogHistogram[]> {
    const histogram = await this.getLogsHistogram()
    return histogram.slice(0, limit)
  }

  /**
   * Get logs within a specific time range
   *
   * @param timeRange - Time range to fetch logs for
   * @returns Array of log entries
   */
  async getLogsByTimeRange(timeRange: TimeRange): Promise<LogEntry[]> {
    const filters: LogFilter = {
      from: formatDateTimeForBackend(timeRange.from),
      to: formatDateTimeForBackend(timeRange.to)
    }

    const response = await logsService.getLogs(filters, 1, 100)
    return response.data?.data || []
  }

  /**
   * Detect potential issues (high frequency errors)
   */
  async detectIssues(): Promise<IssueReport> {
    const histogram = await this.getLogsHistogram()

    // Find errors that occur frequently
    const frequentErrors = histogram.filter(
      h => h.levels.includes('error') || h.levels.includes('critical')
    )

    // Find messages with sudden spikes (messages that occur much more frequently than average)
    const spikes = this.detectSpikes(histogram)

    return {
      frequentErrors,
      spikes,
      timestamp: new Date()
    }
  }

  /**
   * Detect spikes in log frequency
   * Simple heuristic: messages with count > 2x average are considered spikes
   */
  private detectSpikes(histogram: LogHistogram[]): LogHistogram[] {
    if (histogram.length === 0) return []

    const avgCount = histogram.reduce((sum, h) => sum + h.count, 0) / histogram.length
    const spikeThreshold = avgCount * 2

    return histogram.filter(h => h.count > spikeThreshold)
  }

  /**
   * Get log statistics
   */
  async getStats(timeRange?: TimeRange): Promise<{
    totalLogs: number
    uniqueMessages: number
    errorCount: number
    warningCount: number
    topSources: { source: string; count: number }[]
  }> {
    const filters: LogFilter = {}
    if (timeRange) {
      filters.from = formatDateTimeForBackend(timeRange.from)
      filters.to = formatDateTimeForBackend(timeRange.to)
    }

    const response = await logsService.getLogs(filters, 1, 100)
    const logs = response.data?.data || []

    const messageSet = new Set<string>()
    const sourceCounts = new Map<string, number>()
    let errorCount = 0
    let warningCount = 0

    for (const log of logs) {
      messageSet.add(log.message)

      if (log.source) {
        sourceCounts.set(log.source, (sourceCounts.get(log.source) || 0) + 1)
      }

      if (log.level === 'error' || log.level === 'critical') {
        errorCount++
      } else if (log.level === 'warning') {
        warningCount++
      }
    }

    const topSources = Array.from(sourceCounts.entries())
      .map(([source, count]) => ({ source, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10)

    return {
      totalLogs: logs.length,
      uniqueMessages: messageSet.size,
      errorCount,
      warningCount,
      topSources
    }
  }

  /**
   * Analyze message performance from database messages
   *
   * Extracts message metadata from sessions to calculate:
   * - Average token count
   * - Average duration
   * - Tokens per second
   * - Fastest provider/model
   *
   * Uses SessionsService cache (database data, not logs)
   *
   * @param timeRange - Optional time range to filter messages
   * @returns Message performance metrics
   */
  async getMessagePerformance(timeRange?: TimeRange): Promise<MessagePerformance> {
    // traceService.trace('HistoryService', 'getMessagePerformance started', {
      // timeRange: timeRange ? `${timeRange.from.toISOString()} - ${timeRange.to.toISOString()}` : 'all time'
    // })

    // Get sessions from cache (database data)
    const sessions = sessionsService.getSessions()

    // traceService.trace('HistoryService', 'getMessagePerformance: sessions loaded', {
      // totalSessions: sessions.length
    // })

    // Extract all messages with metadata from sessions
    const allMessages = sessions.flatMap(s => s.messages || [])
    
    // Filter by time range if provided
    const messages = timeRange
      ? allMessages.filter(m => {
          const msgTime = new Date(m.timestamp).getTime()
          return msgTime >= timeRange.from.getTime() && msgTime <= timeRange.to.getTime()
        })
      : allMessages

    // Filter for assistant messages with metadata
    const assistantMessages = messages.filter(m => 
      m.role === 'assistant' && m.metadata && (m.metadata.tokenCount || m.metadata.totalTimeMs)
    )

    // traceService.trace('HistoryService', 'getMessagePerformance: message filtering', {
      // totalMessages: allMessages.length,
      // filteredByTime: messages.length,
      // assistantMessagesWithMetadata: assistantMessages.length
    // })

    // Extract metrics from message metadata
    const tokenCounts: number[] = []
    const durations: number[] = []
    const tokensPerSecond: number[] = []
    const providerSpeeds = new Map<string, number[]>()
    const modelSpeeds = new Map<string, number[]>()

    for (const msg of assistantMessages) {
      const metadata = msg.metadata || {}

      // traceService.trace('HistoryService', 'processing message metadata', {
        // messageId: msg.id,
        // hasTokenCount: !!metadata.tokenCount,
        // hasTotalTimeMs: !!metadata.totalTimeMs,
        // hasTokensPerSecond: !!metadata.tokensPerSecond,
        // provider: metadata.provider,
        // model: metadata.model
      // })

      // Extract token count
      if (metadata.tokenCount && typeof metadata.tokenCount === 'number') {
        tokenCounts.push(metadata.tokenCount)
      }

      // Extract duration
      if (metadata.totalTimeMs && typeof metadata.totalTimeMs === 'number') {
        durations.push(metadata.totalTimeMs)
      }

      // Extract tokens per second
      if (metadata.tokensPerSecond && typeof metadata.tokensPerSecond === 'number') {
        tokensPerSecond.push(metadata.tokensPerSecond)
      }

      // Track provider speeds
      if (metadata.provider && typeof metadata.provider === 'string' && metadata.tokensPerSecond) {
        if (!providerSpeeds.has(metadata.provider)) {
          providerSpeeds.set(metadata.provider, [])
        }
        providerSpeeds.get(metadata.provider)!.push(metadata.tokensPerSecond)
      }

      // Track model speeds
      if (metadata.model && typeof metadata.model === 'string' && metadata.tokensPerSecond) {
        if (!modelSpeeds.has(metadata.model)) {
          modelSpeeds.set(metadata.model, [])
        }
        modelSpeeds.get(metadata.model)!.push(metadata.tokensPerSecond)
      }
    }

    // traceService.trace('HistoryService', 'getMessagePerformance: extracted metrics', {
      // tokenCountsCount: tokenCounts.length,
      // durationsCount: durations.length,
      // tokensPerSecondCount: tokensPerSecond.length,
      // providerSpeedsCount: providerSpeeds.size,
      // modelSpeedsCount: modelSpeeds.size
    // })

    // Calculate averages
    const avg = (arr: number[]) => arr.length > 0 ? arr.reduce((a, b) => a + b, 0) / arr.length : 0

    const averageTokenCount = Math.round(avg(tokenCounts))
    const averageDurationMs = Math.round(avg(durations))
    const averageTokensPerSecond = Math.round(avg(tokensPerSecond) * 10) / 10

    // Find fastest provider
    let fastestProvider = ''
    let fastestProviderSpeed = 0
    providerSpeeds.forEach((speeds, provider) => {
      const avgSpeed = avg(speeds)
      if (avgSpeed > fastestProviderSpeed) {
        fastestProviderSpeed = avgSpeed
        fastestProvider = provider
      }
    })

    // Find fastest model
    let fastestModel = ''
    let fastestModelSpeed = 0
    modelSpeeds.forEach((speeds, model) => {
      const avgSpeed = avg(speeds)
      if (avgSpeed > fastestModelSpeed) {
        fastestModelSpeed = avgSpeed
        fastestModel = model
      }
    })

    return {
      averageTokenCount,
      averageDurationMs,
      averageTokensPerSecond,
      totalMessages: assistantMessages.length,
      fastestProvider,
      fastestModel
    }
  }

  /**
   * Analyze message length distribution from database messages
   *
   * Categorizes messages by content length:
   * - Short: < 100 characters
   * - Medium: 100-500 characters
   * - Long: 500-1000 characters
   * - Very Long: > 1000 characters
   *
   * Uses SessionsService cache (database data, not logs)
   *
   * @param timeRange - Optional time range to filter messages
   * @returns Message length distribution
   */
  async getMessageLengthDistribution(timeRange?: TimeRange): Promise<MessageLengthDistribution> {
    // traceService.trace('HistoryService', 'getMessageLengthDistribution started', {
      // timeRange: timeRange ? `${timeRange.from.toISOString()} - ${timeRange.to.toISOString()}` : 'all time'
    // })

    // Get sessions from cache (database data)
    const sessions = sessionsService.getSessions()

    // traceService.trace('HistoryService', 'getMessageLengthDistribution: sessions loaded', {
      // totalSessions: sessions.length
    // })

    // Extract all messages from sessions
    const allMessages = sessions.flatMap(s => s.messages || [])
    
    // Filter by time range if provided
    const messages = timeRange
      ? allMessages.filter(m => {
          const msgTime = new Date(m.timestamp).getTime()
          return msgTime >= timeRange.from.getTime() && msgTime <= timeRange.to.getTime()
        })
      : allMessages

    // Filter for assistant messages with content
    const assistantMessages = messages.filter(m => 
      m.role === 'assistant' && m.content
    )

    // traceService.trace('HistoryService', 'getMessageLengthDistribution: message filtering', {
      // totalMessages: allMessages.length,
      // filteredByTime: messages.length,
      // assistantMessagesWithContent: assistantMessages.length
    // })

    const distribution: MessageLengthDistribution = {
      short: 0,
      medium: 0,
      long: 0,
      veryLong: 0
    }

    for (const msg of assistantMessages) {
      const charCount = msg.content.length

      // traceService.trace('HistoryService', 'processing message length', {
        // messageId: msg.id,
        // charCount,
        // contentPreview: msg.content.substring(0, 50)
      // })

      if (charCount < 100) {
        distribution.short++
      } else if (charCount < 500) {
        distribution.medium++
      } else if (charCount < 1000) {
        distribution.long++
      } else {
        distribution.veryLong++
      }
    }

    // traceService.trace('HistoryService', 'getMessageLengthDistribution: result', {
      // distribution,
      // totalMessages: assistantMessages.length
    // })

    return distribution
  }

  /**
   * Analyze provider and model performance from database messages
   *
   * Groups messages by provider and model to calculate:
   * - Message count per provider/model
   * - Average token count
   * - Average duration
   * - Average tokens per second
   *
   * Uses SessionsService cache (database data, not logs)
   *
   * @param timeRange - Optional time range to filter messages
   * @returns Array of provider/model statistics
   */
  async getProviderModelStats(timeRange?: TimeRange): Promise<ProviderStats[]> {
    // traceService.trace('HistoryService', 'getProviderModelStats started', {
      // timeRange: timeRange ? `${timeRange.from.toISOString()} - ${timeRange.to.toISOString()}` : 'all time'
    // })

    // Get sessions from cache (database data)
    const sessions = sessionsService.getSessions()

    // traceService.trace('HistoryService', 'getProviderModelStats: sessions loaded', {
      // totalSessions: sessions.length
    // })

    // Extract all messages from sessions
    const allMessages = sessions.flatMap(s => s.messages || [])
    
    // Filter by time range if provided
    const messages = timeRange
      ? allMessages.filter(m => {
          const msgTime = new Date(m.timestamp).getTime()
          return msgTime >= timeRange.from.getTime() && msgTime <= timeRange.to.getTime()
        })
      : allMessages

    // Filter for assistant messages with metadata
    const assistantMessages = messages.filter(m => 
      m.role === 'assistant' && m.metadata
    )

    // traceService.trace('HistoryService', 'getProviderModelStats: message filtering', {
      // totalMessages: allMessages.length,
      // filteredByTime: messages.length,
      // assistantMessagesWithMetadata: assistantMessages.length
    // })

    // Group by provider+model combination
    const stats = new Map<string, {
      provider: string
      model?: string
      tokenCounts: number[]
      durations: number[]
      tokensPerSecond: number[]
    }>()

    for (const msg of assistantMessages) {
      const metadata = msg.metadata || {}
      const provider = metadata.provider || 'unknown'
      const model = metadata.model

      // traceService.trace('HistoryService', 'processing provider stats', {
        // messageId: msg.id,
        // provider,
        // model,
        // hasTokenCount: !!metadata.tokenCount,
        // hasDuration: !!metadata.totalTimeMs,
        // hasTPS: !!metadata.tokensPerSecond
      // })

      const key = `${provider}:${model || 'unknown'}`

      if (!stats.has(key)) {
        stats.set(key, {
          provider,
          model,
          tokenCounts: [],
          durations: [],
          tokensPerSecond: []
        })
      }

      const stat = stats.get(key)!

      if (metadata.tokenCount && typeof metadata.tokenCount === 'number') {
        stat.tokenCounts.push(metadata.tokenCount)
      }

      if (metadata.totalTimeMs && typeof metadata.totalTimeMs === 'number') {
        stat.durations.push(metadata.totalTimeMs)
      }

      if (metadata.tokensPerSecond && typeof metadata.tokensPerSecond === 'number') {
        stat.tokensPerSecond.push(metadata.tokensPerSecond)
      }
    }

    // traceService.trace('HistoryService', 'getProviderModelStats: grouped stats', {
      // statsCount: stats.size,
      // providers: Array.from(stats.keys())
    // })

    // Convert to array and calculate averages
    const avg = (arr: number[]) => arr.length > 0 ? arr.reduce((a, b) => a + b, 0) / arr.length : 0

    return Array.from(stats.values())
      .map(stat => ({
        provider: stat.provider,
        model: stat.model,
        messageCount: stat.tokenCounts.length,
        avgTokenCount: Math.round(avg(stat.tokenCounts)),
        avgDurationMs: Math.round(avg(stat.durations)),
        avgTokensPerSecond: Math.round(avg(stat.tokensPerSecond) * 10) / 10
      }))
      .sort((a, b) => b.messageCount - a.messageCount)
  }

  /**
   * Get comprehensive message analysis
   *
   * Combines performance, distribution, and provider stats
   *
   * @param timeRange - Optional time range to filter logs
   * @returns Complete message analysis
   */
  async getMessageAnalysis(timeRange?: TimeRange): Promise<MessageAnalysis> {
    const [performance, distribution, providerStats] = await Promise.all([
      this.getMessagePerformance(timeRange),
      this.getMessageLengthDistribution(timeRange),
      this.getProviderModelStats(timeRange)
    ])

    return {
      performance,
      distribution,
      providerStats,
      timeRange
    }
  }

  /**
   * Analyze last N sessions
   *
   * Fetches the most recent sessions and calculates:
   * - Message count per session
   * - Total tokens per session
   * - Average response time
   * - Session duration
   *
   * @param limit - Number of sessions to analyze (default: 10)
   * @returns Session analysis result
   */
  async getLastSessionsAnalysis(limit: number = 10): Promise<SessionAnalysisResult> {
    // traceService.trace('HistoryService', 'getLastSessionsAnalysis started', { limit })

    // Get sessions from SessionsService cache (no API call needed)
    const cachedSessions = sessionsService.getSessions()

    // traceService.trace('HistoryService', 'getLastSessionsAnalysis: sessions loaded from cache', {
      // totalSessions: cachedSessions.length
    // })

    if (!cachedSessions || cachedSessions.length === 0) {
      // traceService.trace('HistoryService', 'getLastSessionsAnalysis: no sessions found')
      return {
        sessions: [],
        totalSessions: 0,
        totalMessages: 0,
        totalTokens: 0,
        avgMessagesPerSession: 0,
        avgTokensPerSession: 0,
        avgSessionDurationMs: 0,
        limit
      }
    }

    // Sort by updatedAt (most recent first) and take limit
    const recentSessions = cachedSessions
      .sort((a, b) => b.updatedAt.getTime() - a.updatedAt.getTime())
      .slice(0, limit)

    // traceService.trace('HistoryService', 'getLastSessionsAnalysis: analyzing recent sessions', {
      // sessionIds: recentSessions.map(s => s.id)
    // })

    // Analyze cached sessions (already have messages)
    const sessionSummaries: SessionAnalysisSummary[] = recentSessions.map((session) => {
      const messages = session.messages || []
      const messageCount = messages.length

      const totalTokens = messages.reduce((sum: number, msg: unknown) => {
        const m = msg as { metadata?: { tokenCount?: number; totalTimeMs?: number } }
        return sum + (m.metadata?.tokenCount ?? 0)
      }, 0)

      const totalDuration = messages.reduce((sum: number, msg: unknown) => {
        const m = msg as { metadata?: { tokenCount?: number; totalTimeMs?: number } }
        return sum + (m.metadata?.totalTimeMs ?? 0)
      }, 0)

      const avgResponseTimeMs = messageCount > 0 ? totalDuration / messageCount : 0
      const avgTokensPerSecond = avgResponseTimeMs > 0 ? (totalTokens / avgResponseTimeMs) * 1000 : 0

      // Calculate session duration (from first to last message)
      let duration = 0
      if (messages.length > 1) {
        const timestamps = messages.map((m: unknown) => new Date((m as { timestamp?: string }).timestamp ?? Date.now()).getTime())
        duration = Math.max(...timestamps) - Math.min(...timestamps)
      }

      return {
        sessionId: session.id,
        title: session.title ?? 'New Session',
        agentId: session.agentId,
        messageCount,
        totalTokens,
        avgResponseTimeMs: Math.round(avgResponseTimeMs),
        avgTokensPerSecond: Math.round(avgTokensPerSecond * 10) / 10,
        createdAt: session.createdAt,
        updatedAt: session.updatedAt,
        duration
      }
    })

    // Calculate totals
    const totalSessions = sessionSummaries.length
    const totalMessages = sessionSummaries.reduce((sum, s) => sum + s.messageCount, 0)
    const totalTokens = sessionSummaries.reduce((sum, s) => sum + s.totalTokens, 0)
    const avgMessagesPerSession = totalSessions > 0 ? Math.round(totalMessages / totalSessions) : 0
    const avgTokensPerSession = totalSessions > 0 ? Math.round(totalTokens / totalSessions) : 0
    const avgSessionDurationMs = totalSessions > 0
      ? Math.round(sessionSummaries.reduce((sum, s) => sum + s.duration, 0) / totalSessions)
      : 0

    return {
      sessions: sessionSummaries,
      totalSessions,
      totalMessages,
      totalTokens,
      avgMessagesPerSession,
      avgTokensPerSession,
      avgSessionDurationMs,
      limit
    }
  }

  /**
   * Get summary statistics for sessions
   *
   * @param limit - Number of sessions to analyze
   * @returns Session summary statistics
   */
  async getSessionSummary(limit: number = 10): Promise<{
    totalSessions: number
    totalMessages: number
    totalTokens: number
    avgMessagesPerSession: number
    avgTokensPerSession: number
  }> {
    const result = await this.getLastSessionsAnalysis(limit)
    return {
      totalSessions: result.totalSessions,
      totalMessages: result.totalMessages,
      totalTokens: result.totalTokens,
      avgMessagesPerSession: result.avgMessagesPerSession,
      avgTokensPerSession: result.avgTokensPerSession
    }
  }
}

// Export singleton instance
export const historyService = new HistoryService()
