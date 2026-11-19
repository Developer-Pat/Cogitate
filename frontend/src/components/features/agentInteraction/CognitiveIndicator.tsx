import { useMemo } from 'react'
import type { CognitiveEvent, CognitiveState } from '@/services/domain/StreamingService'

interface CognitiveIndicatorProps {
  cognitiveState: CognitiveState
  /** If true, renders a compact inline version (for embedding in the message area) */
  compact?: boolean
}

// ── Stage icons and labels ──────────────────────────────────────────────────

const STAGE_CONFIG: Record<string, { icon: string; label: string; color: string }> = {
  context_builder:   { icon: '🔍', label: 'Context',   color: 'text-info' },
  executor:          { icon: '🧠', label: 'Thinking',  color: 'text-warning' },
  memory_manager:    { icon: '💾', label: 'Memory',    color: 'text-secondary' },
  response_formatter:{ icon: '✍️', label: 'Format',    color: 'text-accent' },
}

// THE STAGES THE EXECUTOR ACTUALLY REPORTS — and deliberately NO `idle` entry.
//
// This map used to carry one, and the lookup below fell back to it, so a stage it
// did not recognise drew "⏸️ Idle" INSIDE a badge whose tooltip read "Thinking:
// active". The indicator contradicted itself, during the one moment it is on
// screen. An unrecognised stage now draws nothing beside the badge instead of a
// word that is at best meaningless and at worst exactly backwards.
const EXECUTOR_STAGES: Record<string, { icon: string; label: string }> = {
  thinking:     { icon: '🤔', label: 'Thinking' },
  streaming:    { icon: '📝', label: 'Streaming' },
  executing:    { icon: '🔧', label: 'Executing' },
  completed:    { icon: '✅', label: 'Completed' },
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function getLastEventOfType(state: CognitiveState, type: string): CognitiveEvent | undefined {
  // Iterate backwards to find the most recent event of the given type
  for (let i = state.events.length - 1; i >= 0; i--) {
    if (state.events[i].type === type) return state.events[i]
  }
  return undefined
}

// ── Component ───────────────────────────────────────────────────────────────

export default function CognitiveIndicator({ cognitiveState, compact = false }: CognitiveIndicatorProps) {
  const { isActive, executorStage, events, latestTrace } = cognitiveState

  // Derive which pipeline components have completed / are active
  const componentStatuses = useMemo(() => {
    const statuses: Record<string, 'pending' | 'active' | 'done'> = {
      context_builder: 'pending',
      executor: 'pending',
      memory_manager: 'pending',
      response_formatter: 'pending',
    }

    for (const evt of events) {
      switch (evt.type) {
        case 'cognitive_context_built':
          statuses.context_builder = 'done'
          break
        case 'cognitive_executor_started':
          statuses.executor = 'active'
          break
        case 'cognitive_executor_completed':
          statuses.executor = 'done'
          break
        case 'cognitive_memory_updated':
          statuses.memory_manager = 'done'
          break
        case 'cognitive_response_formatted':
          statuses.response_formatter = 'done'
          break
        case 'cognitive_trace_complete':
          statuses.context_builder = 'done'
          statuses.executor = 'done'
          statuses.memory_manager = 'done'
          statuses.response_formatter = 'done'
          break
      }
    }

    return statuses
  }, [events])

  // Get duration from latest trace if available
  const totalDuration = latestTrace?.trace.total_duration_ms ?? 0
  const totalTokens = latestTrace?.trace.total_tokens ?? 0

  // The executor stage detail — UNDEFINED for a stage this map does not know (see
  // the note on EXECUTOR_STAGES). Both render sites below guard on it, so an unknown
  // stage shows the badge and its tooltip and nothing else.
  const executorDisplay = EXECUTOR_STAGES[executorStage]

  // If not active and no events, render nothing
  if (!isActive && events.length === 0) {
    return null
  }

  // ── Compact variant (single line, small badges) ──────────────────────────
  if (compact) {
    return (
      <div className="flex items-center gap-1.5 text-xs opacity-80">
        {/* Pipeline stage badges */}
        {Object.entries(componentStatuses).map(([component, status]) => {
          const cfg = STAGE_CONFIG[component]
          if (!cfg) return null
          return (
            <span
              key={component}
              className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full transition-all duration-300 ${
                status === 'done'
                  ? 'bg-success/10 text-success'
                  : status === 'active' && isActive
                  ? `${cfg.color} bg-base-300`
                  : 'bg-base-300 text-readout'
              }`}
            >
              <span className="tooltip tooltip-bottom" data-tip={`${cfg.label}: ${status}`}>
                <span className="text-[10px]">{cfg.icon}</span>
              </span>
              {!isActive && status === 'done' ? (
                <span className="font-medium">{formatDuration(totalDuration)}</span>
              ) : status === 'active' && isActive && executorDisplay ? (
                <span className="font-medium">{executorDisplay.icon} {executorDisplay.label}</span>
              ) : null}
            </span>
          )
        })}

        {/* Token count from latest trace */}
        {!isActive && totalTokens > 0 && (
          <div className="tooltip tooltip-bottom" data-tip="Total tokens used"><span className="text-readout">
            {totalTokens} tokens
          </span></div>
        )}

        {/* Spinner when active — THE ONE activity animation (2026-09-05,
            the user's call): the stage badges highlight statically and
            NEVER pulse — a stuck-active state would otherwise animate
            forever. The spinner rides the same isActive flag + the
            render-site settle guard. */}
        {isActive && (
          <span className="loading loading-spinner loading-xs text-primary" />
        )}
      </div>
    )
  }

  // ── Full variant (stacked, detailed) ─────────────────────────────────────
  return (
    <div className="rounded-lg border border-base-300 bg-base-200/50 p-3 text-xs space-y-2">
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="font-semibold text-readout flex items-center gap-1.5">
          <span>🧠</span> Cognitive Pipeline
          {isActive && (
            <span className="loading loading-spinner loading-xs text-primary ml-1" />
          )}
        </span>
        {!isActive && totalDuration > 0 && (
          <span className="text-readout">{formatDuration(totalDuration)}</span>
        )}
      </div>

      {/* Component stages */}
      <div className="space-y-1">
        {Object.entries(componentStatuses).map(([component, status]) => {
          const cfg = STAGE_CONFIG[component]
          if (!cfg) return null

          // Find the event data for this component to show timing
          const eventTypeMap: Record<string, string> = {
            context_builder: 'cognitive_context_built',
            executor: 'cognitive_executor_completed',
            memory_manager: 'cognitive_memory_updated',
            response_formatter: 'cognitive_response_formatted',
          }
          const lastEvent = getLastEventOfType(cognitiveState, eventTypeMap[component])
          const duration = lastEvent && 'duration_ms' in lastEvent.data
            ? (lastEvent.data as { duration_ms: number }).duration_ms
            : undefined

          return (
            <div
              key={component}
              className={`flex items-center justify-between px-2 py-1 rounded transition-all duration-300 ${
                status === 'done'
                  ? 'bg-success/5'
                  : status === 'active' && isActive
                  ? 'bg-base-300'
                  : ''
              }`}
            >
              <span className="flex items-center gap-1.5">
                <span>{cfg.icon}</span>
                <span className={status === 'done' ? 'text-success' : status === 'active' ? cfg.color : 'text-readout'}>
                  {cfg.label}
                </span>
                {status === 'active' && isActive && component === 'executor' && executorDisplay && (
                  <span className="text-readout ml-1">
                    ({executorDisplay.icon} {executorDisplay.label})
                  </span>
                )}
              </span>
              <span className="text-readout">
                {status === 'done' && duration !== undefined
                  ? formatDuration(duration)
                  : status === 'active' && isActive
                  ? '…'
                  : '⏳'}
              </span>
            </div>
          )
        })}
      </div>

      {/* Footer metrics from trace complete */}
      {latestTrace && (
        <div className="flex items-center gap-3 text-readout pt-1 border-t border-base-300">
          {totalTokens > 0 && <span>{totalTokens} tokens</span>}
          {latestTrace.metrics.llm_calls > 0 && <span>{latestTrace.metrics.llm_calls} LLM calls</span>}
          {latestTrace.metrics.tool_calls > 0 && <span>{latestTrace.metrics.tool_calls} tool calls</span>}
          {latestTrace.memory_delta?.compaction_triggered && (
            <span className="text-warning">Compacted</span>
          )}
        </div>
      )}
    </div>
  )
}
