/**
 * StatsCards - Summary statistics for log histogram
 */

import type { LogHistogram } from '@/services/domain/HistoryService'

interface StatsCardsProps {
  histogram: LogHistogram[]
  totalLogs?: number
  errorCount?: number
  warningCount?: number
}

export default function StatsCards({ histogram, totalLogs, errorCount = 0, warningCount = 0 }: StatsCardsProps) {
  const totalMessages = histogram.length

  // Count errors and warnings from histogram
  const calculatedErrorCount = histogram.filter(h =>
    h.levels.includes('error') || h.levels.includes('critical')
  ).reduce((sum, h) => sum + h.count, 0)

  const calculatedWarningCount = histogram.filter(h =>
    h.levels.includes('warning')
  ).reduce((sum, h) => sum + h.count, 0)

  const displayErrorCount = errorCount || calculatedErrorCount
  const displayWarningCount = warningCount || calculatedWarningCount

  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
      {/* Total Logs */}
      <div className="card bg-base-200 shadow-sm">
        <div className="card-body py-4">
          <div className="text-sm text-readout">Total Logs</div>
          <div className="text-3xl font-bold text-primary">{totalLogs || 'N/A'}</div>
        </div>
      </div>

      {/* Unique Messages */}
      <div className="card bg-base-200 shadow-sm">
        <div className="card-body py-4">
          <div className="text-sm text-readout">Unique Messages</div>
          <div className="text-3xl font-bold text-info">{totalMessages}</div>
        </div>
      </div>

      {/* Errors */}
      <div className="card bg-base-200 shadow-sm">
        <div className="card-body py-4">
          <div className="text-sm text-readout">Errors</div>
          <div className={`text-3xl font-bold ${displayErrorCount > 0 ? 'text-error' : 'text-success'}`}>
            {displayErrorCount}
          </div>
        </div>
      </div>

      {/* Warnings */}
      <div className="card bg-base-200 shadow-sm">
        <div className="card-body py-4">
          <div className="text-sm text-readout">Warnings</div>
          <div className={`text-3xl font-bold ${displayWarningCount > 0 ? 'text-warning' : 'text-success'}`}>
            {displayWarningCount}
          </div>
        </div>
      </div>
    </div>
  )
}
