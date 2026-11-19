/**
 * MessagePerformanceCards - Display message performance metrics
 *
 * Shows average token count, duration, tokens per second, and fastest provider/model
 */

import type { MessagePerformance } from '@/services/domain/HistoryService'

interface MessagePerformanceCardsProps {
  performance?: MessagePerformance
  isLoading?: boolean
}

export default function MessagePerformanceCards({ performance, isLoading }: MessagePerformanceCardsProps) {
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

  if (!performance) {
    return null
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* Average Token Count */}
      <div className="card bg-base-200 shadow-sm">
        <div className="card-body py-4">
          <div className="text-sm text-readout">Avg Token Count</div>
          <div className="text-3xl font-bold text-primary">
            {performance.averageTokenCount > 0 ? performance.averageTokenCount.toLocaleString() : 'N/A'}
          </div>
          <div className="text-xs text-readout">tokens per message</div>
        </div>
      </div>

      {/* Average Duration */}
      <div className="card bg-base-200 shadow-sm">
        <div className="card-body py-4">
          <div className="text-sm text-readout">Avg Response Time</div>
          <div className="text-3xl font-bold text-secondary">
            {performance.averageDurationMs > 0 ? `${(performance.averageDurationMs / 1000).toFixed(2)}s` : 'N/A'}
          </div>
          <div className="text-xs text-readout">per message</div>
        </div>
      </div>

      {/* Tokens Per Second */}
      <div className="card bg-base-200 shadow-sm">
        <div className="card-body py-4">
          <div className="text-sm text-readout">Avg Speed</div>
          <div className="text-3xl font-bold text-accent">
            {performance.averageTokensPerSecond > 0 ? performance.averageTokensPerSecond : 'N/A'}
          </div>
          <div className="text-xs text-readout">tokens/second</div>
        </div>
      </div>

      {/* Total Messages */}
      <div className="card bg-base-200 shadow-sm">
        <div className="card-body py-4">
          <div className="text-sm text-readout">Total Messages</div>
          <div className="text-3xl font-bold text-info">
            {performance.totalMessages.toLocaleString()}
          </div>
          <div className="text-xs text-readout">analyzed</div>
        </div>
      </div>

      {/* Fastest Provider - Full Width Row */}
      <div className="card bg-base-200 shadow-sm md:col-span-2">
        <div className="card-body py-4">
          <div className="text-sm text-readout">Fastest Provider</div>
          <div className="flex items-baseline gap-2">
            <div className="text-2xl font-bold text-success">
              {performance.fastestProvider || 'N/A'}
            </div>
            {performance.fastestProvider && (
              <span className="badge badge-success badge-outline badge-sm">Fastest</span>
            )}
          </div>
        </div>
      </div>

      {/* Fastest Model - Full Width Row */}
      <div className="card bg-base-200 shadow-sm md:col-span-2">
        <div className="card-body py-4">
          <div className="text-sm text-readout">Fastest Model</div>
          <div className="flex items-baseline gap-2">
            <div className="text-2xl font-bold text-success">
              {performance.fastestModel || 'N/A'}
            </div>
            {performance.fastestModel && (
              <span className="badge badge-success badge-outline badge-sm">Fastest</span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
