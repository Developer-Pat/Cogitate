import { getLevelBadge } from './levelBadge'
import type { LogEntry } from '@/types'

export interface LogFilters {
  selectedLevel: string
  searchTerm: string
}

interface LogsTableProps {
  logs: LogEntry[]
  logsLoading: boolean
  logsError: Error | null
  onLogSelect: (log: LogEntry) => void
}

export default function LogsTable({
  logs,
  logsLoading,
  logsError,
  onLogSelect
}: LogsTableProps) {


  const getSourceBadge = (log: LogEntry) => {
    // Frontend logs have user_agent (browser), backend logs have null/undefined user_agent
    const isFrontend = log.log_type === 'frontend' ||
                       log.source?.toLowerCase().includes('navigation') ||
                       log.source?.toLowerCase().includes('performance') ||
                       log.source?.toLowerCase().includes('error') ||
                       !!log.user_agent  // Check for truthy value (not just defined)

    return isFrontend ? (
      <div className="tooltip tooltip-top" data-tip="Frontend log">
        <span className="text-xl">🖥️</span>
      </div>
    ) : (
      <div className="tooltip tooltip-top" data-tip="Backend log">
        <span className="text-xl">⚙️</span>
      </div>
    )
  }

  const formatTimestamp = (timestamp: string) => {
    if (!timestamp) return ''
    
    // Handle timestamps without timezone (treat as local time)
    // Format: "2026-03-20 13:20:39" or "2026-03-20T13:20:39"
    const cleanTimestamp = timestamp.replace('T', ' ')
    
    // Parse as local time
    const date = new Date(cleanTimestamp)
    
    // Check if date is valid
    if (isNaN(date.getTime())) {
      return timestamp // Return original if invalid
    }
    
    // Format as local datetime with timezone
    return date.toLocaleString(undefined, {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
      timeZoneName: 'short'
    })
  }

  return (
    <div className="card bg-base-100 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
      <div className="card-body p-0">
        {logsError && (
          <div className="alert alert-error m-4">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>Failed to load logs: {logsError.message}</span>
          </div>
        )}

        <div className="overflow-x-auto">
          <table className="table table-zebra">
            <thead>
              <tr className="bg-base-200">
                <th className="py-3">
                  <div className="tooltip tooltip-bottom" data-tip="Timestamps shown in your local timezone">
                    <span className="cursor-help">Timestamp ⓘ</span>
                  </div>
                </th>
                <th>Level</th>
                <th>Source</th>
                <th>Type</th>
                <th className="w-full">Message</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {logsLoading ? (
                <tr>
                  <td colSpan={6} className="text-center py-8">
                    <span className="loading loading-spinner loading-lg"></span>
                    <p className="mt-2 text-readout">Loading logs...</p>
                  </td>
                </tr>
              ) : logsError ? (
                <tr>
                  <td colSpan={6} className="text-center py-12">
                    <div className="text-readout">
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-16 w-16 mx-auto mb-4 opacity-50 text-error" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                      </svg>
                      <p className="text-lg font-medium mb-2 text-error">Error loading logs</p>
                      <p className="text-sm">{logsError.message}</p>
                    </div>
                  </td>
                </tr>
              ) : logs.length > 0 ? (
                logs.map((log, index) => (
                  <tr key={log.id || index} className="hover:bg-base-200/50">
                    <td className="font-mono text-xs whitespace-nowrap p-3">
                      {formatTimestamp(log.timestamp)}
                    </td>
                    <td>
                      {(() => {
                        const style = getLevelBadge(log.level)
                        return (
                          <div className={`badge ${style.cls} badge-sm font-semibold`}>
                            {style.label}
                          </div>
                        )
                      })()}
                    </td>
                    <td className="font-medium text-sm max-w-[120px] truncate">
                      {log.source}
                    </td>
                    <td>
                      {getSourceBadge(log)}
                    </td>
                    <td className="text-sm p-3 align-top">
                      <div className="tooltip tooltip-top max-w-none" data-tip={log.message}>
                        <div className="text-xs font-mono text-base-content break-all whitespace-pre-wrap">
                          {log.message}
                        </div>
                      </div>
                      {log.context && Object.keys(log.context).length > 0 && (
                        <div className="text-xs text-readout mt-1">
                          {Object.keys(log.context).length} context fields
                        </div>
                      )}
                    </td>
                    <td>
                      <button
                        className="btn btn-ghost btn-xs rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
                        onClick={() => onLogSelect(log)}
                      >
                        View
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="text-center py-12">
                    <div className="text-readout">
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-16 w-16 mx-auto mb-4 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      <p className="text-lg font-medium mb-2">No logs found</p>
                      {logs.length === 0 && !logsLoading ? (
                        <div className="text-sm">
                          <p className="mb-2">💡 The logs table is empty. This could mean:</p>
                          <ul className="text-left inline-block">
                            <li>• Backend returned no logs (check console for API response)</li>
                            <li>• Filters are excluding all logs</li>
                            <li>• Data is still loading (check if loading spinner appeared)</li>
                          </ul>
                          <p className="mt-2 text-xs text-readout">Check browser console (F12) for detailed debug logs starting with [LOGS PAGE], [useLogs], and [LOGS SERVICE]</p>
                        </div>
                      ) : (
                        <p className="text-sm mb-2">No logs match your current filters</p>
                      )}
                      {logs.length === 0 && (
                        <p className="text-xs mt-2">
                          💡 Tip: Navigate the app or check the browser console for errors to generate logs
                        </p>
                      )}
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {!logsLoading && !logsError && logs.length > 0 && (
          <div className="p-3 bg-base-200 text-center text-xs text-readout">
            Showing {logs.length} log{logs.length !== 1 ? 's' : ''}
          </div>
        )}
      </div>
    </div>
  )
}
