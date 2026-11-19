import { API_BASE_URL } from '@/services/apiClient';
import { useState, useEffect, useRef } from 'react'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { frontendLoggingService } from '@/services/frontendLoggingService'
import { type TraceTag } from '@/services/domain/TraceService';

interface TraceAnalysisProps {
  onExport?: (format: 'json' | 'csv') => void
  refreshInterval?: number
  initialLimit?: number
}

interface TraceEntry {
  sequence: number
  timestamp: string
  flow: string
  step: string
  message: string
  context: Record<string, unknown>
  tags?: TraceTag[]
  perfTime?: number  // High-precision time in ms since page load
}

interface TraceFilters {
  flowName?: string
  sequenceFrom?: number
  sequenceTo?: number
  stepSearch?: string
  timeFrom?: string
  timeTo?: string
  selectedTags?: TraceTag[]
  includeText?: string  // Include traces containing this text (comma-delimited, OR logic)
  excludeText?: string  // Exclude traces containing this text (comma-delimited, OR logic)
  includePreset?: string  // Selected preset inclusion pattern
}

/** Preset inclusion patterns for focusing on specific trace types */
const INCLUDE_PRESETS: { label: string; value: string; description: string }[] = [
  {
    label: '💬 Chat Flows',
    value: 'ChatFlow',
    description: 'Show only chat flow traces'
  },
  {
    label: '👤 Session Flows',
    value: 'SessionFlow, SessionService',
    description: 'Show session management traces'
  },
  {
    label: '🤖 Agent Flows',
    value: 'AgentFlow, AgentService',
    description: 'Show agent-related traces'
  },
  {
    label: '⚠️ Errors Only',
    value: 'error',
    description: 'Show traces with errors'
  }
]

/** Preset exclusion patterns for filtering common background noise */
const EXCLUDE_PRESETS: { label: string; value: string; description: string }[] = [
  {
    label: '🔇 System Noise',
    value: 'SystemDiagnosticsService, LogManagementService, TraceAnalysis',
    description: 'Hide system monitoring and self-traces'
  },
  {
    label: '🔇 Background Tasks',
    value: 'background sync, loadTraces:success',
    description: 'Hide background operations'
  },
  {
    label: '🔇 Notifications',
    value: 'notifying, metrics:notified, subscribers',
    description: 'Hide notification traces'
  },
  {
    label: '🔇 All Noise (Recommended)',
    value: 'SystemDiagnosticsService, LogManagementService, TraceAnalysis, background sync, loadTraces:success, notifying, metrics:notified, subscribers',
    description: 'Hide all system noise - focus on business logic'
  }
]

const ALL_TAGS: TraceTag[] = [
  'lifecycle',
  'data',
  'api-call',
  'streaming',
  'error',
  'performance',
  'user-action',
  'state-change',
  'validation',
  'cache',
  'sync'
]

export const TraceAnalysis: React.FC<TraceAnalysisProps> = ({
  onExport,
  refreshInterval = 2000,
  initialLimit = 500
}) => {
  const [traces, setTraces] = useState<TraceEntry[]>([])
  const [filters, setFilters] = useState<TraceFilters>({})
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [expandedTraces, setExpandedTraces] = useState<Set<number>>(new Set())
  const [stats, setStats] = useState<{
    total: number
    byFlow: Record<string, number>
    byTag: Record<string, number>
    timeRange?: { start: string; end: string }
  }>({ total: 0, byFlow: {}, byTag: {} })

  const isVisible = useRef(true)

  // Load initial traces
  useEffect(() => {
    loadTraces()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Auto-refresh when tab is visible
  useEffect(() => {
    if (!autoRefresh) return

    const interval = setInterval(() => {
      if (isVisible.current) {
        loadTraces(true)
      }
    }, refreshInterval)

    return () => clearInterval(interval)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoRefresh, refreshInterval])

  // Visibility observer - only refresh when tab is visible
  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        isVisible.current = entry.isIntersecting
      },
      { threshold: 0 }
    )

    const element = document.getElementById('trace-analysis-container')
    if (element) {
      observer.observe(element)
    }

    return () => observer.disconnect()
  }, [])

  const loadTraces = async (silent = false) => {
    if (!silent) {
      setIsRefreshing(true)
    }

    try {
      const baseUrl = API_BASE_URL
      const response = await fetch(
        `${baseUrl}/api/v1/logs/recent?n=${initialLimit}&source=FlowTrace`
      )

      if (!response.ok) {
        throw new Error(`Failed to load traces: ${response.statusText}`)
      }

      const logs = await response.json()

      // Transform logs to trace entries
      const traceEntries: TraceEntry[] = logs.map((log: Record<string, unknown>) => {
        const context = (log.context || {}) as Record<string, unknown>
        const sequence = (context.sequence as number) || 0
        const tags = (context.tags as string[]) || []

        // Extract flow and step from message
        let flow = 'Unknown'
        let step = 'Unknown'
        const message = (log.message as string) || ''

        if (message.includes('] ')) {
          const afterPrefix = message.split('] ')[1]
          if (afterPrefix && afterPrefix.includes(':')) {
            const parts = afterPrefix.split(':')
            flow = parts[0]
            step = parts[1].split('(')[0]
          }
        }

        return {
          sequence,
          timestamp: log.timestamp,
          flow,
          step,
          message: log.message,
          context,
          tags
        }
      })

      // Sort by sequence
      traceEntries.sort((a, b) => a.sequence - b.sequence)

      setTraces(traceEntries)
      calculateStats(traceEntries)

      // traceService.trace('TraceAnalysis', 'loadTraces:success', {
        // count: traceEntries.length
      // }, ['lifecycle', 'api-call', 'sync'])

      // TODO: Re-enable this log when needed - currently clogs logs.txt
      // frontendLoggingService.info('TraceAnalysis', 'Traces loaded', {
      //   count: traceEntries.length
      // })
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error)
      frontendLoggingService.error('TraceAnalysis', 'Failed to load traces', {
        error: errorMessage
      })

      // traceService.trace('TraceAnalysis', 'loadTraces:error', {
        // error: errorMessage
      // }, ['error'])
    } finally {
      setIsLoading(false)
      setIsRefreshing(false)
    }
  }

  const calculateStats = (traceList: TraceEntry[]) => {
    const byFlow: Record<string, number> = {}
    const byTag: Record<string, number> = {}

    traceList.forEach(trace => {
      byFlow[trace.flow] = (byFlow[trace.flow] || 0) + 1

      // Count tags
      if (trace.tags && trace.tags.length > 0) {
        trace.tags.forEach(tag => {
          byTag[tag] = (byTag[tag] || 0) + 1
        })
      }
    })

    const timeRange = traceList.length > 0
      ? {
          start: traceList[0].timestamp,
          end: traceList[traceList.length - 1].timestamp
        }
      : undefined

    setStats({
      total: traceList.length,
      byFlow,
      byTag,
      timeRange
    })
  }

  const handleExport = async (format: 'json' | 'csv') => {
    try {
      frontendLoggingService.info('TraceAnalysis', `Exporting traces as ${format}`)

      // Build export URL with current filters
      const params = new URLSearchParams()
      params.append('format', format)
      params.append('limit', String(traces.length))

      if (filters.flowName) {
        params.append('flow', filters.flowName)
      }

      // Use fetch directly for blob response
      const baseUrl = API_BASE_URL
      const url = `${baseUrl}/api/v1/logs/traces/export?${params.toString()}`
      
      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json'
        }
      })

      if (!response.ok) {
        throw new Error(`Export failed: ${response.statusText}`)
      }

      const blob = await response.blob()

      // Create download link
      const downloadUrl = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = downloadUrl
      a.download = `traces-export-${new Date().toISOString().split('T')[0]}.${format}`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(downloadUrl)

      onExport?.(format)
      frontendLoggingService.info('TraceAnalysis', 'Traces exported successfully')
    } catch (error) {
      frontendLoggingService.error('TraceAnalysis', 'Failed to export traces', error)
    }
  }

  const handleCopyContext = (context: Record<string, unknown>) => {
    navigator.clipboard.writeText(JSON.stringify(context, null, 2))
    frontendLoggingService.info('TraceAnalysis', 'Context copied to clipboard')
  }

  const handleCopyTrace = (trace: TraceEntry) => {
    navigator.clipboard.writeText(JSON.stringify(trace, null, 2))
    frontendLoggingService.info('TraceAnalysis', 'Trace copied to clipboard')
  }

  const toggleExpand = (sequence: number) => {
    setExpandedTraces(prev => {
      const next = new Set(prev)
      if (next.has(sequence)) {
        next.delete(sequence)
      } else {
        next.add(sequence)
      }
      return next
    })
  }

  const clearFilters = () => {
    setFilters({})
    frontendLoggingService.debug('TraceAnalysis', 'Filters cleared')
  }

  const handleIncludePresetChange = (presetValue: string) => {
    const preset = INCLUDE_PRESETS.find(p => p.value === presetValue)
    if (preset) {
      setFilters({ 
        ...filters, 
        includePreset: presetValue,
        includeText: presetValue 
      })
      frontendLoggingService.debug('TraceAnalysis', `Applied include preset: ${preset.label}`)
    }
  }

  const handleExcludePresetChange = (presetValue: string) => {
    const preset = EXCLUDE_PRESETS.find(p => p.value === presetValue)
    if (preset) {
      setFilters({ 
        ...filters, 
        excludeText: presetValue 
      })
      frontendLoggingService.debug('TraceAnalysis', `Applied exclude preset: ${preset.label}`)
    }
  }

  const filteredTraces = traces.filter(trace => {
    // Filter by flow name
    if (filters.flowName && !trace.flow.toLowerCase().includes(filters.flowName.toLowerCase())) {
      return false
    }

    // Filter by sequence range
    if (filters.sequenceFrom !== undefined && trace.sequence < filters.sequenceFrom) {
      return false
    }
    if (filters.sequenceTo !== undefined && trace.sequence > filters.sequenceTo) {
      return false
    }

    // Filter by step search
    if (filters.stepSearch && !trace.step.toLowerCase().includes(filters.stepSearch.toLowerCase())) {
      return false
    }

    // Filter by include text - search in message, flow, and step
    // Supports comma-delimited list with OR logic (matches ANY term)
    if (filters.includeText) {
      const includeTerms = filters.includeText
        .split(',')
        .map(term => term.trim().toLowerCase())
        .filter(term => term.length > 0)
      
      if (includeTerms.length > 0) {
        const messageLower = trace.message?.toLowerCase() || ''
        const flowLower = trace.flow.toLowerCase()
        const stepLower = trace.step.toLowerCase()
        
        const matchesAnyTerm = includeTerms.some(term =>
          messageLower.includes(term) || flowLower.includes(term) || stepLower.includes(term)
        )
        
        if (!matchesAnyTerm) {
          return false
        }
      }
    }

    // Filter by exclude text - exclude if found in message, flow, or step
    // Supports comma-delimited list with OR logic (excludes if ANY term matches)
    if (filters.excludeText) {
      const excludeTerms = filters.excludeText
        .split(',')
        .map(term => term.trim().toLowerCase())
        .filter(term => term.length > 0)
      
      if (excludeTerms.length > 0) {
        const messageLower = trace.message?.toLowerCase() || ''
        const flowLower = trace.flow.toLowerCase()
        const stepLower = trace.step.toLowerCase()
        
        const matchesAnyTerm = excludeTerms.some(term =>
          messageLower.includes(term) || flowLower.includes(term) || stepLower.includes(term)
        )
        
        if (matchesAnyTerm) {
          return false
        }
      }
    }

    // Filter by tags - if tags are selected, only show traces with matching tags
    if (filters.selectedTags && filters.selectedTags.length > 0) {
      // If trace has no tags, it cannot match
      if (!trace.tags || trace.tags.length === 0) {
        return false
      }
      // Show trace if it has ANY of the selected tags
      const hasMatchingTag = trace.tags.some(tag => filters.selectedTags!.includes(tag))
      if (!hasMatchingTag) {
        return false
      }
    }

    // Filter by time range
    if (filters.timeFrom) {
      const traceTime = new Date(trace.timestamp).getTime()
      const fromTime = new Date(filters.timeFrom).getTime()
      if (traceTime < fromTime) return false
    }
    if (filters.timeTo) {
      const traceTime = new Date(trace.timestamp).getTime()
      const toTime = new Date(filters.timeTo).getTime()
      if (traceTime > toTime) return false
    }

    return true
  })

  // Debug log for tag filtering
  if (filters.selectedTags && filters.selectedTags.length > 0) {
    console.log('[TraceAnalysis] Tag filter active:', {
      selectedTags: filters.selectedTags,
      totalTraces: traces.length,
      filteredCount: filteredTraces.length,
      tracesWithTags: traces.filter(t => t.tags && t.tags.length > 0).length
    })
  }

  const formatTime = (timestamp: string) => {
    try {
      return new Date(timestamp).toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        fractionalSecondDigits: 3
      })
    } catch {
      return timestamp
    }
  }

  const getTimeAgo = (timestamp: string) => {
    try {
      const diff = Date.now() - new Date(timestamp).getTime()
      const seconds = Math.floor(diff / 1000)
      const minutes = Math.floor(seconds / 60)
      const hours = Math.floor(minutes / 60)

      if (hours > 0) return `${hours}h ago`
      if (minutes > 0) return `${minutes}m ago`
      return `${seconds}s ago`
    } catch {
      return ''
    }
  }

  /**
   * Calculate delta time from previous trace
   * @param trace - Current trace
   * @param index - Index in filtered list
   * @returns Delta in ms with formatted string
   */
  const getDeltaFromPrevious = (trace: TraceEntry, index: number): string => {
    if (index === 0 || trace.perfTime === undefined) return ''

    const prevTrace = filteredTraces[index - 1]
    if (!prevTrace || prevTrace.perfTime === undefined) return ''

    const delta = trace.perfTime - prevTrace.perfTime
    if (delta < 1) return `${(delta * 1000).toFixed(0)}μs`
    if (delta < 1000) return `${delta.toFixed(1)}ms`
    return `${(delta / 1000).toFixed(2)}s`
  }

  if (isLoading) {
    return (
      <ErrorBoundary>
        <div className="card bg-base-200 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
          <div className="card-body gap-[var(--card-gap)]">
            <h2 className="card-title">Trace Analysis</h2>
            <div className="flex items-center justify-center py-8">
              <span className="loading loading-spinner loading-md"></span>
              <span className="ml-3">Loading traces...</span>
            </div>
          </div>
        </div>
      </ErrorBoundary>
    )
  }

  return (
    <ErrorBoundary>
      <div id="trace-analysis-container" className="card bg-base-200 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
        <div className="card-body gap-[var(--card-gap)]">
          {/* Header */}
          <div className="flex items-center justify-between">
            <h2 className="card-title">Trace Analysis</h2>
            <div className="flex gap-2">
              <span className="tooltip tooltip-bottom" data-tip={autoRefresh ? 'Auto-refresh enabled' : 'Auto-refresh disabled'}>
              <button
                className={`btn btn-sm ${autoRefresh ? 'btn-active btn-selected' : 'btn-outline'}`}
                onClick={() => setAutoRefresh(!autoRefresh)}
              >
                Auto
              </button>
              </span>
              <span className="tooltip tooltip-bottom" data-tip="Refresh traces">
              <button
                className="btn btn-sm btn-outline"
                onClick={() => loadTraces()}
                disabled={isRefreshing}
              >
                {isRefreshing ? (
                  <span className="loading loading-spinner loading-sm"></span>
                ) : (
                  'Refresh'
                )}
              </button>
              </span>
            </div>
          </div>

          {/* Quick Filters - Always Visible */}
          <div className="flex flex-wrap gap-2 items-center">
            <div className="tooltip" data-tip="Filter by flow name">
              <input
                type="text"
                className="input input-bordered input-sm w-48 rounded-[var(--form-input-radius)] px-[var(--form-input-padding)]"
                placeholder="Flow name..."
                value={filters.flowName || ''}
                onChange={(e) => setFilters({ ...filters, flowName: e.target.value })}
              />
            </div>

            <div className="tooltip" data-tip="Search by step name">
              <input
                type="text"
                className="input input-bordered input-sm w-48 rounded-[var(--form-input-radius)] px-[var(--form-input-padding)]"
                placeholder="Step..."
                value={filters.stepSearch || ''}
                onChange={(e) => setFilters({ ...filters, stepSearch: e.target.value })}
              />
            </div>

            <button
              className="btn btn-sm btn-outline tooltip rounded-[var(--button-radius)] px-[var(--button-padding)]"
              onClick={clearFilters}
              data-tip="Remove all filters"
            >
              Clear Filters
            </button>

            <span className="text-sm text-readout ml-auto">
              Showing {filteredTraces.length} of {traces.length} traces
            </span>
          </div>

          {/* Advanced Filters - Collapsible */}
          <details className="collapse collapse-arrow bg-base-100 rounded-[var(--card-radius)]">
            <summary className="collapse-title text-sm font-medium cursor-pointer">
              🔧 Advanced Filters (Include/Exclude, Tags, Sequence, Time)
            </summary>
            <div className="collapse-content space-y-4">
              {/* Include/Exclude Presets - Quick Access */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="tooltip" data-tip="Focus on specific flow types">
                  <div className="form-control">
                    <label className="label cursor-pointer">
                      <span className="label-text text-xs">💡 Include Preset:</span>
                      <select
                        className="select select-bordered select-sm w-full max-w-xs"
                        value={filters.includePreset || ''}
                        onChange={(e) => handleIncludePresetChange(e.target.value)}
                      >
                        <option value="">Select...</option>
                        {INCLUDE_PRESETS.map(preset => (
                          <option key={preset.value} value={preset.value}>
                            {preset.label}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                </div>

                <div className="tooltip" data-tip="Hide system noise">
                  <div className="form-control">
                    <label className="label cursor-pointer">
                      <span className="label-text text-xs">🔇 Exclude Preset:</span>
                      <select
                        className="select select-bordered select-sm w-full max-w-xs"
                        value={filters.excludeText || ''}
                        onChange={(e) => handleExcludePresetChange(e.target.value)}
                      >
                        <option value="">Select...</option>
                        {EXCLUDE_PRESETS.map(preset => (
                          <option key={preset.value} value={preset.value}>
                            {preset.label}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                </div>
              </div>

              {/* Include/Exclude Text Inputs */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="tooltip" data-tip="Only show traces containing this text (comma-delimited, OR logic)">
                  <div className="form-control">
                    <label className="label">
                      <span className="label-text text-xs">Include (text or comma-separated):</span>
                    </label>
                    <input
                      type="text"
                      className="input input-bordered input-sm w-full rounded-[var(--form-input-radius)] px-[var(--form-input-padding)]"
                      placeholder="e.g., ChatFlow, error"
                      value={filters.includeText || ''}
                      onChange={(e) => setFilters({ ...filters, includeText: e.target.value })}
                    />
                  </div>
                </div>

                <div className="tooltip" data-tip="Exclude traces containing this text (comma-delimited, OR logic)">
                  <div className="form-control">
                    <label className="label">
                      <span className="label-text text-xs">Exclude (text or comma-separated):</span>
                    </label>
                    <input
                      type="text"
                      className="input input-bordered input-sm w-full rounded-[var(--form-input-radius)] px-[var(--form-input-padding)]"
                      placeholder="e.g., background, SystemDiagnostics"
                      value={filters.excludeText || ''}
                      onChange={(e) => setFilters({ ...filters, excludeText: e.target.value })}
                    />
                  </div>
                </div>
              </div>

              {/* Sequence Range */}
              <div>
                <span className="text-xs text-readout">Sequence Range:</span>
                <div className="flex items-center gap-2 mt-1">
                  <input
                    type="number"
                    className="input input-bordered input-sm w-32 rounded-[var(--form-input-radius)] px-[var(--form-input-padding)]"
                    placeholder="From"
                    value={filters.sequenceFrom ?? ''}
                    onChange={(e) => setFilters({ ...filters, sequenceFrom: e.target.value ? parseInt(e.target.value) : undefined })}
                  />
                  <span className="text-readout">-</span>
                  <input
                    type="number"
                    className="input input-bordered input-sm w-32 rounded-[var(--form-input-radius)] px-[var(--form-input-padding)]"
                    placeholder="To"
                    value={filters.sequenceTo ?? ''}
                    onChange={(e) => setFilters({ ...filters, sequenceTo: e.target.value ? parseInt(e.target.value) : undefined })}
                  />
                </div>
              </div>

              {/* Tag Filters */}
              <div>
                <span className="text-xs text-readout block mb-2">Filter by Tags:</span>
                <div className="flex flex-wrap gap-1">
                  {ALL_TAGS.map(tag => {
                    const isSelected = (filters.selectedTags || []).includes(tag)
                    const count = stats.byTag[tag] || 0
                    return (
                      <button
                        key={tag}
                        className={`btn btn-xs rounded-[var(--button-radius)] ${
                          isSelected ? 'btn-active btn-selected' : 'btn-outline'
                        }`}
                        onClick={() => {
                          const currentTags = filters.selectedTags || []
                          const newTags = isSelected
                            ? currentTags.filter(t => t !== tag)
                            : [...currentTags, tag]
                          setFilters({ ...filters, selectedTags: newTags.length > 0 ? newTags : undefined })
                        }}
                      >
                        {tag} {count > 0 && <span className="ml-1 opacity-70">({count})</span>}
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* Export Buttons */}
              <div className="pt-2 border-t border-base-300">
                <span className="text-xs text-readout block mb-2">Export:</span>
                <div className="flex gap-2">
                  <button
                    className="btn btn-sm btn-outline"
                    onClick={() => handleExport('json')}
                  >
                    📥 Export JSON
                  </button>
                  <button
                    className="btn btn-sm btn-outline"
                    onClick={() => handleExport('csv')}
                  >
                    📥 Export CSV
                  </button>
                </div>
              </div>
            </div>
          </details>

          {/* Stats Summary */}
          <div className="flex items-center gap-4 text-sm">
            <span className="text-readout">
              <strong>{filteredTraces.length}</strong> of <strong>{traces.length}</strong> traces
            </span>
            {Object.entries(stats.byFlow).slice(0, 4).map(([flow, count]) => (
              <span key={flow} className="text-xs text-readout">
                | <strong>{flow}:</strong> {count}
              </span>
            ))}
          </div>

          {/* Trace List */}
          <div className="space-y-2 max-h-[500px] overflow-y-auto">
            {filteredTraces.map((trace, index) => (
              <div
                key={trace.sequence}
                className="card bg-base-100 shadow-sm shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]"
              >
                <div className="card-body p-3">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <span className="badge badge-primary badge-outline">#{trace.sequence}</span>
                        <span className="font-mono text-sm font-bold">{trace.flow}:{trace.step}</span>
                        <span className="text-xs text-readout">
                          {formatTime(trace.timestamp)}
                        </span>
                        <span className="text-xs text-readout">
                          {getTimeAgo(trace.timestamp)}
                        </span>
                        {getDeltaFromPrevious(trace, index) && (
                          <span className="tooltip tooltip-top inline-block text-xs text-primary font-mono" data-tip="Time since previous trace">
                            +{getDeltaFromPrevious(trace, index)}
                          </span>
                        )}
                      </div>

                      <p className="text-sm text-readout">{trace.message}</p>

                      {trace.context && Object.keys(trace.context).length > 0 && (
                        <details
                          className="collapse collapse-arrow mt-2"
                          open={expandedTraces.has(trace.sequence)}
                        >
                          <summary
                            className="collapse-title text-xs font-medium cursor-pointer"
                            onClick={(e) => {
                              e.preventDefault()
                              toggleExpand(trace.sequence)
                            }}
                          >
                            Context ({Object.keys(trace.context).length} keys)
                          </summary>
                          <div className="collapse-content">
                            <div className="flex gap-2 mb-2">
                              <button
                                className="btn btn-xs btn-ghost"
                                onClick={() => handleCopyContext(trace.context)}
                              >
                                📋 Copy Context
                              </button>
                              <button
                                className="btn btn-xs btn-ghost"
                                onClick={() => handleCopyTrace(trace)}
                              >
                                📋 Copy Trace
                              </button>
                            </div>
                            <pre className="text-xs bg-base-300 p-2 rounded overflow-x-auto max-h-64 overflow-y-auto">
                              {JSON.stringify(trace.context, null, 2)}
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

          {filteredTraces.length === 0 && (
            <div className="text-center py-8 text-readout">
              <p>No traces found matching the current filters.</p>
              {traces.length === 0 && (
                <p className="mt-2 text-sm">Try sending a chat message to generate traces.</p>
              )}
            </div>
          )}
        </div>
      </div>
    </ErrorBoundary>
  )
}
