/**
 * ProviderComparisonTable - Display provider/model performance comparison
 *
 * Shows performance metrics grouped by provider and model
 */

import type { ProviderStats } from '@/services/domain/HistoryService'
import { Star, Zap } from 'lucide-react'

interface ProviderComparisonTableProps {
  stats?: ProviderStats[]
  isLoading?: boolean
}

export default function ProviderComparisonTable({ stats, isLoading }: ProviderComparisonTableProps) {
  if (isLoading) {
    return (
      <div className="card bg-base-200 shadow-sm">
        <div className="card-body p-0">
          <div className="p-4">
            <div className="skeleton h-6 w-48 mb-4"></div>
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="skeleton h-16 w-full"></div>
              ))}
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (!stats || stats.length === 0) {
    return (
      <div className="card bg-base-200 shadow-sm">
        <div className="card-body">
          <div className="text-center py-8 text-readout">
            <div className="text-4xl mb-2">📊</div>
            <div>No provider/model data available</div>
            <div className="text-sm">Make sure you have messages with provider/model metadata</div>
          </div>
        </div>
      </div>
    )
  }

  // Find best values for highlighting
  const fastest = stats.reduce((best, curr) =>
    curr.avgTokensPerSecond > best.avgTokensPerSecond ? curr : best
  )

  const mostUsed = stats.reduce((best, curr) =>
    curr.messageCount > best.messageCount ? curr : best
  )

  return (
    <div className="card bg-base-200 shadow-sm">
      <div className="card-body p-0">
        <div className="overflow-x-auto">
          <table className="table table-zebra">
            <thead>
              <tr>
                <th>Provider</th>
                <th>Model</th>
                <th className="text-right">Messages</th>
                <th className="text-right">Avg Tokens</th>
                <th className="text-right">Avg Time</th>
                <th className="text-right">Tokens/Sec</th>
              </tr>
            </thead>
            <tbody>
              {stats.map((stat, index) => {
                const isFastest = stat === fastest
                const isMostUsed = stat === mostUsed

                return (
                  <tr
                    key={`${stat.provider}-${stat.model || 'unknown'}-${index}`}
                    className={`hover:bg-base-300/50 ${isFastest ? 'bg-success/10' : ''}`}
                  >
                    <td>
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{stat.provider}</span>
                        {isMostUsed && (
                          <span className="tooltip tooltip-top" data-tip="Most used">
                            <span className="badge badge-primary badge-outline badge-xs">
                              <Star className="h-2.5 w-2.5" />
                            </span>
                          </span>
                        )}
                      </div>
                    </td>
                    <td>
                      <span className="font-mono text-sm">{stat.model || 'N/A'}</span>
                    </td>
                    <td className="text-right">
                      <span className="font-medium">{stat.messageCount.toLocaleString()}</span>
                    </td>
                    <td className="text-right">
                      <span className="text-readout">
                        {stat.avgTokenCount > 0 ? stat.avgTokenCount.toLocaleString() : 'N/A'}
                      </span>
                    </td>
                    <td className="text-right">
                      <span className="text-readout">
                        {stat.avgDurationMs > 0 ? `${(stat.avgDurationMs / 1000).toFixed(2)}s` : 'N/A'}
                      </span>
                    </td>
                    <td className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <span className={`font-bold ${isFastest ? 'text-success' : ''}`}>
                          {stat.avgTokensPerSecond > 0 ? stat.avgTokensPerSecond : 'N/A'}
                        </span>
                        {isFastest && (
                          <span className="tooltip tooltip-top" data-tip="Fastest">
                            <span className="badge badge-success badge-outline badge-xs">
                              <Zap className="h-2.5 w-2.5" />
                            </span>
                          </span>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {/* Summary */}
        <div className="p-4 bg-base-300 rounded-b-lg">
          <div className="flex flex-wrap gap-4 text-sm">
            <div className="flex items-center gap-2">
              <span className="badge badge-primary badge-outline badge-sm"><Star className="h-3 w-3" /></span>
              <span>Most used provider/model</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="badge badge-success badge-outline badge-sm"><Zap className="h-3 w-3" /></span>
              <span>Fastest (tokens/sec)</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}