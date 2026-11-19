/**
 * SessionAnalysisControls - Controls for session analysis
 *
 * - Session limit selector (5, 10, 20, 50)
 * - Generate/Regenerate analysis button
 */

interface SessionAnalysisControlsProps {
  limit: number
  onLimitChange: (limit: number) => void
  onGenerate: () => void
  isLoading?: boolean
  hasData?: boolean
}

const LIMIT_OPTIONS = [5, 10, 20, 50]

export default function SessionAnalysisControls({
  limit,
  onLimitChange,
  onGenerate,
  isLoading = false,
  hasData = false
}: SessionAnalysisControlsProps) {
  return (
    <div className="card bg-base-200 shadow-sm">
      <div className="card-body py-4">
        <div className="flex flex-wrap gap-4 items-center justify-between">
          {/* Limit Selector */}
          <div className="flex items-center gap-3">
            <label className="text-sm font-medium">Analyze Last:</label>
            <div className="btn-group">
              {LIMIT_OPTIONS.map((option) => (
                <button
                  key={option}
                  className={`btn btn-sm ${limit === option ? 'btn-active btn-primary' : 'btn-ghost'}`}
                  onClick={() => onLimitChange(option)}
                  disabled={isLoading}
                >
                  {option}
                </button>
              ))}
            </div>
            <span className="text-sm text-readout">sessions</span>
          </div>

          {/* Generate Button */}
          <button
            className={`btn ${isLoading ? 'btn-ghost' : 'btn-primary'}`}
            onClick={onGenerate}
            disabled={isLoading}
          >
            {isLoading ? (
              <>
                <span className="loading loading-spinner loading-sm"></span>
                Analyzing...
              </>
            ) : hasData ? (
              <>
                <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Regenerate Analysis
              </>
            ) : (
              <>
                <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
                Generate Analysis
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
