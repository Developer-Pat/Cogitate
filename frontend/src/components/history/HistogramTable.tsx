/**
 * HistogramTable - Display log message frequency table
 */

import type { LogHistogram } from '@/services/domain/HistoryService'

interface HistogramTableProps {
  data: LogHistogram[]
  isLoading?: boolean
  maxRows?: number
}

export default function HistogramTable({ data, isLoading, maxRows = 100 }: HistogramTableProps) {
  if (isLoading) {
    return (
      <div className="card bg-base-200 shadow-sm">
        <div className="card-body">
          <div className="flex justify-center items-center py-12">
            <span className="loading loading-spinner loading-md text-primary"></span>
            <span className="ml-3 text-readout">Loading histogram...</span>
          </div>
        </div>
      </div>
    )
  }

  if (!data || data.length === 0) {
    return (
      <div className="card bg-base-200 shadow-sm">
        <div className="card-body">
          <div className="text-center py-12">
            <div className="text-4xl mb-4">📊</div>
            <div className="text-lg font-medium text-readout">No logs found</div>
            <div className="text-sm text-readout">Try adjusting the time range</div>
          </div>
        </div>
      </div>
    )
  }

  const displayData = data.slice(0, maxRows)
  const hasMore = data.length > maxRows

  return (
    <div className="card bg-base-200 shadow-sm">
      <div className="card-body p-0">
        <div className="overflow-x-auto">
          <table className="table table-zebra">
            <thead>
              <tr>
                <th className="w-20 text-right">Count</th>
                <th>Message</th>
                <th className="w-40">Sources</th>
                <th className="w-32">Levels</th>
                <th className="w-48">Time Range</th>
              </tr>
            </thead>
            <tbody>
              {displayData.map((entry, index) => (
                <tr key={`${entry.message}-${index}`} className="hover:bg-base-300/50">
                  <td className="text-right font-mono font-bold text-primary">
                    {entry.count}
                  </td>
                  <td>
                    <div className="font-mono text-sm break-all">
                      {entry.message}
                    </div>
                  </td>
                  <td>
                    <div className="flex flex-wrap gap-1">
                      {entry.sources.slice(0, 3).map((source) => (
                        <span
                          key={source}
                          className="badge badge-sm badge-outline"
                          title={source}
                        >
                          {source.length > 15 ? source.slice(0, 15) + '...' : source}
                        </span>
                      ))}
                      {entry.sources.length > 3 && (
                        <span className="badge badge-sm badge-ghost">
                          +{entry.sources.length - 3}
                        </span>
                      )}
                    </div>
                  </td>
                  <td>
                    <div className="flex flex-wrap gap-1">
                      {entry.levels.map((level) => {
                        const levelColors: Record<string, string> = {
                          debug: 'badge-ghost',
                          info: 'badge-info badge-outline',
                          warning: 'badge-warning badge-outline',
                          error: 'badge-error badge-outline',
                          critical: 'badge-error badge-outline'
                        }
                        return (
                          <span
                            key={level}
                            className={`badge badge-xs ${levelColors[level.toLowerCase()] || 'badge-ghost'}`}
                          >
                            {level}
                          </span>
                        )
                      })}
                    </div>
                  </td>
                  <td className="text-xs text-readout">
                    <div>{formatDate(entry.firstSeen)}</div>
                    <div className="text-readout">
                      to {formatDate(entry.lastSeen)}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {hasMore && (
          <div className="p-4 text-center text-sm text-readout border-t border-base-300">
            Showing {maxRows} of {data.length} messages
          </div>
        )}
      </div>
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
