/**
 * CognitiveTraceViewer
 *
 * A comprehensive trace viewer for the cognitive pipeline. Provides:
 * - Real-time trace timeline via SSE stream
 * - Historical trace browser from the database
 * - Filter by component type (context_builder, executor, memory_manager, response_formatter)
 * - Per-step expand/collapse with detail view
 * - Trace summary metrics
 *
 * Part of Phase 4: Polish + Observability — Task 1: Cognitive Trace Viewer
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { frontendLoggingService } from '@/services/frontendLoggingService'

// ── Types ───────────────────────────────────────────────────────────────────

interface ComponentTraceData {
  strategy: string
  duration_ms: number
  tokens_used: number
  metadata: Record<string, unknown>
  error: string | null
}

interface CognitiveTraceCompleteData {
  trace: {
    context_builder: ComponentTraceData
    executor: ComponentTraceData
    memory_manager: ComponentTraceData
    response_formatter: ComponentTraceData
    total_duration_ms: number
    total_tokens: number
  }
  metrics: {
    total_duration_ms: number
    total_tokens: number
    llm_calls: number
    tool_calls: number
    cache_hits: number
  }
  memory_delta: {
    stored_keys: string[]
    evicted_keys: string[]
    compaction_triggered: boolean
  } | null
  error: string | null
}

interface TraceEntry {
  id: number
  session_id: number
  message_id: number | null
  trace: CognitiveTraceCompleteData['trace']
  metrics: CognitiveTraceCompleteData['metrics']
  memory_delta: CognitiveTraceCompleteData['memory_delta']
  error: string | null
  created_at: string
}

type ComponentName = 'context_builder' | 'executor' | 'memory_manager' | 'response_formatter'

const COMPONENT_LABELS: Record<ComponentName, string> = {
  context_builder: 'Context Builder',
  executor: 'Executor',
  memory_manager: 'Memory Manager',
  response_formatter: 'Response Formatter',
}

const COMPONENT_ICONS: Record<ComponentName, string> = {
  context_builder: '🔍',
  executor: '🧠',
  memory_manager: '💾',
  response_formatter: '✍️',
}

const COMPONENT_COLORS: Record<ComponentName, string> = {
  context_builder: 'text-info',
  executor: 'text-warning',
  memory_manager: 'text-secondary',
  response_formatter: 'text-accent',
}

const API_BASE = '/api/v1/agent-chat'

// ── Helpers ─────────────────────────────────────────────────────────────────

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${(ms / 60000).toFixed(1)}m`
}

function formatTimestamp(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function formatTokens(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(n)
}

// ── Sub-components ──────────────────────────────────────────────────────────

function ComponentStepCard({
  name,
  data,
  defaultExpanded,
}: {
  name: ComponentName
  data: ComponentTraceData
  defaultExpanded: boolean
}) {
  const [expanded, setExpanded] = useState(defaultExpanded)
  const color = COMPONENT_COLORS[name]
  const icon = COMPONENT_ICONS[name]
  const label = COMPONENT_LABELS[name]
  const hasError = data.error !== null && data.error !== undefined

  return (
    <div className={`border rounded-lg overflow-hidden transition-all duration-200 ${
      hasError ? 'border-error/30' : 'border-base-300'
    }`}>
      {/* Header (always visible) */}
      <button
        type="button"
        className={`flex items-center justify-between w-full px-3 py-2 text-sm transition-colors ${
          hasError ? 'bg-error/5 hover:bg-error/10' : 'hover:bg-base-300/50'
        }`}
        onClick={() => setExpanded((e) => !e)}
      >
        <div className="flex items-center gap-2 min-w-0">
          <span>{icon}</span>
          <span className={`font-medium ${color}`}>{label}</span>
          <span className="text-readout text-xs font-mono">
            {data.strategy}
          </span>
          {hasError && (
            <span className="tooltip tooltip-top inline-block text-error text-xs" data-tip={data.error!}>⚠</span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-readout text-xs font-mono">
            {formatDuration(data.duration_ms)}
          </span>
          {data.tokens_used > 0 && (
            <span className="text-readout text-xs font-mono">
              {formatTokens(data.tokens_used)} tok
            </span>
          )}
          <span className="text-readout text-xs">
            {expanded ? '▾' : '▸'}
          </span>
        </div>
      </button>

      {/* Expanded detail */}
      {expanded && (
        <div className="px-3 pb-3 pt-1 space-y-2">
          {/* Error display */}
          {hasError && (
            <div className="text-xs text-error font-mono bg-error/5 rounded p-2">
              Error: {data.error}
            </div>
          )}

          {/* Detail grid */}
          <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
            <DetailRow label="Strategy" value={data.strategy} />
            <DetailRow label="Duration" value={formatDuration(data.duration_ms)} />
            <DetailRow label="Tokens Used" value={String(data.tokens_used)} />
          </div>

          {/* Metadata */}
          {Object.keys(data.metadata).length > 0 && (
            <div>
              <div className="text-[10px] font-semibold text-readout mb-1 uppercase tracking-wider">
                Metadata
              </div>
              <pre className="text-[10px] font-mono bg-base-300/30 rounded p-2 overflow-x-auto max-h-32 overflow-y-auto text-readout">
                {JSON.stringify(data.metadata, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-readout w-24 shrink-0">{label}</span>
      <span className="font-mono text-readout truncate">{value}</span>
    </div>
  )
}

function TraceSummaryCard({ trace }: { trace: CognitiveTraceCompleteData }) {
  return (
    <div className="rounded-lg border border-base-300 bg-base-200/50 p-3 text-xs space-y-2">
      <div className="flex items-center justify-between">
        <span className="font-semibold text-readout flex items-center gap-1.5">
          <span>📊</span> Trace Summary
        </span>
        <span className="text-readout font-mono text-[10px]">
          {formatDuration(trace.trace.total_duration_ms)} total
        </span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <MetricBadge
          label="Total Duration"
          value={formatDuration(trace.trace.total_duration_ms)}
          color="text-info"
        />
        <MetricBadge
          label="Total Tokens"
          value={formatTokens(trace.trace.total_tokens)}
          color="text-primary"
        />
        <MetricBadge
          label="LLM Calls"
          value={String(trace.metrics.llm_calls)}
          color="text-warning"
        />
        <MetricBadge
          label="Tool Calls"
          value={String(trace.metrics.tool_calls)}
          color="text-accent"
        />
      </div>

      {trace.metrics.cache_hits > 0 && (
        <div className="text-[10px] text-readout">
          Cache hits: {trace.metrics.cache_hits}
        </div>
      )}

      {/* Memory delta */}
      {trace.memory_delta && (
        <div className="pt-1 border-t border-base-300">
          <div className="text-[10px] font-semibold text-readout mb-1">Memory Delta</div>
          <div className="flex flex-wrap gap-2 text-[10px] font-mono text-readout">
            {trace.memory_delta.stored_keys.length > 0 && (
              <span>Stored: {trace.memory_delta.stored_keys.join(', ')}</span>
            )}
            {trace.memory_delta.evicted_keys.length > 0 && (
              <span>Evicted: {trace.memory_delta.evicted_keys.join(', ')}</span>
            )}
            {trace.memory_delta.compaction_triggered && (
              <span className="text-warning">⚠ Compaction triggered</span>
            )}
          </div>
        </div>
      )}

      {/* Error */}
      {trace.error && (
        <div className="text-[10px] text-error font-mono pt-1 border-t border-base-300">
          Error: {trace.error}
        </div>
      )}
    </div>
  )
}

function MetricBadge({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="rounded bg-base-300/30 p-2 text-center">
      <div className={`text-lg font-bold font-mono ${color}`}>{value}</div>
      <div className="text-[10px] text-readout mt-0.5">{label}</div>
    </div>
  )
}

// ── Main Component ──────────────────────────────────────────────────────────

export default function CognitiveTraceViewer() {
  // Tab state
  const [activeTab, setActiveTab] = useState<'live' | 'history'>('live')

  // Live stream state
  const [liveEvents, setLiveEvents] = useState<CognitiveTraceCompleteData[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamError, setStreamError] = useState<string | null>(null)
  const eventSourceRef = useRef<EventSource | null>(null)

  // History state
  const [historyTraces, setHistoryTraces] = useState<TraceEntry[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyError, setHistoryError] = useState<string | null>(null)
  const [selectedTraceId, setSelectedTraceId] = useState<number | null>(null)

  // Filter state
  const [componentFilter, setComponentFilter] = useState<ComponentName | 'all'>('all')
  const [autoScroll, setAutoScroll] = useState(true)

  // ── Live SSE stream ─────────────────────────────────────────────────────

  const startStream = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }

    setIsStreaming(true)
    setStreamError(null)

    const es = new EventSource(`${API_BASE}/trace-stream`)
    eventSourceRef.current = es

    es.addEventListener('cognitive_trace_complete', (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data) as CognitiveTraceCompleteData
        setLiveEvents((prev) => {
          const updated = [...prev, data]
          // Keep last 100 events in memory
          return updated.slice(-100)
        })
      } catch (err) {
        frontendLoggingService.error('CognitiveTraceViewer', 'Failed to parse SSE event', err as Error)
      }
    })

    es.onerror = () => {
      setStreamError('SSE connection lost. Check if the backend is running.')
      setIsStreaming(false)
      es.close()
      eventSourceRef.current = null
    }

    es.onopen = () => {
      setIsStreaming(true)
      setStreamError(null)
    }
  }, [])

  const stopStream = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    setIsStreaming(false)
  }, [])

  // Auto-start stream on mount
  useEffect(() => {
    startStream()
    return () => {
      stopStream()
    }
  }, [startStream, stopStream])

  // ── History loading ─────────────────────────────────────────────────────

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true)
    setHistoryError(null)
    try {
      const res = await fetch(`${API_BASE}/session/traces?limit=50`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setHistoryTraces(data.traces || [])
    } catch (err) {
      setHistoryError(String(err))
    } finally {
      setHistoryLoading(false)
    }
  }, [])

  useEffect(() => {
    if (activeTab === 'history') {
      loadHistory()
    }
  }, [activeTab, loadHistory])

  // ── Filtering ───────────────────────────────────────────────────────────

  const filteredLiveEvents = liveEvents.filter((event) => {
    if (componentFilter === 'all') return true
    // Show events where the filtered component has non-zero duration or tokens
    const comp = event.trace[componentFilter]
    return comp.duration_ms > 0 || comp.tokens_used > 0
  })

  const filteredHistoryTraces = historyTraces.filter((entry) => {
    if (componentFilter === 'all') return true
    const comp = entry.trace[componentFilter]
    return comp.duration_ms > 0 || comp.tokens_used > 0
  })

  // Auto-scroll to bottom when new events arrive
  const liveContainerRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (autoScroll && liveContainerRef.current) {
      liveContainerRef.current.scrollTop = liveContainerRef.current.scrollHeight
    }
  }, [filteredLiveEvents.length, autoScroll])

  // ── Render ──────────────────────────────────────────────────────────────

  return (
    <div className="space-y-4">
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <span>🔬</span> Cognitive Trace Viewer
          </h3>
          <p className="text-sm text-readout">
            Real-time and historical cognitive pipeline traces
          </p>
        </div>

        {/* Live stream controls */}
        <div className="flex items-center gap-2">
          {isStreaming ? (
            <div className="flex items-center gap-2">
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-75" />
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-success" />
              </span>
              <span className="text-xs text-success font-medium">Streaming</span>
              <button
                type="button"
                className="btn btn-error btn-outline btn-xs"
                onClick={stopStream}
              >
                Stop
              </button>
            </div>
          ) : (
            <button
              type="button"
              className="btn btn-primary btn-outline btn-xs"
              onClick={startStream}
            >
              {streamError ? 'Reconnect' : 'Start Streaming'}
            </button>
          )}
        </div>
      </div>

      {/* ── Filters ─────────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="form-control">
          <label className="label py-0">
            <span className="label-text text-xs text-readout">Component Filter</span>
          </label>
          <select
            className="select select-bordered select-xs w-44"
            value={componentFilter}
            onChange={(e) => setComponentFilter(e.target.value as ComponentName | 'all')}
          >
            <option value="all">All Components</option>
            <option value="context_builder">Context Builder</option>
            <option value="executor">Executor</option>
            <option value="memory_manager">Memory Manager</option>
            <option value="response_formatter">Response Formatter</option>
          </select>
        </div>

        {activeTab === 'live' && (
          <label className="flex items-center gap-2 text-xs text-readout cursor-pointer pt-5">
            <input
              type="checkbox"
              className="checkbox checkbox-sm checkbox-primary"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
            />
            Auto-scroll
          </label>
        )}

        {activeTab === 'history' && (
          <button
            type="button"
            className="btn btn-outline btn-xs pt-5"
            onClick={loadHistory}
            disabled={historyLoading}
          >
            {historyLoading ? (
              <span className="loading loading-spinner loading-xs" />
            ) : (
              'Refresh'
            )}
          </button>
        )}
      </div>

      {/* ── Tab Navigation ──────────────────────────────────────────────── */}
      <div className="tabs tabs-boxed">
        <button
          type="button"
          className={`tab tab-sm ${activeTab === 'live' ? 'tab-active' : ''}`}
          onClick={() => setActiveTab('live')}
        >
          <span className="flex items-center gap-1.5">
            {isStreaming && (
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-success" />
              </span>
            )}
            Live Stream
            {filteredLiveEvents.length > 0 && (
              <span className="badge badge-sm badge-ghost">{filteredLiveEvents.length}</span>
            )}
          </span>
        </button>
        <button
          type="button"
          className={`tab tab-sm ${activeTab === 'history' ? 'tab-active' : ''}`}
          onClick={() => setActiveTab('history')}
        >
          <span className="flex items-center gap-1.5">
            History
            {filteredHistoryTraces.length > 0 && (
              <span className="badge badge-sm badge-ghost">{filteredHistoryTraces.length}</span>
            )}
          </span>
        </button>
      </div>

      {/* ── Stream Error ────────────────────────────────────────────────── */}
      {streamError && (
        <div className="alert alert-warning text-xs py-2">
          <span>⚠</span>
          <span>{streamError}</span>
        </div>
      )}

      {/* ── Live Tab ────────────────────────────────────────────────────── */}
      {activeTab === 'live' && (
        <div
          ref={liveContainerRef}
          className="space-y-3 max-h-[60vh] overflow-y-auto pr-1"
        >
          {filteredLiveEvents.length === 0 ? (
            <div className="text-center py-12 text-readout text-sm">
              {isStreaming ? (
                <>
                  <div className="text-2xl mb-2">⏳</div>
                  <div>Waiting for cognitive pipeline events...</div>
                  <div className="text-xs mt-1">Send a message to an agent to see traces</div>
                </>
              ) : (
                <>
                  <div className="text-2xl mb-2">📡</div>
                  <div>Stream is disconnected</div>
                  <button
                    type="button"
                    className="btn btn-primary btn-xs mt-2"
                    onClick={startStream}
                  >
                    Connect
                  </button>
                </>
              )}
            </div>
          ) : (
            filteredLiveEvents.map((event, index) => (
              <TraceCard
                key={`live-${index}`}
                event={event}
                index={filteredLiveEvents.length - index}
                componentFilter={componentFilter}
              />
            ))
          )}
        </div>
      )}

      {/* ── History Tab ─────────────────────────────────────────────────── */}
      {activeTab === 'history' && (
        <div>
          {historyLoading ? (
            <div className="flex items-center justify-center py-12">
              <span className="loading loading-spinner loading-md text-primary" />
            </div>
          ) : historyError ? (
            <div className="alert alert-error text-xs py-2">
              <span>⚠</span>
              <span>{historyError}</span>
            </div>
          ) : filteredHistoryTraces.length === 0 ? (
            <div className="text-center py-12 text-readout text-sm">
              <div className="text-2xl mb-2">📭</div>
              <div>No historical traces found</div>
              <div className="text-xs mt-1">
                Traces appear here after you send messages to agents
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              {/* History list */}
              {filteredHistoryTraces.map((entry) => (
                <div key={entry.id}>
                  <button
                    type="button"
                    className={`w-full flex items-center justify-between px-3 py-2 rounded-lg border text-sm transition-colors ${
                      selectedTraceId === entry.id
                        ? 'border-primary bg-primary/5'
                        : 'border-base-300 hover:bg-base-300/50'
                    }`}
                    onClick={() =>
                      setSelectedTraceId(
                        selectedTraceId === entry.id ? null : entry.id
                      )
                    }
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <span className="text-readout font-mono text-xs">
                        #{entry.id}
                      </span>
                      <span className="text-readout text-xs">
                        {formatTimestamp(entry.created_at)}
                      </span>
                      <span className="text-readout text-xs font-mono">
                        {formatDuration(entry.trace.total_duration_ms)}
                      </span>
                      <span className="text-readout text-xs">
                        {formatTokens(entry.trace.total_tokens)} tok
                      </span>
                    </div>
                    <span className="text-readout text-xs">
                      {selectedTraceId === entry.id ? '▾' : '▸'}
                    </span>
                  </button>

                  {/* Expanded trace detail */}
                  {selectedTraceId === entry.id && (
                    <div className="mt-2 space-y-3 pl-4 border-l-2 border-primary/20 ml-2">
                      <TraceSummaryCard
                        trace={{
                          trace: entry.trace,
                          metrics: entry.metrics,
                          memory_delta: entry.memory_delta,
                          error: entry.error,
                        }}
                      />
                      <div className="space-y-2">
                        {(Object.keys(COMPONENT_LABELS) as ComponentName[]).map((name) => (
                          <ComponentStepCard
                            key={name}
                            name={name}
                            data={entry.trace[name]}
                            defaultExpanded={false}
                          />
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Trace Card (for live stream) ────────────────────────────────────────────

function TraceCard({
  event,
  index,
  componentFilter,
}: {
  event: CognitiveTraceCompleteData
  index: number
  componentFilter: ComponentName | 'all'
}) {
  const [expanded, setExpanded] = useState(false)

  const components = (Object.keys(COMPONENT_LABELS) as ComponentName[]).filter(
    (name) => componentFilter === 'all' || name === componentFilter
  )

  return (
    <div className="rounded-lg border border-base-300 bg-base-200/30 overflow-hidden">
      {/* Header */}
      <button
        type="button"
        className="flex items-center justify-between w-full px-3 py-2 text-sm hover:bg-base-300/50 transition-colors"
        onClick={() => setExpanded((e) => !e)}
      >
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-readout font-mono text-xs w-8 shrink-0">
            #{index}
          </span>
          <span className="text-readout font-medium">
            Pipeline Run
          </span>
          <span className="text-readout text-xs font-mono">
            {formatDuration(event.trace.total_duration_ms)}
          </span>
          <span className="text-readout text-xs">
            {formatTokens(event.trace.total_tokens)} tok
          </span>
        </div>
        <div className="flex items-center gap-2">
          {event.error && (
            <span className="tooltip tooltip-top inline-block text-error text-xs" data-tip={event.error}>⚠</span>
          )}
          <span className="text-readout text-xs">
            {expanded ? '▾' : '▸'}
          </span>
        </div>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="px-3 pb-3 space-y-3">
          <TraceSummaryCard trace={event} />
          <div className="space-y-2">
            {components.map((name) => (
              <ComponentStepCard
                key={name}
                name={name}
                data={event.trace[name]}
                defaultExpanded={false}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
