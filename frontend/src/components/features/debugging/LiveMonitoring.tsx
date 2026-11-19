import { ErrorBoundary } from '@/components/ErrorBoundary'
import { useState, useEffect } from 'react'
import { frontendLoggingService } from '@/services/frontendLoggingService'
import { liveMonitoringService, type ActivityEvent, type MonitoringMetrics } from '@/services/domain/LiveMonitoringService'

/**
 * LiveMonitoring - Real-time activity monitoring
 * 
 * Phase 4 Consolidation (2026-03-07):
 * - Extracted from RealTimeMonitor.tsx (now deleted)
 * - Moved to Debugging page > Live Monitoring tab
 */

interface Session {
  id: string
  name: string
  status: 'active' | 'idle' | 'error' | 'completed'
  createdAt: string
  lastActivity: string
  agentCount: number
  workflowCount: number
  progress: number
}

export const LiveMonitoring: React.FC = () => {
  const [sessions, setSessions] = useState<Session[]>([])
  const [selectedSession, setSelectedSession] = useState<Session | null>(null)
  const [events, setEvents] = useState<ActivityEvent[]>([])
  const [metrics, setMetrics] = useState<MonitoringMetrics | null>(null)
  const [isMonitoring, setIsMonitoring] = useState(false)

  // Initialize with mock session data
  useEffect(() => {
    const mockSessions: Session[] = [
      {
        id: 'session-1',
        name: 'Research Workflow',
        status: 'active',
        createdAt: '2024-01-15T10:30:00Z',
        lastActivity: new Date().toISOString(),
        agentCount: 3,
        workflowCount: 1,
        progress: 75,
      },
      {
        id: 'session-2',
        name: 'Document Analysis',
        status: 'idle',
        createdAt: '2024-01-15T09:15:00Z',
        lastActivity: new Date().toISOString(),
        agentCount: 2,
        workflowCount: 1,
        progress: 100,
      },
      {
        id: 'session-3',
        name: 'Code Review',
        status: 'error',
        createdAt: '2024-01-15T08:00:00Z',
        lastActivity: new Date().toISOString(),
        agentCount: 1,
        workflowCount: 1,
        progress: 45,
      },
    ]
    setSessions(mockSessions)
  }, [])

  // Subscribe to live monitoring events
  useEffect(() => {
    frontendLoggingService.info('LiveMonitoring', 'Component mounted')

    // Start monitoring service
    liveMonitoringService.start()
    setIsMonitoring(true)

    // Subscribe to events
    const unsubscribeEvents = liveMonitoringService.subscribe((event) => {
      setEvents(prev => [event, ...prev].slice(0, 100)) // Keep last 100 events
      frontendLoggingService.debug('LiveMonitoring', 'New event received', {
        type: event.type,
        source: event.source
      })
    })

    // Subscribe to metrics
    const unsubscribeMetrics = liveMonitoringService.subscribeToMetrics((newMetrics) => {
      setMetrics(newMetrics)
      frontendLoggingService.debug('LiveMonitoring', 'Metrics updated', {
        rps: newMetrics.requestsPerSecond
      })
    })

    return () => {
      unsubscribeEvents()
      unsubscribeMetrics()
      liveMonitoringService.stop()
      setIsMonitoring(false)
      frontendLoggingService.info('LiveMonitoring', 'Component unmounted')
    }
  }, [])

  const handleSessionSelect = (session: Session) => {
    frontendLoggingService.debug('LiveMonitoring', 'Session selected', { 
      sessionId: session.id, 
      sessionName: session.name 
    })
    setSelectedSession(session)
  }

  const handleSessionTerminate = (sessionId: string) => {
    frontendLoggingService.info('LiveMonitoring', 'Terminating session', { sessionId })
    setSessions(prev => prev.map(session =>
      session.id === sessionId
        ? { ...session, status: 'completed' as const }
        : session
    ))
  }

  const getStatusColor = (status: Session['status']) => {
    switch (status) {
      case 'active': return 'badge-success badge-outline'
      case 'idle': return 'badge-warning badge-outline'
      case 'error': return 'badge-error badge-outline'
      case 'completed': return 'badge-muted badge-outline'
      default: return 'badge-muted badge-outline'
    }
  }

  const activeSessions = sessions.filter(s => s.status === 'active').length

  return (
    <ErrorBoundary>
      <div className="space-y-6">
        {/* Monitoring Status Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold">Live Monitoring</h2>
            <div className={`badge ${isMonitoring ? 'badge-success badge-outline' : 'badge-muted badge-outline'} gap-2`}>
              {isMonitoring ? '●' : '○'} {isMonitoring ? 'Live' : 'Stopped'}
            </div>
          </div>
          <div className="text-sm text-readout">
            {events.length} events • {activeSessions} active sessions
          </div>
        </div>

        {/* Metrics Overview */}
        {metrics && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="stat bg-base-100 rounded-lg p-4">
              <div className="stat-title">Requests/sec</div>
              <div className="stat-value text-2xl">{metrics.requestsPerSecond}</div>
            </div>
            <div className="stat bg-base-100 rounded-lg p-4">
              <div className="stat-title">Errors/sec</div>
              <div className="stat-value text-2xl text-error">{metrics.errorsPerSecond}</div>
            </div>
            <div className="stat bg-base-100 rounded-lg p-4">
              <div className="stat-title">Connections</div>
              <div className="stat-value text-2xl">{metrics.activeConnections}</div>
            </div>
            <div className="stat bg-base-100 rounded-lg p-4">
              <div className="stat-title">Avg Response</div>
              <div className="stat-value text-2xl">{metrics.avgResponseTime}ms</div>
            </div>
          </div>
        )}

        {/* Sessions and Events Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Active Sessions */}
          <div className="card bg-base-200 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
            <div className="card-body gap-[var(--card-gap)]">
              <h3 className="card-title">Active Sessions</h3>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {sessions.map(session => (
                  <div
                    key={session.id}
                    className={`card bg-base-100 shadow-sm cursor-pointer transition-colors ${
                      selectedSession?.id === session.id ? 'ring-2 ring-primary' : 'hover:bg-base-300'
                    }`}
                    onClick={() => handleSessionSelect(session)}
                  >
                    <div className="card-body p-3">
                      <div className="flex items-center justify-between">
                        <div>
                          <h4 className="font-medium">{session.name}</h4>
                          <div className="text-xs text-readout">
                            {session.agentCount} agents • {session.workflowCount} workflows
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={`badge ${getStatusColor(session.status)}`}>
                            {session.status}
                          </span>
                          <span className="text-xs">{session.progress}%</span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Live Events Feed */}
          <div className="card bg-base-200 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
            <div className="card-body gap-[var(--card-gap)]">
              <h3 className="card-title">Live Events</h3>
              <div className="space-y-2 max-h-96 overflow-y-auto font-mono text-sm">
                {events.length === 0 ? (
                  <div className="text-center py-8 text-readout">
                    Waiting for events...
                  </div>
                ) : (
                  events.map((event, index) => (
                    <div key={event.id || index} className="flex items-start gap-2">
                      <span className="text-xs text-readout whitespace-nowrap">
                        {new Date(event.timestamp).toLocaleTimeString()}
                      </span>
                      <span className={`badge badge-xs ${
                        event.type === 'error' ? 'badge-error badge-outline' :
                        'badge-info badge-outline'
                      }`}>
                        {event.type}
                      </span>
                      <span className="flex-1">{event.message}</span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Session Details (if selected) */}
        {selectedSession && (
          <div className="card bg-base-200 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
            <div className="card-body gap-[var(--card-gap)]">
              <div className="flex items-center justify-between">
                <h3 className="card-title">Session Details: {selectedSession.name}</h3>
                <button
                  className="btn btn-sm btn-ghost"
                  onClick={() => setSelectedSession(null)}
                >
                  ✕ Close
                </button>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <div className="text-sm text-readout">Status</div>
                  <div className={`badge ${getStatusColor(selectedSession.status)}`}>
                    {selectedSession.status}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-readout">Progress</div>
                  <div className="text-lg font-bold">{selectedSession.progress}%</div>
                </div>
                <div>
                  <div className="text-sm text-readout">Agents</div>
                  <div className="text-lg font-bold">{selectedSession.agentCount}</div>
                </div>
                <div>
                  <div className="text-sm text-readout">Workflows</div>
                  <div className="text-lg font-bold">{selectedSession.workflowCount}</div>
                </div>
              </div>
              {selectedSession.status === 'active' && (
                <div className="flex gap-2">
                  <button
                    className="btn btn-error btn-sm"
                    onClick={() => handleSessionTerminate(selectedSession.id)}
                  >
                    Terminate Session
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </ErrorBoundary>
  )
}
