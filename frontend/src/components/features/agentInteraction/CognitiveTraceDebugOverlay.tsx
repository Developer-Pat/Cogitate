/**
 * CognitiveTraceDebugOverlay
 *
 * Development-only floating overlay that shows the raw cognitive pipeline
 * trace events in real-time. Activated via keyboard shortcut (Ctrl+Shift+D).
 *
 * Displays:
 * - Ordered list of all cognitive events with timestamps
 * - Full event data (expandable)
 * - Trace summary metrics
 * - Memory delta information
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import type { CognitiveEvent, CognitiveState, CognitiveTraceCompleteEvent } from '@/services/domain/StreamingService'

// ── Types ───────────────────────────────────────────────────────────────────

interface CognitiveTraceDebugOverlayProps {
  cognitiveState: CognitiveState
  getCognitiveState: () => CognitiveState
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function formatTime(ms: number): string {
  if (ms < 1000) return `${ms.toFixed(0)}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${(ms / 60000).toFixed(1)}m`
}



const EVENT_COLORS: Record<string, string> = {
  cognitive_context_built: 'text-info',
  cognitive_executor_started: 'text-warning',
  cognitive_executor_progress: 'text-warning',
  cognitive_executor_completed: 'text-success',
  cognitive_memory_updated: 'text-secondary',
  cognitive_response_formatted: 'text-accent',
  cognitive_trace_complete: 'text-primary',
}

const EVENT_LABELS: Record<string, string> = {
  cognitive_context_built: 'Context Built',
  cognitive_executor_started: 'Executor Started',
  cognitive_executor_progress: 'Executor Progress',
  cognitive_executor_completed: 'Executor Completed',
  cognitive_memory_updated: 'Memory Updated',
  cognitive_response_formatted: 'Response Formatted',
  cognitive_trace_complete: 'Trace Complete',
}

// ── Sub-components ──────────────────────────────────────────────────────────

function EventRow({ event, index }: { event: CognitiveEvent; index: number }) {
  const [expanded, setExpanded] = useState(false)
  const color = EVENT_COLORS[event.type] ?? 'text-base-content'
  const label = EVENT_LABELS[event.type] ?? event.type

  return (
    <div className="border-b border-base-300 last:border-b-0">
      {/* Event header (always visible) */}
      <button
        type="button"
        className="flex items-center justify-between w-full px-2 py-1.5 text-xs hover:bg-base-300/50 transition-colors text-left"
        onClick={() => setExpanded((e) => !e)}
      >
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-readout font-mono w-6 shrink-0">#{index}</span>
          <span className={`font-medium ${color} shrink-0`}>{label}</span>
          {'duration_ms' in event.data && (
            <span className="text-readout font-mono">
              {formatTime((event.data as { duration_ms: number }).duration_ms)}
            </span>
          )}
        </div>
        <span className="text-readout font-mono text-[10px] shrink-0 ml-2">
          {expanded ? '▾' : '▸'}
        </span>
      </button>

      {/* Expanded event data */}
      {expanded && (
        <div className="px-3 pb-2">
          <pre className="text-[10px] font-mono bg-base-300/50 rounded p-2 overflow-x-auto max-h-48 overflow-y-auto text-readout">
            {JSON.stringify(event.data, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}

function TraceSummary({ trace }: { trace: CognitiveTraceCompleteEvent }) {
  return (
    <div className="px-2 py-1.5 space-y-1">
      <div className="text-xs font-semibold text-readout flex items-center gap-1.5">
        <span>📊</span> Trace Summary
      </div>
      <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[10px] font-mono text-readout">
        <span>Total Duration:</span>
        <span className="text-right">{formatTime(trace.trace.total_duration_ms)}</span>
        <span>Total Tokens:</span>
        <span className="text-right">{trace.trace.total_tokens.toLocaleString()}</span>
        <span>LLM Calls:</span>
        <span className="text-right">{trace.metrics.llm_calls}</span>
        <span>Tool Calls:</span>
        <span className="text-right">{trace.metrics.tool_calls}</span>
        <span>Cache Hits:</span>
        <span className="text-right">{trace.metrics.cache_hits}</span>
      </div>

      {/* Per-component breakdown */}
      <div className="pt-1 space-y-0.5">
        {Object.entries(trace.trace).filter(([key]) => key !== 'total_duration_ms' && key !== 'total_tokens').map(([key, val]) => {
          const data = val as { component: string; strategy: string; duration_ms: number; tokens_used?: number }
          return (
            <div key={key} className="flex items-center justify-between text-[10px] font-mono text-readout">
              <span className="truncate">{data.component}:{data.strategy}</span>
              <span className="shrink-0 ml-2">
                {formatTime(data.duration_ms)}
                {data.tokens_used ? ` · ${data.tokens_used} tok` : ''}
              </span>
            </div>
          )
        })}
      </div>

      {/* Memory delta */}
      {trace.memory_delta && (
        <div className="pt-1">
          <div className="text-[10px] font-semibold text-readout">Memory Delta</div>
          <div className="text-[10px] font-mono text-readout">
            {trace.memory_delta.stored_keys.length > 0 && (
              <div>Stored: {trace.memory_delta.stored_keys.join(', ')}</div>
            )}
            {trace.memory_delta.evicted_keys.length > 0 && (
              <div>Evicted: {trace.memory_delta.evicted_keys.join(', ')}</div>
            )}
            {trace.memory_delta.compaction_triggered && (
              <div className="text-warning">⚠ Compaction triggered</div>
            )}
          </div>
        </div>
      )}

      {/* Error if present */}
      {trace.error && (
        <div className="text-[10px] text-error font-mono pt-1">
          Error: {trace.error}
        </div>
      )}
    </div>
  )
}

// ── Main Component ──────────────────────────────────────────────────────────

export default function CognitiveTraceDebugOverlay({
  cognitiveState,
  getCognitiveState,
}: CognitiveTraceDebugOverlayProps) {
  const [visible, setVisible] = useState(false)
  const [position, setPosition] = useState({ x: 16, y: 60 })
  const [activeTab, setActiveTab] = useState<'events' | 'trace' | 'raw'>('events')
  const [rawState, setRawState] = useState<string>('')
  const overlayRef = useRef<HTMLDivElement>(null)
  const dragRef = useRef<{ startX: number; startY: number; offsetX: number; offsetY: number } | null>(null)

  // Keyboard shortcut: Ctrl+Shift+D to toggle
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.shiftKey && e.key === 'D') {
        e.preventDefault()
        setVisible((v) => !v)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  // Update raw state snapshot periodically when visible
  useEffect(() => {
    if (!visible) return
    const interval = setInterval(() => {
      setRawState(JSON.stringify(getCognitiveState(), null, 2))
    }, 500)
    return () => clearInterval(interval)
  }, [visible, getCognitiveState])

  // Drag handling
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    const rect = overlayRef.current?.getBoundingClientRect()
    if (!rect) return
    dragRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      offsetX: rect.left,
      offsetY: rect.top,
    }

    const handleMouseMove = (ev: MouseEvent) => {
      if (!dragRef.current) return
      setPosition({
        x: ev.clientX - dragRef.current.startX + dragRef.current.offsetX,
        y: ev.clientY - dragRef.current.startY + dragRef.current.offsetY,
      })
    }

    const handleMouseUp = () => {
      dragRef.current = null
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
  }, [])

  if (!visible) return null

  const { events, latestTrace, isActive, executorStage } = cognitiveState

  return (
    <div
      ref={overlayRef}
      className="fixed z-[9999] w-[420px] max-h-[80vh] flex flex-col rounded-lg border border-base-300 bg-base-200/95 backdrop-blur-md shadow-2xl text-xs"
      style={{ left: position.x, top: position.y }}
    >
      {/* ── Header (draggable) ──────────────────────────────────────────── */}
      <div
        className="flex items-center justify-between px-3 py-2 border-b border-base-300 cursor-grab active:cursor-grabbing select-none bg-base-300/50 rounded-t-lg"
        onMouseDown={handleMouseDown}
      >
        <div className="flex items-center gap-2">
          <span className="text-warning font-bold text-sm">🐛 Debug</span>
          <span className="text-readout text-[10px] font-mono">
            Cognitive Trace
          </span>
          {isActive && (
            <span className="loading loading-spinner loading-xs text-primary" />
          )}
        </div>
        <div className="flex items-center gap-1.5">
          <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded-full ${
            isActive ? 'bg-success/10 text-success' : 'bg-base-300 text-readout'
          }`}>
            {isActive ? executorStage : 'idle'}
          </span>
          <span className="tooltip tooltip-top" data-tip="Close (Ctrl+Shift+D)">
          <button
            type="button"
            className="btn btn-ghost btn-xs text-base-content/50 hover:text-base-content"
            onClick={() => setVisible(false)}
            aria-label="Close trace debug overlay"
          >
            ✕
          </button>
          </span>
        </div>
      </div>

      {/* ── Tabs ────────────────────────────────────────────────────────── */}
      <div className="flex border-b border-base-300">
        {(['events', 'trace', 'raw'] as const).map((tab) => (
          <button
            key={tab}
            type="button"
            className={`flex-1 py-1.5 text-[10px] font-medium transition-colors ${
              activeTab === tab
                ? 'text-primary border-b-2 border-primary bg-primary/5'
                : 'text-base-content/40 hover:text-base-content/70'
            }`}
            onClick={() => setActiveTab(tab)}
          >
            {tab === 'events' && `Events (${events.length})`}
            {tab === 'trace' && 'Trace'}
            {tab === 'raw' && 'Raw State'}
          </button>
        ))}
      </div>

      {/* ── Content ─────────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto min-h-0">
        {activeTab === 'events' && (
          <div>
            {events.length === 0 ? (
              <div className="p-4 text-center text-readout text-[10px]">
                No cognitive events yet. Send a message to see pipeline events.
              </div>
            ) : (
              events.map((event, i) => (
                <EventRow key={`${event.type}-${i}`} event={event} index={i + 1} />
              ))
            )}
          </div>
        )}

        {activeTab === 'trace' && (
          <div>
            {latestTrace ? (
              <TraceSummary trace={latestTrace} />
            ) : (
              <div className="p-4 text-center text-readout text-[10px]">
                No trace data available yet. Trace is available after pipeline completes.
              </div>
            )}
          </div>
        )}

        {activeTab === 'raw' && (
          <div className="p-2">
            <pre className="text-[10px] font-mono bg-base-300/50 rounded p-2 overflow-x-auto max-h-96 overflow-y-auto text-readout">
              {rawState || 'Waiting for state...'}
            </pre>
          </div>
        )}
      </div>

      {/* ── Footer ──────────────────────────────────────────────────────── */}
      <div className="px-3 py-1.5 border-t border-base-300 flex items-center justify-between text-[10px] text-readout">
        <span>Ctrl+Shift+D to toggle</span>
        <span>{events.length} events · {isActive ? 'active' : 'idle'}</span>
      </div>
    </div>
  )
}
