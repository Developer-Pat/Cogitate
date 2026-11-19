/**
 * SessionCards - Display individual session analysis cards
 *
 * Shows session details in a card layout with metrics
 */

import type { SessionAnalysisSummary } from '@/services/domain/HistoryService'

interface SessionCardsProps {
  sessions?: SessionAnalysisSummary[]
  isLoading?: boolean
}

export default function SessionCards({ sessions, isLoading }: SessionCardsProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="card bg-base-200 shadow-sm">
            <div className="card-body">
              <div className="skeleton h-6 w-3/4 mb-2"></div>
              <div className="skeleton h-4 w-1/2 mb-4"></div>
              <div className="space-y-2">
                <div className="skeleton h-4 w-full"></div>
                <div className="skeleton h-4 w-full"></div>
                <div className="skeleton h-4 w-full"></div>
              </div>
            </div>
          </div>
        ))}
      </div>
    )
  }

  if (!sessions || sessions.length === 0) {
    return (
      <div className="card bg-base-200 shadow-sm">
        <div className="card-body">
          <div className="text-center py-12 text-readout">
            <div className="text-4xl mb-4">💬</div>
            <div className="text-lg font-medium">No sessions found</div>
            <div className="text-sm">Start chatting to create sessions</div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {sessions.map((session) => (
        <div
          key={session.sessionId}
          className="card bg-base-200 shadow-sm hover:shadow-md transition-shadow"
        >
          <div className="card-body">
            {/* Session Title */}
            <div className="mb-2">
              <h3 className="card-title text-base truncate" title={session.title}>
                {session.title ?? 'New Session'}
              </h3>
              <div className="text-xs text-readout font-mono mt-1">
                {session.sessionId.slice(0, 8)}...
              </div>
            </div>

            {/* Agent ID */}
            <div className="text-xs text-readout">
              <span className="font-medium">Agent:</span> {session.agentId || 'N/A'}
            </div>

            {/* Divider */}
            <div className="divider my-2"></div>

            {/* Metrics Grid */}
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div>
                <div className="text-xs text-readout">Messages</div>
                <div className="font-bold text-primary">{session.messageCount}</div>
              </div>
              <div>
                <div className="text-xs text-readout">Tokens</div>
                <div className="font-bold text-secondary">
                  {session.totalTokens > 0 ? session.totalTokens.toLocaleString() : '0'}
                </div>
              </div>
              <div>
                <div className="text-xs text-readout">Avg Time</div>
                <div className="font-bold text-accent">
                  {session.avgResponseTimeMs > 0
                    ? session.avgResponseTimeMs < 1000
                      ? `${session.avgResponseTimeMs}ms`
                      : `${(session.avgResponseTimeMs / 1000).toFixed(2)}s`
                    : 'N/A'}
                </div>
              </div>
              <div>
                <div className="text-xs text-readout">Speed</div>
                <div className="font-bold text-info">
                  {session.avgTokensPerSecond > 0 ? `${session.avgTokensPerSecond} t/s` : 'N/A'}
                </div>
              </div>
            </div>

            {/* Session Duration */}
            {session.duration > 0 && (
              <div className="mt-2 pt-2 border-t border-base-300">
                <div className="text-xs text-readout">Session Duration</div>
                <div className="text-sm font-medium">
                  {session.duration < 60000
                    ? `${Math.round(session.duration / 1000)}s`
                    : session.duration < 3600000
                    ? `${Math.round(session.duration / 60000)}m ${Math.round((session.duration % 60000) / 1000)}s`
                    : `${Math.round(session.duration / 3600000)}h ${Math.round((session.duration % 3600000) / 60000)}m`}
                </div>
              </div>
            )}

            {/* Timestamps */}
            <div className="mt-2 text-xs text-readout">
              <div>Created: {formatDate(session.createdAt)}</div>
              <div>Updated: {formatDate(session.updatedAt)}</div>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

function formatDate(date: Date): string {
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}
