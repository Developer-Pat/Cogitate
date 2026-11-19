/**
 * DateRangeSelector - Time range picker for history analysis
 *
 * Provides quick select buttons and custom date range inputs
 */

export interface TimeRange {
  from: Date
  to: Date
}

interface DateRangeSelectorProps {
  value: TimeRange
  onChange: (range: TimeRange) => void
}

const QUICK_RANGES = [
  { label: 'Last 1h', hours: 1 },
  { label: 'Last 6h', hours: 6 },
  { label: 'Last 12h', hours: 12 },
  { label: 'Last 24h', hours: 24 },
  { label: 'Last 7d', days: 7 },
  { label: 'Last 30d', days: 30 }
]

export default function DateRangeSelector({ value, onChange }: DateRangeSelectorProps) {
  const handleQuickRange = (hours?: number, days?: number) => {
    const now = new Date()
    const from = new Date()

    if (hours) {
      from.setHours(now.getHours() - hours)
    } else if (days) {
      from.setDate(now.getDate() - days)
    }

    onChange({ from, to: now })
  }

  const handleFromChange = (dateString: string) => {
    const from = new Date(dateString)
    onChange({ from, to: value.to })
  }

  const handleToChange = (dateString: string) => {
    const to = new Date(dateString)
    onChange({ from: value.from, to })
  }

  const formatDate = (date: Date) => {
    return date.toISOString().slice(0, 16) // YYYY-MM-DDTHH:mm
  }

  return (
    <div className="card bg-base-200 shadow-sm">
      <div className="card-body py-4">
        <div className="flex flex-wrap gap-3 items-center justify-between">
          {/* Quick range buttons */}
          <div className="flex flex-wrap gap-2">
            {QUICK_RANGES.map((range) => (
              <button
                key={range.label}
                onClick={() => handleQuickRange(range.hours, range.days)}
                className="btn btn-sm btn-ghost"
              >
                {range.label}
              </button>
            ))}
          </div>

          {/* Custom range inputs */}
          <div className="flex gap-2 items-center">
            <div className="form-control">
              <label className="label">
                <span className="label-text text-xs">From</span>
              </label>
              <input
                type="datetime-local"
                value={formatDate(value.from)}
                onChange={(e) => handleFromChange(e.target.value)}
                className="input input-bordered input-sm w-40"
              />
            </div>

            <div className="form-control">
              <label className="label">
                <span className="label-text text-xs">To</span>
              </label>
              <input
                type="datetime-local"
                value={formatDate(value.to)}
                onChange={(e) => handleToChange(e.target.value)}
                className="input input-bordered input-sm w-40"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
