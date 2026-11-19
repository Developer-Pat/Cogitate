/**
 * MessageDistributionChart - Display message length distribution
 *
 * Simple bar chart showing message length categories:
 * - Short: < 100 characters
 * - Medium: 100-500 characters
 * - Long: 500-1000 characters
 * - Very Long: > 1000 characters
 */

import type { MessageLengthDistribution } from '@/services/domain/HistoryService'

interface MessageDistributionChartProps {
  distribution?: MessageLengthDistribution
  isLoading?: boolean
}

export default function MessageDistributionChart({ distribution, isLoading }: MessageDistributionChartProps) {
  if (isLoading) {
    return (
      <div className="card bg-base-200 shadow-sm">
        <div className="card-body">
          <h3 className="card-title mb-4">Message Length Distribution</h3>
          <div className="space-y-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="flex items-center gap-4">
                <div className="skeleton h-4 w-20"></div>
                <div className="skeleton h-6 flex-1 rounded"></div>
                <div className="skeleton h-4 w-12"></div>
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  if (!distribution) {
    return null
  }

  const total = distribution.short + distribution.medium + distribution.long + distribution.veryLong

  const categories = [
    {
      label: 'Short',
      value: distribution.short,
      description: '< 100 chars',
      color: 'bg-info',
      barColor: 'progress-info'
    },
    {
      label: 'Medium',
      value: distribution.medium,
      description: '100-500 chars',
      color: 'bg-success',
      barColor: 'progress-success'
    },
    {
      label: 'Long',
      value: distribution.long,
      description: '500-1000 chars',
      color: 'bg-warning',
      barColor: 'progress-warning'
    },
    {
      label: 'Very Long',
      value: distribution.veryLong,
      description: '> 1000 chars',
      color: 'bg-error',
      barColor: 'progress-error'
    }
  ]

  return (
    <div className="card bg-base-200 shadow-sm">
      <div className="card-body">
        <h3 className="card-title mb-4">Message Length Distribution</h3>

        {total === 0 ? (
          <div className="text-center py-8 text-readout">
            <div className="text-4xl mb-2">📊</div>
            <div>No message data available</div>
          </div>
        ) : (
          <div className="space-y-4">
            {categories.map((category) => {
              const percentage = total > 0 ? Math.round((category.value / total) * 100) : 0

              return (
                <div key={category.label}>
                  <div className="flex justify-between items-center mb-1">
                    <div className="flex items-center gap-2">
                      <div className={`w-3 h-3 rounded-full ${category.color}`}></div>
                      <span className="font-medium">{category.label}</span>
                      <span className="text-xs text-readout">({category.description})</span>
                    </div>
                    <div className="text-sm font-medium">
                      {category.value} <span className="text-readout">({percentage}%)</span>
                    </div>
                  </div>
                  <progress
                    className={`progress ${category.barColor} w-full`}
                    value={percentage}
                    max="100"
                  ></progress>
                </div>
              )
            })}

            {/* Total */}
            <div className="divider my-4"></div>
            <div className="flex justify-between items-center">
              <span className="font-bold">Total Messages</span>
              <span className="text-xl font-bold text-primary">{total.toLocaleString()}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
