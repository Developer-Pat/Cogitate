import { useState, useEffect } from 'react'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { debugActionsService, type DebugAction, type DebugActionStatus, type ActionResult } from '@/services/domain/DebugActionsService'
import { frontendLoggingService } from '@/services/frontendLoggingService'

interface DebugControlsProps {
  onActionExecute?: (action: DebugAction) => void
  onBreakpointToggle?: (enabled: boolean) => void
}

export const DebugControls: React.FC<DebugControlsProps> = ({
  onActionExecute,
  onBreakpointToggle
}) => {
  const [actions, setActions] = useState<DebugAction[]>([])
  const [breakpointsEnabled, setBreakpointsEnabled] = useState(false)
  const [selectedAction, setSelectedAction] = useState<DebugAction | null>(null)
  const [showConfirmation, setShowConfirmation] = useState(false)
  const [actionResults, setActionResults] = useState<Record<string, ActionResult>>({})
  const [isLoading, setIsLoading] = useState(true)

  // Load actions and subscribe to updates
  useEffect(() => {
    frontendLoggingService.info('DebugControls', 'Component mounted')

    // Load actions - FAIL LOUDLY if backend unavailable
    debugActionsService.loadActions()
      .catch(err => {
        frontendLoggingService.error('DebugControls', 'BACKEND API NOT AVAILABLE - DebugActionsService failed', err)
        frontendLoggingService.error('DebugControls', 'EXPECTED: Backend endpoint /api/v1/debug/actions must be implemented')
        throw err // Re-throw to make it visible
      })

    // Subscribe to action updates
    const unsubscribe = debugActionsService.subscribe((updatedActions) => {
      setActions(updatedActions)
      setIsLoading(false)
      frontendLoggingService.debug('DebugControls', 'Actions updated', {
        count: updatedActions.length
      })
    })

    // Subscribe to status updates
    const unsubscribeStatus = debugActionsService.subscribeToStatus((statuses) => {
      frontendLoggingService.debug('DebugControls', 'Status updated', statuses)
    })

    return () => {
      unsubscribe()
      unsubscribeStatus()
      frontendLoggingService.info('DebugControls', 'Component unmounted')
    }
  }, [])

  const executeAction = async (action: DebugAction) => {
    if (action.requiresConfirmation && !showConfirmation) {
      setSelectedAction(action)
      setShowConfirmation(true)
      return
    }

    const actionToExecute = selectedAction || action

    frontendLoggingService.info('DebugControls', 'Executing action', {
      actionId: actionToExecute.id,
      actionName: actionToExecute.name
    })

    try {
      const result = await debugActionsService.executeAction(actionToExecute.id)
      setActionResults(prev => ({ ...prev, [actionToExecute.id]: result }))
      onActionExecute?.(action)
      
      frontendLoggingService.info('DebugControls', 'Action executed', {
        actionId: actionToExecute.id,
        status: result.status
      })

      setShowConfirmation(false)
      setSelectedAction(null)
    } catch (error) {
      frontendLoggingService.error('DebugControls', 'Failed to execute action', error, {
        actionId: actionToExecute.id
      })
    }
  }

  const handleBreakpointToggle = () => {
    const newState = !breakpointsEnabled
    setBreakpointsEnabled(newState)
    onBreakpointToggle?.(newState)
    frontendLoggingService.debug('DebugControls', `Breakpoints ${newState ? 'enabled' : 'disabled'}`)
  }

  const getStatusColor = (status: DebugActionStatus) => {
    switch (status) {
      case 'running': return 'badge-warning badge-outline'
      case 'completed': return 'badge-success badge-outline'
      case 'failed': return 'badge-error badge-outline'
      case 'cancelled': return 'badge-muted badge-outline'
      default: return 'badge-muted badge-outline'
    }
  }

  const getCategoryColor = (category: DebugAction['category']) => {
    switch (category) {
      case 'system': return 'badge-primary badge-outline'
      case 'performance': return 'badge-secondary badge-outline'
      case 'diagnostic': return 'badge-accent badge-outline'
      case 'maintenance': return 'badge-info badge-outline'
      default: return 'badge-muted badge-outline'
    }
  }

  const getActionIcon = (action: DebugAction) => {
    const status = debugActionsService.getActionStatus(action.id)
    if (action.dangerous) return '⚠️'
    if (status === 'running') return '🔄'
    if (status === 'completed') return '✅'
    if (status === 'failed') return '❌'
    if (status === 'cancelled') return '🚫'
    return '⚙️'
  }

  const groupedActions = actions.reduce((acc, action) => {
    if (!acc[action.category]) {
      acc[action.category] = []
    }
    acc[action.category].push(action)
    return acc
  }, {} as Record<string, DebugAction[]>)

  const getStatusSummary = () => {
    return actions.reduce((acc, action) => {
      const status = debugActionsService.getActionStatus(action.id)
      acc[status] = (acc[status] || 0) + 1
      return acc
    }, {} as Record<string, number>)
  }

  const statusSummary = getStatusSummary()

  if (isLoading) {
    return (
      <ErrorBoundary>
        <div className="card bg-base-200 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
          <div className="card-body gap-[var(--card-gap)]">
            <h2 className="card-title">Debug Controls</h2>
            <div className="flex items-center justify-center py-8">
              <span className="loading loading-spinner loading-md"></span>
              <span className="ml-3">Loading actions...</span>
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
            <h2 className="card-title">Debug Controls</h2>
            <span className="badge badge-warning badge-outline">Mock Actions - Coming Soon</span>
          </div>
          <div className="alert alert-warning py-2">
            <span className="text-xs">⚠️ Actions execute with simulated results. Real backend integration planned.</span>
          </div>

          {/* Breakpoint Controls */}
          <div className="mb-6">
            <div className="flex items-center justify-between p-4 bg-base-100 rounded-lg">
              <div>
                <h3 className="font-semibold">Debug Breakpoints</h3>
                <p className="text-sm text-readout">
                  Enable/disable debugging breakpoints for code inspection
                </p>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-sm">
                  {breakpointsEnabled ? 'Enabled' : 'Disabled'}
                </span>
                <input
                  type="checkbox"
                  className="toggle toggle-primary"
                  checked={breakpointsEnabled}
                  onChange={handleBreakpointToggle}
                />
              </div>
            </div>
          </div>

          {/* Debug Actions by Category */}
          <div className="space-y-6">
            {actions.length === 0 ? (
              <div className="text-center py-8 text-readout">
                <p>No debug actions available. Backend integration required.</p>
              </div>
            ) : (
              Object.entries(groupedActions).map(([category, categoryActions]) => (
                <div key={category}>
                  <h3 className="font-semibold text-lg mb-3 capitalize">{category} Actions</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {categoryActions.map(action => {
                      const status = debugActionsService.getActionStatus(action.id)
                      const result = actionResults[action.id]
                      
                      return (
                        <div key={action.id} className="card bg-base-100 shadow-sm shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
                          <div className="card-body p-[var(--card-padding)]">
                            <div className="flex items-start justify-between mb-2">
                              <div className="flex items-center gap-2">
                                <span className="text-lg">{getActionIcon(action)}</span>
                                <h4 className="font-medium">{action.name}</h4>
                              </div>
                              <div className="flex gap-2">
                                <span className={`badge ${getCategoryColor(action.category)}`}>
                                  {action.category}
                                </span>
                                <span className={`badge ${getStatusColor(status)}`}>
                                  {status}
                                </span>
                              </div>
                            </div>

                            <p className="text-sm text-readout mb-3">
                              {action.description}
                            </p>

                            {result && (
                              <div className={`alert alert-${result.status === 'completed' ? 'success' : 'error'} py-2 mb-3`}>
                                <span className="text-xs">{result.message}</span>
                              </div>
                            )}

                            <div className="flex justify-between items-center">
                              <div className="flex gap-1">
                                {action.dangerous && (
                                  <span className="badge badge-warning badge-outline">Dangerous</span>
                                )}
                                {action.requiresConfirmation && (
                                  <span className="badge badge-outline">Confirmation Required</span>
                                )}
                                {!action.enabled && (
                                  <span className="badge badge-muted badge-outline">Not Implemented</span>
                                )}
                              </div>

                              <button
                                className={`btn btn-sm rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)] ${
                                  action.dangerous ? 'btn-error' : 'btn-primary'
                                } ${status === 'running' || !action.enabled ? 'btn-disabled' : ''}`}
                                onClick={() => executeAction(action)}
                                disabled={status === 'running' || !action.enabled}
                              >
                                {status === 'running' ? (
                                  <>
                                    <span className="loading loading-spinner loading-xs"></span>
                                    Running
                                  </>
                                ) : (
                                  'Execute'
                                )}
                              </button>
                            </div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Confirmation Modal */}
          {showConfirmation && selectedAction && (
            <div className="modal modal-open">
              <div className="modal-box">
                <h3 className="font-bold text-lg mb-4">Confirm Action</h3>

                <div className="space-y-4">
                  <div className="alert alert-warning">
                    <span>⚠️ Warning: This action may have significant consequences.</span>
                  </div>

                  <div>
                    <label className="label">
                      <span className="label-text font-semibold">Action</span>
                    </label>
                    <p>{selectedAction.name}</p>
                  </div>

                  <div>
                    <label className="label">
                      <span className="label-text font-semibold">Description</span>
                    </label>
                    <p>{selectedAction.description}</p>
                  </div>

                  <div>
                    <label className="label">
                      <span className="label-text font-semibold">Impact</span>
                    </label>
                    <p className="text-warning">
                      {selectedAction.dangerous
                        ? 'This action is dangerous and may cause system instability or data loss.'
                        : 'This action requires confirmation before proceeding.'
                      }
                    </p>
                  </div>
                </div>

                <div className="modal-action">
                  <button
                    className="btn btn-error rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
                    onClick={() => executeAction(selectedAction)}
                  >
                    Confirm & Execute
                  </button>
                  <button
                    className="btn rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
                    onClick={() => {
                      setShowConfirmation(false)
                      setSelectedAction(null)
                    }}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Quick Actions Summary */}
          <div className="mt-6 p-4 bg-base-100 rounded-lg">
            <h3 className="font-semibold mb-3">Quick Actions Summary</h3>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm">
              <div className="text-center">
                <div className="stat-value text-2xl">
                  {statusSummary['idle'] || 0}
                </div>
                <div className="stat-title">Ready</div>
              </div>

              <div className="text-center">
                <div className="stat-value text-2xl text-warning">
                  {statusSummary['running'] || 0}
                </div>
                <div className="stat-title">Running</div>
              </div>

              <div className="text-center">
                <div className="stat-value text-2xl text-success">
                  {statusSummary['completed'] || 0}
                </div>
                <div className="stat-title">Completed</div>
              </div>

              <div className="text-center">
                <div className="stat-value text-2xl text-error">
                  {statusSummary['failed'] || 0}
                </div>
                <div className="stat-title">Failed</div>
              </div>

              <div className="text-center">
                <div className="stat-value text-2xl text-neutral">
                  {statusSummary['cancelled'] || 0}
                </div>
                <div className="stat-title">Cancelled</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </ErrorBoundary>
  )
}
