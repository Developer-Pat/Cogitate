import { useState, useEffect } from 'react'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { logManagementService } from '@/services/domain/LogManagementService'
import { frontendLoggingService } from '@/services/frontendLoggingService'
import LoggingConfigPanel from '@/components/settings/LoggingConfigPanel'
import type { LogEntry as ServiceLogEntry, LogFilter } from '@/types'

interface LogViewerProps {
  onLogFilter?: (filters: LogFilters) => void
  onLogExport?: (format: 'json' | 'csv') => void
  enableStreaming?: boolean
}

export interface LogFilters {
  level: string[]
  source: string[]
  timeRange: {
    start: string
    end: string
  }
  search: string
}

export const LogViewer: React.FC<LogViewerProps> = ({
  onLogFilter,
  onLogExport,
  enableStreaming = true
}) => {
  const [logs, setLogs] = useState<ServiceLogEntry[]>([])
  const [filters, setFilters] = useState<LogFilters>({
    level: [],
    source: [],
    timeRange: {
      start: new Date(Date.now() - 3600000).toISOString(),
      end: new Date().toISOString()
    },
    search: ''
  })
  const [showConfig, setShowConfig] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [_unused] = useState(true);

  // Load initial logs and subscribe to updates
  useEffect(() => {
    // TODO: Re-enable mount log when debugging is needed - currently clogs logs.txt
    // frontendLoggingService.info('LogViewer', 'Component mounted')

    // Load initial logs - FAIL LOUDLY if backend unavailable
    logManagementService.loadRecentLogs(100)
      .catch(err => {
        frontendLoggingService.error('LogViewer', 'BACKEND API NOT AVAILABLE - LogManagementService failed', err)
        frontendLoggingService.error('LogViewer', 'EXPECTED: Backend endpoint /api/v1/logs/recent must be implemented')
        throw err // Re-throw to make it visible
      })
      .finally(() => {
        setIsLoading(false)
      })

    // Subscribe to log updates
    const unsubscribe = logManagementService.subscribe((updatedLogs) => {
      setLogs(updatedLogs)
      // TODO: Re-enable this debug log when needed - currently clogs logs.txt
      // frontendLoggingService.debug('LogViewer', 'Logs updated', {
      //   count: updatedLogs.length
      // })
    })

    // Start streaming if enabled
    let streamingUnsubscribe: (() => void) | undefined
    if (enableStreaming) {
      streamingUnsubscribe = logManagementService.streamLogs((newLog) => {
        frontendLoggingService.debug('LogViewer', 'New log streamed', {
          level: newLog.level,
          source: newLog.source
        })
      })
      setIsStreaming(true)
    }

    return () => {
      unsubscribe()
      streamingUnsubscribe?.()
      if (isStreaming) {
        logManagementService.stopStreaming()
      }
      frontendLoggingService.info('LogViewer', 'Component unmounted')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enableStreaming])

  const handleRefresh = async () => {
    // TODO: Re-enable this log when debugging is needed - currently clogs logs.txt
    // frontendLoggingService.info('LogViewer', 'Manual refresh triggered')
    setIsLoading(true)
    try {
      await logManagementService.loadRecentLogs(100, filters as unknown as LogFilter | undefined)
    } catch (error) {
      frontendLoggingService.error('LogViewer', 'Failed to refresh logs', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleExport = async (format: 'json' | 'csv') => {
    try {
      frontendLoggingService.info('LogViewer', `Exporting logs as ${format}`)
      const blob = await logManagementService.exportLogs(format, filters as unknown as LogFilter | undefined)
      
      // Create download link
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `logs-${new Date().toISOString()}.${format}`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      
      onLogExport?.(format)
      frontendLoggingService.info('LogViewer', 'Logs exported successfully')
    } catch (error) {
      frontendLoggingService.error('LogViewer', 'Failed to export logs', error)
    }
  }

  const handleClearLogs = async () => {
    if (!confirm('Are you sure you want to clear all frontend logs?')) return

    try {
      await logManagementService.clearFrontendLogs()
      frontendLoggingService.info('LogViewer', 'Frontend logs cleared')

      // Clear local state immediately
      setLogs([])

      // Reload empty logs from backend
      await logManagementService.loadRecentLogs(100)
      
      // Note: Stats will auto-refresh via useLogStats hook (1 second interval)
      // No page reload needed
    } catch (error) {
      frontendLoggingService.error('LogViewer', 'Failed to clear logs', error)
    }
  }

  const handleFilterChange = (newFilters: Partial<LogFilters>) => {
    const updatedFilters = { ...filters, ...newFilters }
    setFilters(updatedFilters)
    onLogFilter?.(updatedFilters)
    frontendLoggingService.debug('LogViewer', 'Filters changed', updatedFilters)
  }

  const filteredLogs = logs.filter(log => {
    // Filter by level
    if (filters.level.length > 0 && !filters.level.includes(log.level)) {
      return false
    }

    // Filter by source
    if (filters.source.length > 0 && !filters.source.some(s => log.source.includes(s))) {
      return false
    }

    // Filter by time range
    const logTime = new Date(log.timestamp).getTime()
    const startTime = new Date(filters.timeRange.start).getTime()
    const endTime = new Date(filters.timeRange.end).getTime()
    if (logTime < startTime || logTime > endTime) {
      return false
    }

    // Filter by search
    if (filters.search && !log.message.toLowerCase().includes(filters.search.toLowerCase())) {
      return false
    }

    return true
  })

  const getLevelColor = (level: string) => {
    switch (level) {
      case 'critical': return 'badge-error badge-outline'
      case 'error': return 'badge-error badge-outline'
      case 'warning': return 'badge-warning badge-outline'
      case 'info': return 'badge-info badge-outline'
      case 'debug': return 'badge-muted badge-outline'
      default: return 'badge-muted badge-outline'
    }
  }

  const getTimeAgo = (timestamp: string) => {
    const diff = Date.now() - new Date(timestamp).getTime()
    const seconds = Math.floor(diff / 1000)
    const minutes = Math.floor(seconds / 60)
    const hours = Math.floor(minutes / 60)

    if (hours > 0) return `${hours}h ago`
    if (minutes > 0) return `${minutes}m ago`
    return `${seconds}s ago`
  }

  const levelCounts = logs.reduce((acc, log) => {
    acc[log.level] = (acc[log.level] || 0) + 1
    return acc
  }, {} as Record<string, number>)

  if (isLoading) {
    return (
      <ErrorBoundary>
        <div className="card bg-base-200 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
          <div className="card-body gap-[var(--card-gap)]">
            <h2 className="card-title">Log Viewer</h2>
            <div className="flex items-center justify-center py-8">
              <span className="loading loading-spinner loading-md"></span>
              <span className="ml-3">Loading logs...</span>
            </div>
          </div>
        </div>
      </ErrorBoundary>
    )
  }

  return (
    <ErrorBoundary>
      <div className="card bg-base-200 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
        <div className="card-body gap-[var(--card-gap)]">
          <div className="flex items-center justify-between">
            <h2 className="card-title">Log Viewer</h2>
            <div className="flex gap-2">
              <span className="tooltip tooltip-bottom" data-tip="Refresh logs">
              <button
                className="btn btn-sm btn-outline"
                onClick={handleRefresh}
              >
                Refresh
              </button>
              </span>
              <span className="tooltip tooltip-bottom" data-tip={isStreaming ? 'Stop streaming' : 'Start streaming'}>
              <button
                className={`btn btn-sm ${isStreaming ? 'btn-active btn-selected' : 'btn-outline'}`}
                onClick={() => {
                  if (isStreaming) {
                    logManagementService.stopStreaming()
                    setIsStreaming(false)
                  } else {
                    logManagementService.streamLogs(() => {})
                    setIsStreaming(true)
                  }
                }}
              >
                Live
              </button>
              </span>
              <span className="tooltip tooltip-bottom" data-tip="Log settings">
              <button
                className="btn btn-sm btn-outline"
                onClick={() => setShowConfig(!showConfig)}
              >
                Settings
              </button>
              </span>
            </div>
          </div>

          {/* Summary Stats */}
          <div className="grid grid-cols-5 gap-2 mb-4">
            <div className="text-center p-2 bg-base-100 rounded">
              <div className="text-xs text-readout">Total</div>
              <div className="text-lg font-bold">{logs.length}</div>
            </div>
            {['debug', 'info', 'warning', 'error'].map(level => (
              <div key={level} className="text-center p-2 bg-base-100 rounded">
                <div className="text-xs text-readout capitalize">{level}</div>
                <div className={`text-lg font-bold ${
                  level === 'error' ? 'text-error' :
                  level === 'warning' ? 'text-warning' : ''
                }`}>
                  {levelCounts[level] || 0}
                </div>
              </div>
            ))}
          </div>

          {/* Filters */}
          <div className="flex flex-col gap-4 mb-4">
            <div className="flex flex-col sm:flex-row gap-2">
              <select
                className="select select-bordered w-full"
                multiple
                value={filters.level}
                onChange={(e) => handleFilterChange({
                  level: Array.from(e.target.selectedOptions, option => option.value)
                })}
              >
                <option value="debug">Debug</option>
                <option value="info">Info</option>
                <option value="warning">Warning</option>
                <option value="error">Error</option>
                <option value="critical">Critical</option>
              </select>

              <input
                type="text"
                className="input input-bordered flex-1 rounded-[var(--form-input-radius)] px-[var(--form-input-padding)]"
                placeholder="Search logs..."
                value={filters.search}
                onChange={(e) => handleFilterChange({ search: e.target.value })}
              />

              <button
                className="btn btn-sm btn-outline rounded-[var(--button-radius)] px-[var(--button-padding)]"
                onClick={() => handleFilterChange({ level: [], search: '' })}
              >
                Clear Filters
              </button>

              <div className="tooltip tooltip-top flex-1" data-tip="Filter by source (Ctrl/Cmd+click to select multiple)">
              <select
                className="select select-bordered w-full"
                multiple
                value={filters.source}
                onChange={(e) => handleFilterChange({
                  source: Array.from(e.target.selectedOptions, option => option.value)
                })}
              >
                <option value="frontend">Frontend</option>
                <option value="backend">Backend</option>
                {/* THE UNMANAGED CAPTURES (2026-09-12). These two files are the
                    launcher's raw redirect captures, and they are the ones that
                    actually break: console.log reached 162 MB during the flood
                    while this page showed a healthy 30 MB, because neither file
                    was reachable here. Labelled by what writes them. */}
                <option value="console">Console (backend stdout)</option>
                <option value="vite">Vite (frontend server)</option>
              </select>
              </div>
            </div>

            <div className="flex gap-2">
              <button
                className="btn btn-sm btn-outline rounded-[var(--button-radius)] px-[var(--button-padding)]"
                onClick={() => handleExport('json')}
              >
                Export JSON
              </button>
              <button
                className="btn btn-sm btn-outline rounded-[var(--button-radius)] px-[var(--button-padding)]"
                onClick={() => handleExport('csv')}
              >
                Export CSV
              </button>
              <button
                className="btn btn-sm btn-error btn-outline rounded-[var(--button-radius)] px-[var(--button-padding)]"
                onClick={handleClearLogs}
              >
                Clear Logs
              </button>
            </div>
          </div>

          {/* Log List */}
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {filteredLogs.map(log => (
              <div
                key={log.id}
                className="card bg-base-100 shadow-sm shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]"
              >
                <div className="card-body p-3">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`badge ${getLevelColor(log.level)}`}>
                          {log.level}
                        </span>
                        <span className="text-xs text-readout">
                          {getTimeAgo(log.timestamp)}
                        </span>
                        <span className="text-xs text-readout">
                          {new Date(log.timestamp).toLocaleTimeString()}
                        </span>
                      </div>

                      <p className="text-sm">{log.message}</p>

                      <div className="flex flex-wrap gap-2 mt-2 text-xs text-readout">
                        <span>Source: {log.source}</span>
                        {log.trace_id && <span>Trace: {log.trace_id}</span>}
                        {log.userId && <span>User: {log.userId}</span>}
                      </div>

                      {log.context && Object.keys(log.context).length > 0 && (
                        <details className="collapse collapse-arrow mt-2">
                          <summary className="collapse-title text-xs font-medium">
                            Context
                          </summary>
                          <div className="collapse-content">
                            <pre className="text-xs bg-base-300 p-2 rounded overflow-x-auto">
                              {JSON.stringify(log.context, null, 2)}
                            </pre>
                          </div>
                        </details>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {filteredLogs.length === 0 && (
            <div className="text-center py-8 text-readout">
              <div className="text-4xl mb-4">📝</div>
              <p className="text-lg font-medium">
                {logs.length === 0 ? 'No logs - Log viewer is empty' : 'No logs match your filters'}
              </p>
              <p className="text-sm mt-2">
                {logs.length === 0 
                  ? 'Logs will appear here as you use the application' 
                  : 'Try adjusting your filters or click Refresh'}
              </p>
              <button
                className="btn btn-sm btn-primary mt-4"
                onClick={handleRefresh}
              >
                ↻ Refresh Logs
              </button>
            </div>
          )}

          {/* Settings Panel */}
          {showConfig && (
            <div className="mt-4">
              <LoggingConfigPanel />
            </div>
          )}
        </div>
      </div>
    </ErrorBoundary>
  )
}
