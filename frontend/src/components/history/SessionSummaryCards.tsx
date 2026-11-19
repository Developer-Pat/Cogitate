/**
 * SessionSummaryCards - Display session analysis summary statistics
 *
 * Shows total sessions, messages, tokens, and averages
 */

import type { SessionAnalysisResult } from '@/services/domain/HistoryService'

interface SessionSummaryCardsProps {
  result?: SessionAnalysisResult
  isLoading?: boolean
}

export default function SessionSummaryCards({ result, isLoading }: SessionSummaryCardsProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="card bg-base-200 shadow-sm">
            <div className="card-body py-4">
              <div className="skeleton h-4 w-24 mb-2"></div>
              <div className="skeleton h-8 w-32"></div>
            </div>
          </div>
        ))}
      </div>
    )
  }

  if (!result) {
    return null
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* Total Sessions */}
      <div className="card bg-base-200 shadow-sm">
        <div className="card-body py-4">
          <div className="text-sm text-readout">Total Sessions</div>
          <div className="text-3xl font-bold text-primary">
            {result.totalSessions}
          </div>
          <div className="text-xs text-readout">analyzed</div>
        </div>
      </div>

      {/* Total Messages */}
      <div className="card bg-base-200 shadow-sm">
        <div className="card-body py-4">
          <div className="text-sm text-readout">Total Messages</div>
          <div className="text-3xl font-bold text-secondary">
            {result.totalMessages.toLocaleString()}
          </div>
          <div className="text-xs text-readout">across all sessions</div>
        </div>
      </div>

      {/* Total Tokens */}
      <div className="card bg-base-200 shadow-sm">
        <div className="card-body py-4">
          <div className="text-sm text-readout">Total Tokens</div>
          <div className="text-3xl font-bold text-accent">
            {result.totalTokens.toLocaleString()}
          </div>
          <div className="text-xs text-readout">estimated</div>
        </div>
      </div>

      {/* Avg Messages Per Session */}
      <div className="card bg-base-200 shadow-sm">
        <div className="card-body py-4">
          <div className="text-sm text-readout">Avg Messages/Session</div>
          <div className="text-3xl font-bold text-info">
            {result.avgMessagesPerSession}
          </div>
          <div className="text-xs text-readout">messages</div>
        </div>
      </div>

      {/* Avg Tokens Per Session - Full Width Row */}
      <div className="card bg-base-200 shadow-sm md:col-span-2">
        <div className="card-body py-4">
          <div className="text-sm text-readout">Avg Tokens/Session</div>
          <div className="text-2xl font-bold text-success">
            {result.avgTokensPerSession.toLocaleString()}
          </div>
          <div className="text-xs text-readout">tokens per session</div>
        </div>
      </div>

      {/* Avg Session Duration - Full Width Row */}
      <div className="card bg-base-200 shadow-sm md:col-span-2">
        <div className="card-body py-4">
          <div className="text-sm text-readout">Avg Session Duration</div>
          <div className="text-2xl font-bold">
            {result.avgSessionDurationMs > 0
              ? result.avgSessionDurationMs < 60000
                ? `${Math.round(result.avgSessionDurationMs / 1000)}s`
                : `${Math.round(result.avgSessionDurationMs / 60000)}m ${Math.round((result.avgSessionDurationMs % 60000) / 1000)}s`
              : 'N/A'}
          </div>
          <div className="text-xs text-readout">per session</div>
        </div>
      </div>
    </div>
  )
}
