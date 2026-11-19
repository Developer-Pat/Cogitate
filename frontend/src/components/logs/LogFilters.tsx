import Pagination from './Pagination'

interface LogFiltersProps {
  selectedLevel: string
  searchTerm: string
  sourceType: 'all' | 'frontend' | 'backend'
  isSearching?: boolean
  // Time range filters
  fromTime?: string
  toTime?: string
  onFromTimeChange?: (time: string) => void
  onToTimeChange?: (time: string) => void
  // Time preset
  timePreset?: string
  onTimePresetChange?: (preset: string) => void
  showAdvancedTime?: boolean
  onToggleAdvancedTime?: () => void
  // Source filter (specific source like ProfileService, etc.)
  selectedSource?: string
  onSourceChange?: (source: string) => void
  availableSources?: string[]
  // Pagination props
  currentPage?: number
  totalPages?: number
  totalItems?: number
  pageSize?: number
  hasPrevPage?: boolean
  hasNextPage?: boolean
  onPrevPage?: () => void
  onNextPage?: () => void
  onPageChange?: (page: number) => void
  onLevelChange: (level: string) => void
  onSearchChange: (term: string) => void
  onSourceTypeChange: (type: 'all' | 'frontend' | 'backend') => void
  onPageSizeChange?: (size: number) => void
}

export default function LogFilters({
  selectedLevel,
  searchTerm,
  sourceType,
  isSearching = false,
  // Time range filters
  fromTime = '',
  toTime = '',
  onFromTimeChange = () => {},
  onToTimeChange = () => {},
  // Time preset
  timePreset = 'all',
  onTimePresetChange = () => {},
  showAdvancedTime = false,
  onToggleAdvancedTime = () => {},
  // Source filter
  selectedSource = 'all',
  onSourceChange = () => {},
  availableSources = [],
  // Pagination props
  currentPage = 1,
  totalPages = 1,
  totalItems = 0,
  pageSize = 50,
  hasPrevPage = false,
  hasNextPage = false,
  onPrevPage = () => {},
  onNextPage = () => {},
  onPageChange = () => {},
  onLevelChange,
  onSearchChange,
  onSourceTypeChange,
  onPageSizeChange = () => {}
}: LogFiltersProps) {
  const levels = [
    { value: 'all', label: 'All Levels' },
    { value: 'debug', label: 'Debug' },
    { value: 'info', label: 'Info' },
    { value: 'warning', label: 'Warning' },
    { value: 'error', label: 'Error' },
    { value: 'critical', label: 'Critical' }
  ]

  return (
    <div className="flex flex-col gap-4">
          {/* THE FILTERS BODY (2026-09-06): the card shell moved to the
              Logs page's collapse (the Filters expander) — this renders
              the body only, so the shell doesn't double up. */}
          {/* Search Bar with Refresh */}
          <div className="flex gap-3">
            <div className="relative flex-1">
              <input
                type="text"
                placeholder="Search logs by message or source..."
                className="input input-bordered w-full pl-10 rounded-[var(--form-input-radius)] bg-[var(--form-input-bg)] border-[var(--form-input-border)] text-[var(--form-input-text)] focus:border-[var(--form-input-focus-border)] transition-all duration-[var(--button-transition)]"
                value={searchTerm}
                onChange={(e) => onSearchChange(e.target.value)}
              />
              <svg
                className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-readout"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                />
              </svg>
              {searchTerm && (
                <div className="tooltip tooltip-top" data-tip="Clear search">
                  <button
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-base-content/50 hover:text-base-content"
                    onClick={() => onSearchChange('')}
                  >
                    ✕
                  </button>
                </div>
              )}
              {isSearching && (
                <span className="absolute right-10 top-1/2 -translate-y-1/2">
                  <span className="loading loading-spinner loading-xs text-primary"></span>
                </span>
              )}
            </div>

            {/* SEARCH + TIME on one line (2026-09-06, the user's
                ask): the time preset rides the search row, right
                justified; the Refresh button moved up to the Filters
                summary bar. */}
            <div className="flex items-center gap-2 shrink-0">
              <label className="text-sm font-medium text-label">Time:</label>
              <select
                className="select select-bordered rounded-[var(--form-input-radius)]"
                value={timePreset}
                onChange={(e) => onTimePresetChange?.(e.target.value)}
              >
                <option value="all">All Time</option>
                <option value="1h">Last 1 Hour</option>
                <option value="6h">Last 6 Hours</option>
                <option value="12h">Last 12 Hours</option>
                <option value="24h">Last 24 Hours</option>
                <option value="7d">Last 7 Days</option>
              </select>
              <span className="tooltip tooltip-top" data-tip={showAdvancedTime ? 'Hide the custom time range' : 'Show the custom time range'}>
                <button
                  className="btn btn-ghost"
                  onClick={onToggleAdvancedTime}
                  aria-label={showAdvancedTime ? 'Hide the custom time range' : 'Show the custom time range'}
                >
                  {showAdvancedTime ? '▲ Simple' : '▼ Advanced'}
                </button>
              </span>
              {(fromTime || toTime) && (
                <span className="tooltip tooltip-top" data-tip="Clear the time filter">
                  <button
                    className="btn btn-xs btn-ghost"
                    onClick={() => {
                      onTimePresetChange?.('all')
                      onFromTimeChange?.('')
                      onToTimeChange?.('')
                    }}
                    aria-label="Clear the time filter"
                  >
                    ✕ Clear
                  </button>
                </span>
              )}
            </div>

          </div>

          {/* LEVELS + SOURCES on one line (2026-09-06, the user's
              space ask): the level buttons LEFT, the file-type
              segmented + the specific-source select RIGHT. */}
          <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2">
            <div className="flex flex-wrap items-center gap-2">
              {levels.map(({ value, label }) => (
                <button
                  key={value}
                  className={`btn btn-sm rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)] ${
                    selectedLevel === value
                      ? 'btn-active btn-selected'
                      : 'btn-outline'
                  }`}
                  onClick={() => onLevelChange(value)}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-5 shrink-0 flex-wrap">
              <div className="flex items-center gap-2 shrink-0">
                <label className="text-sm font-medium text-label">Source:</label>
                <select
                  className="select select-bordered select-sm rounded-[var(--form-input-radius)]"
                  value={selectedSource}
                  onChange={(e) => onSourceChange(e.target.value)}
                >
                  <option value="all">All Sources</option>
                  {availableSources.map(source => (
                    <option key={source} value={source}>{source}</option>
                  ))}
                </select>
                {selectedSource !== 'all' && (
                  <span className="tooltip tooltip-top" data-tip="Clear the source filter">
                    <button
                      className="btn btn-xs btn-ghost"
                      onClick={() => onSourceChange('all')}
                      aria-label="Clear the source filter"
                    >
                      ✕
                    </button>
                  </span>
                )}
              </div>
              <div className="btn-group shrink-0">
                <div className="tooltip tooltip-top" data-tip="Show logs from both files">
                  <button
                    className={`btn btn-xs ${sourceType === 'all' ? 'btn-active btn-selected' : 'btn-outline'}`}
                    onClick={() => onSourceTypeChange('all')}
                  >
                    Both
                  </button>
                </div>
                <div className="tooltip tooltip-top" data-tip="Show frontend logs only">
                  <button
                    className={`btn btn-xs ${sourceType === 'frontend' ? 'btn-active btn-selected' : 'btn-outline'}`}
                    onClick={() => onSourceTypeChange('frontend')}
                  >
                    Frontend
                  </button>
                </div>
                <div className="tooltip tooltip-top" data-tip="Show backend logs only">
                  <button
                    className={`btn btn-xs ${sourceType === 'backend' ? 'btn-active btn-selected' : 'btn-outline'}`}
                    onClick={() => onSourceTypeChange('backend')}
                  >
                    Backend
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Time Range Filters - Advanced (Custom datetime) */}
          {showAdvancedTime && (
            <div className="flex flex-wrap gap-2 items-end p-3 bg-base-200 rounded-lg">
              <div className="flex flex-col gap-1">
                <label className="text-xs text-readout">From:</label>
                <input
                  type="datetime-local"
                  className="input input-bordered input-sm rounded-[var(--form-input-radius)]"
                  value={fromTime}
                  onChange={(e) => onFromTimeChange?.(e.target.value)}
                  placeholder="Start time"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-readout">To:</label>
                <input
                  type="datetime-local"
                  className="input input-bordered input-sm rounded-[var(--form-input-radius)]"
                  value={toTime}
                  onChange={(e) => onToTimeChange?.(e.target.value)}
                  placeholder="End time"
                />
              </div>
              <div className="text-xs text-readout pb-2">
                Custom time range (advanced)
              </div>
            </div>
          )}

          {/* Pagination Controls */}
            <div className="flex items-center justify-between gap-4 w-full">
              {/* Page Size Selector */}
              <div className="flex items-center gap-2">
                <label className="text-sm text-readout">Show:</label>
                <select
                  className="select select-bordered select-sm"
                  value={pageSize}
                  onChange={(e) => onPageSizeChange(Number(e.target.value))}
                >
                  <option value={25}>25 per page</option>
                  <option value={50}>50 per page</option>
                  <option value={100}>100 per page</option>
                  <option value={250}>250 per page</option>
                </select>
              </div>
              
              {/* Pagination */}
              <Pagination
                currentPage={currentPage}
                totalPages={totalPages}
                totalItems={totalItems}
                pageSize={pageSize}
                hasPrevPage={hasPrevPage}
                hasNextPage={hasNextPage}
                onPrevPage={onPrevPage}
                onNextPage={onNextPage}
                onPageChange={onPageChange}
              />
            </div>
    </div>
  )
}
