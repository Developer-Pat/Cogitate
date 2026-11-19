import { useState, useEffect } from 'react'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { errorTrackingService, type ErrorEntry as ServiceErrorEntry } from '@/services/domain/ErrorTrackingService'
import { frontendLoggingService } from '@/services/frontendLoggingService'

interface ErrorAnalysisProps {
  onErrorResolve?: (errorId: string) => void
  onErrorIgnore?: (errorId: string) => void
}

export const ErrorAnalysis: React.FC<ErrorAnalysisProps> = ({
  onErrorResolve,
  onErrorIgnore
}) => {
  const [errors, setErrors] = useState<ServiceErrorEntry[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [selectedError, setSelectedError] = useState<ServiceErrorEntry | null>(null)
  const [filterType, setFilterType] = useState<'all' | 'error' | 'warning' | 'info'>('all')
  const [filterSeverity, setFilterSeverity] = useState<'all' | 'low' | 'medium' | 'high' | 'critical'>('all')
  const [filterStatus, setFilterStatus] = useState<'all' | 'active' | 'resolved' | 'ignored'>('active')

  // Load errors from service
  useEffect(() => {
    frontendLoggingService.info('ErrorAnalysis', 'Component mounted, loading errors')

    // Load initial errors - FAIL LOUDLY if backend unavailable
    errorTrackingService.loadFromBackend()
      .catch(err => {
        frontendLoggingService.error('ErrorAnalysis', 'BACKEND API NOT AVAILABLE - ErrorTrackingService failed', err)
        frontendLoggingService.error('ErrorAnalysis', 'EXPECTED: Backend endpoint /api/v1/debug/errors must be implemented')
        throw err // Re-throw to make it visible
      })
      .finally(() => {
        setIsLoading(false)
      })

    // Subscribe to error updates
    const unsubscribe = errorTrackingService.subscribe((updatedErrors) => {
      setErrors(updatedErrors)
      // TODO: Re-enable when debugging is needed - clogs logs
      // frontendLoggingService.debug('ErrorAnalysis', 'Errors updated', {
      //   count: updatedErrors.length
      // })
    })

    return () => {
      unsubscribe()
      frontendLoggingService.info('ErrorAnalysis', 'Component unmounted')
    }
  }, [])

  const handleResolve = async (errorId: string) => {
    try {
      frontendLoggingService.info('ErrorAnalysis', 'Resolving error', { errorId })
      await errorTrackingService.resolveError(errorId)
      onErrorResolve?.(errorId)
    } catch (error) {
      frontendLoggingService.error('ErrorAnalysis', 'Failed to resolve error', error, { errorId })
    }
  }

  const handleIgnore = async (errorId: string) => {
    try {
      frontendLoggingService.info('ErrorAnalysis', 'Ignoring error', { errorId })
      await errorTrackingService.ignoreError(errorId)
      onErrorIgnore?.(errorId)
    } catch (error) {
      frontendLoggingService.error('ErrorAnalysis', 'Failed to ignore error', error, { errorId })
    }
  }

  const getTypeColor = (type: ServiceErrorEntry['type']) => {
    switch (type) {
      case 'error': return 'badge-error badge-outline'
      case 'warning': return 'badge-warning badge-outline'
      case 'info': return 'badge-info badge-outline'
      default: return 'badge-muted badge-outline'
    }
  }

  const getSeverityColor = (severity: ServiceErrorEntry['severity']) => {
    switch (severity) {
      case 'critical': return 'bg-red-600'
      case 'high': return 'bg-orange-500'
      case 'medium': return 'bg-yellow-500'
      case 'low': return 'bg-primary'
      default: return 'bg-base-content/50'
    }
  }

  const getStatusColor = (status: ServiceErrorEntry['status']) => {
    switch (status) {
      case 'active': return 'badge-error badge-outline'
      case 'resolved': return 'badge-success badge-outline'
      case 'ignored': return 'badge-muted badge-outline'
      default: return 'badge-muted badge-outline'
    }
  }

  const getTimeAgo = (timestamp: string) => {
    const diff = Date.now() - new Date(timestamp).getTime()
    const minutes = Math.floor(diff / 60000)
    const hours = Math.floor(minutes / 60)
    const days = Math.floor(hours / 24)

    if (days > 0) return `${days}d ago`
    if (hours > 0) return `${hours}h ago`
    if (minutes > 0) return `${minutes}m ago`
    return 'Just now'
  }

  const filteredErrors = errors.filter(error => {
    const matchesType = filterType === 'all' || error.type === filterType
    const matchesSeverity = filterSeverity === 'all' || error.severity === filterSeverity
    const matchesStatus = filterStatus === 'all' || error.status === filterStatus

    return matchesType && matchesSeverity && matchesStatus
  })

  const activeCount = errors.filter(e => e.status === 'active').length
  const criticalCount = errors.filter(e => e.severity === 'critical' && e.status !== 'ignored').length
  const resolvedCount = errors.filter(e => e.status === 'resolved').length

  if (isLoading) {
    return (
      <ErrorBoundary>
        <div className="card bg-base-200 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
          <div className="card-body gap-[var(--card-gap)]">
            <h2 className="card-title">Error Analysis</h2>
            <div className="flex items-center justify-center py-8">
              <span className="loading loading-spinner loading-md"></span>
              <span className="ml-3">Loading errors...</span>
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
          <h2 className="card-title">Error Analysis</h2>

          {/* Summary Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="stat bg-base-100 rounded-lg p-4">
              <div className="stat-title">Total Errors</div>
              <div className="stat-value text-2xl">{errors.length}</div>
            </div>

            <div className="stat bg-base-100 rounded-lg p-4">
              <div className="stat-title">Critical</div>
              <div className="stat-value text-2xl text-error">
                {criticalCount}
              </div>
            </div>

            <div className="stat bg-base-100 rounded-lg p-4">
              <div className="stat-title">Active</div>
              <div className="stat-value text-2xl text-warning">{activeCount}</div>
            </div>

            <div className="stat bg-base-100 rounded-lg p-4">
              <div className="stat-title">Resolved</div>
              <div className="stat-value text-2xl text-success">
                {resolvedCount}
              </div>
            </div>
          </div>

          {/* Filters */}
          <div className="flex flex-col sm:flex-row gap-4 mb-6">
            <select
              className="select select-bordered flex-1 rounded-[var(--form-input-radius)] px-[var(--form-input-padding)] bg-[var(--form-select-bg)] border-[var(--form-select-border)] text-[var(--form-select-text)] focus:border-[var(--form-input-focus-border)] transition-all duration-[var(--button-transition)]"
              value={filterType}
              onChange={(e) => setFilterType(e.target.value as "error" | "warning" | "info" | "all")}
            >
              <option value="all">All Types</option>
              <option value="error">Errors</option>
              <option value="warning">Warnings</option>
              <option value="info">Info</option>
            </select>

            <select
              className="select select-bordered flex-1 rounded-[var(--form-input-radius)] px-[var(--form-input-padding)] bg-[var(--form-select-bg)] border-[var(--form-select-border)] text-[var(--form-select-text)] focus:border-[var(--form-input-focus-border)] transition-all duration-[var(--button-transition)]"
              value={filterSeverity}
              onChange={(e) => setFilterSeverity(e.target.value as "low" | "medium" | "high" | "critical" | "all")}
            >
              <option value="all">All Severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>

            <select
              className="select select-bordered flex-1 rounded-[var(--form-input-radius)] px-[var(--form-input-padding)] bg-[var(--form-select-bg)] border-[var(--form-select-border)] text-[var(--form-select-text)] focus:border-[var(--form-input-focus-border)] transition-all duration-[var(--button-transition)]"
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value as "active" | "all" | "resolved" | "ignored")}
            >
              <option value="active">Active</option>
              <option value="resolved">Resolved</option>
              <option value="ignored">Ignored</option>
              <option value="all">All</option>
            </select>
          </div>

          {/* Error List */}
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {filteredErrors.map(error => (
              <div
                key={error.id}
                className={`card bg-base-100 shadow-sm shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)] cursor-pointer hover-subtle transition-colors ${
                  selectedError?.id === error.id ? 'ring-2 ring-primary' : ''
                } ${error.status !== 'active' ? 'opacity-60' : ''}`}
                onClick={() => setSelectedError(error)}
              >
                <div className="card-body p-3">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <span className={`badge ${getTypeColor(error.type)}`}>
                          {error.type}
                        </span>
                        <span
                          className={`badge ${getSeverityColor(error.severity)} text-base-content`}
                        >
                          {error.severity}
                        </span>
                        <span className={`badge ${getStatusColor(error.status)}`}>
                          {error.status}
                        </span>
                      </div>

                      <h4 className="font-medium mb-1">{error.message}</h4>

                      <div className="flex flex-wrap gap-4 text-sm text-readout">
                        <span>Source: {error.source}</span>
                        <span>{getTimeAgo(error.timestamp)}</span>
                      </div>

                      {error.context && (
                        <div className="mt-2">
                          <details className="collapse collapse-arrow bg-base-200">
                            <summary className="collapse-title text-sm font-medium">
                              Context Details
                            </summary>
                            <div className="collapse-content">
                              <pre className="text-xs bg-base-300 p-2 rounded">
                                {JSON.stringify(error.context, null, 2)}
                              </pre>
                            </div>
                          </details>
                        </div>
                      )}
                    </div>

                    {error.status === 'active' && (
                      <div className="flex gap-2 ml-4">
                        <button
                          className="btn btn-sm btn-success rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
                          onClick={(e) => {
                            e.stopPropagation()
                            handleResolve(error.id)
                          }}
                        >
                          Resolve
                        </button>
                        <button
                          className="btn btn-sm btn-outline rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
                          onClick={(e) => {
                            e.stopPropagation()
                            handleIgnore(error.id)
                          }}
                        >
                          Ignore
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {filteredErrors.length === 0 && (
            <div className="text-center py-8">
              <p className="text-readout">
                {errors.length === 0 
                  ? 'No errors found. System is healthy!' 
                  : 'No errors found matching the current filters.'}
              </p>
            </div>
          )}

          {/* Error Detail Modal */}
          {selectedError && (
            <div className="modal modal-open">
              <div className="modal-box max-w-4xl">
                <h3 className="font-bold text-lg mb-4">Error Details</h3>

                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="label">
                        <span className="label-text font-semibold">Type</span>
                      </label>
                      <span className={`badge ${getTypeColor(selectedError.type)}`}>
                        {selectedError.type}
                      </span>
                    </div>

                    <div>
                      <label className="label">
                        <span className="label-text font-semibold">Severity</span>
                      </label>
                      <span
                        className={`badge ${getSeverityColor(selectedError.severity)} text-base-content`}
                      >
                        {selectedError.severity}
                      </span>
                    </div>

                    <div>
                      <label className="label">
                        <span className="label-text font-semibold">Status</span>
                      </label>
                      <span className={`badge ${getStatusColor(selectedError.status)}`}>
                        {selectedError.status}
                      </span>
                    </div>

                    <div>
                      <label className="label">
                        <span className="label-text font-semibold">Source</span>
                      </label>
                      <p>{selectedError.source}</p>
                    </div>
                  </div>

                  <div>
                    <label className="label">
                      <span className="label-text font-semibold">Message</span>
                    </label>
                    <p className="font-medium">{selectedError.message}</p>
                  </div>

                  <div>
                    <label className="label">
                      <span className="label-text font-semibold">Timestamp</span>
                    </label>
                    <p>{new Date(selectedError.timestamp).toLocaleString()}</p>
                  </div>

                  {selectedError.stackTrace && (
                    <div>
                      <label className="label">
                        <span className="label-text font-semibold">Stack Trace</span>
                      </label>
                      <pre className="bg-base-300 p-3 rounded text-sm overflow-x-auto">
                        {selectedError.stackTrace}
                      </pre>
                    </div>
                  )}

                  {selectedError.context && (
                    <div>
                      <label className="label">
                        <span className="label-text font-semibold">Context</span>
                      </label>
                      <pre className="bg-base-300 p-3 rounded text-sm overflow-x-auto">
                        {JSON.stringify(selectedError.context, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>

                <div className="modal-action">
                  {selectedError.status === 'active' && (
                    <button
                      className="btn btn-success rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
                      onClick={() => {
                        handleResolve(selectedError.id)
                        setSelectedError(null)
                      }}
                    >
                      Mark as Resolved
                    </button>
                  )}
                  <button 
                    className="btn rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]" 
                    onClick={() => setSelectedError(null)}
                  >
                    Close
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </ErrorBoundary>
  )
}
