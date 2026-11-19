import { useState } from 'react'
import { ErrorBoundary } from '../components/ErrorBoundary'
import { usePageTitle } from '../hooks/usePageTitle'
import { PageBanner } from '../components/ui/PageBanner'
import { type DiagnosticResult } from '../services/domain/SystemDiagnosticsService';
import { ErrorAnalysis } from '../components/features/debugging/ErrorAnalysis'
import { type ErrorEntry } from '../services/domain/ErrorTrackingService'
import { LogViewer, type LogFilters } from '../components/features/debugging/LogViewer'
import { DebugControls } from '../components/features/debugging/DebugControls'
import { type DebugAction } from '../services/domain/DebugActionsService'
import { LiveMonitoring } from '../components/features/debugging/LiveMonitoring'
import { TraceAnalysis } from '../components/features/debugging/TraceAnalysis'
import { TraceControls } from '../components/features/debugging/TraceControls'
import { DatabaseTools } from '../components/features/debugging/DatabaseTools'
import { frontendLoggingService } from '../services/frontendLoggingService'
import BackendTraceViewer from '../components/features/debugging/BackendTraceViewer'
import CognitiveTraceViewer from '../components/features/debugging/CognitiveTraceViewer'

/**
 * Debugging Page - Consolidated debugging and monitoring tools
 *
 * Phase 4 Consolidation (2026-03-07):
 * - Added tab navigation: Error Analysis, Debug Actions, Live Monitoring, Settings
 * - Live Monitoring tab contains functionality from deleted RealTimeMonitor page
 *
 * Trace Analysis Tab (2026-03-09):
 * - Added Trace Analysis as first/default tab
 * - Real-time trace log capture and display
 * - Filtering by flow, step, sequence range, and time
 * - Export to JSON/CSV formats
 */

export default function Debugging() {
  usePageTitle('Debugging', 'Advanced debugging and troubleshooting tools')
  
  const [activeTab, setActiveTab] = useState<'agent-traces' | 'cognitive' | 'errors' | 'actions' | 'monitoring' | 'settings' | 'database' | 'traces'>('agent-traces')
  const [_diagnosticResults, _setDiagnosticResults] = useState<DiagnosticResult[]>([])
  const [_activeErrors, _setActiveErrors] = useState<ErrorEntry[]>([])

  const handleErrorResolve = (errorId: string) => {
    frontendLoggingService.info('Debugging', `Error resolved: ${errorId}`)
    _setActiveErrors((prev: ErrorEntry[]) => prev.filter(error => error.id !== errorId))
  }

  const handleErrorIgnore = (errorId: string) => {
    frontendLoggingService.info('Debugging', `Error ignored: ${errorId}`)
    _setActiveErrors((prev: ErrorEntry[]) => prev.filter(error => error.id !== errorId))
  }

  const handleLogFilter = (filters: LogFilters) => {
    frontendLoggingService.debug('Debugging', 'Log filters applied', filters as unknown as Record<string, unknown>)
  }

  const handleLogExport = (format: 'json' | 'csv') => {
    frontendLoggingService.info('Debugging', `Exporting logs as ${format}`)
  }

  const handleActionExecute = (action: DebugAction) => {
    frontendLoggingService.info('Debugging', `Executing debug action: ${action.name}`)
  }

  const handleBreakpointToggle = (enabled: boolean) => {
    frontendLoggingService.debug('Debugging', `Breakpoints ${enabled ? 'enabled' : 'disabled'}`)
  }

  const handleTraceExport = (format: 'json' | 'csv') => {
    frontendLoggingService.info('Debugging', `Exporting traces as ${format}`)
  }

  const handleTraceConfigChange = (config: unknown) => {
    frontendLoggingService.info('Debugging', 'Trace configuration changed', config as Record<string, unknown>)
  }

  return (
    <ErrorBoundary>
      <div className="p-6 max-w-7xl mx-auto">
        <PageBanner
          title="Debugging"
          className="mb-8"
          tooltip="Advanced debugging and troubleshooting tools for system inspection. Analyze system state, debug requests, and diagnose performance issues."
        />

        {/* Tab Navigation */}
        <div className="tabs tabs-boxed mb-6">
          <button
            className={`tab ${activeTab === 'agent-traces' ? 'tab-active' : ''}`}
            onClick={() => setActiveTab('agent-traces')}
          >
            🤖 Agent Traces
          </button>
          <button
            className={`tab ${activeTab === 'cognitive' ? 'tab-active' : ''}`}
            onClick={() => setActiveTab('cognitive')}
          >
            🧠 Cognitive Traces
          </button>
          <button
            className={`tab ${activeTab === 'traces' ? 'tab-active' : ''}`}
            onClick={() => setActiveTab('traces')}
          >
            🔍 Trace Analysis
          </button>
          <button
            className={`tab ${activeTab === 'errors' ? 'tab-active' : ''}`}
            onClick={() => setActiveTab('errors')}
          >
            ⚠️ Error Analysis
          </button>
          <button
            className={`tab ${activeTab === 'actions' ? 'tab-active' : ''}`}
            onClick={() => setActiveTab('actions')}
          >
            ⚙️ Debug Actions
          </button>
          <button
            className={`tab ${activeTab === 'monitoring' ? 'tab-active' : ''}`}
            onClick={() => setActiveTab('monitoring')}
          >
            📊 Live Monitoring
          </button>
          <button
            className={`tab ${activeTab === 'settings' ? 'tab-active' : ''}`}
            onClick={() => setActiveTab('settings')}
          >
            ⚙️ Settings
          </button>
          <button
            className={`tab ${activeTab === 'database' ? 'tab-active' : ''}`}
            onClick={() => setActiveTab('database')}
          >
            🗄️ Database
          </button>
        </div>

        {/* Trace Analysis Tab */}
        {activeTab === 'traces' && (
          <div className="space-y-6">
            <TraceControls onConfigChange={handleTraceConfigChange} />
            <TraceAnalysis onExport={handleTraceExport} />
          </div>
        )}

        {/* Error Analysis Tab */}
        {activeTab === 'errors' && (
          <div className="space-y-6">
            <ErrorAnalysis
              onErrorResolve={handleErrorResolve}
              onErrorIgnore={handleErrorIgnore}
            />
          </div>
        )}

        {/* Debug Actions Tab */}
        {activeTab === 'actions' && (
          <div className="space-y-6">
            <DebugControls
              onActionExecute={handleActionExecute}
              onBreakpointToggle={handleBreakpointToggle}
            />
          </div>
        )}

        {/* Live Monitoring Tab - From RealTimeMonitor */}
        {activeTab === 'monitoring' && (
          <div className="space-y-6">
            <LiveMonitoring />
          </div>
        )}

        {/* Settings Tab - Log Viewer */}
        {activeTab === 'settings' && (
          <div className="space-y-6">
            <LogViewer
              onLogFilter={handleLogFilter}
              onLogExport={handleLogExport}
            />
          </div>
        )}

        {/* Database Tab - Tools for managing backend data */}
        {activeTab === 'database' && (
          <div className="space-y-6">
            <DatabaseTools />
          </div>
        )}
        {/* Cognitive Traces Tab */}
        {activeTab === 'cognitive' && (
          <div className="space-y-6">
            <CognitiveTraceViewer />
          </div>
        )}
        {activeTab === 'agent-traces' && (
          <div className="space-y-6">
            <BackendTraceViewer defaultSource="agent" title="Agent Request Traces" sourceLabel="Recent traces from the Agent Chat pipeline." />
          </div>
        )}
      </div>
    </ErrorBoundary>
  )
}
