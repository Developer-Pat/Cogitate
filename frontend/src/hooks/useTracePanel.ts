/**
 * useTracePanel — the UI pump for the chat's cognitive trace
 * (Step 3, 2026-08-24).
 *
 * The chat-stream migration's projection hook: subscribes to the
 * bus's chat:* events (the trace events the pipeline publishes —
 * context_built, executor_started/completed, memory_updated,
 * response_formatted, trace_complete) and maps them to the
 * cognitive STATE the UI renders (the CognitiveIndicator + the
 * trace overlay).
 *
 * TARGETED RENDERING (the performance win): the indicator
 * re-renders ONLY on trace events — not on every token chunk
 * (the bubble stays on the direct stream by design).
 */

import { useEffect, useState } from 'react'
import { eventBus } from '../services/eventBus'
import { addTopics, removeTopics } from '../services/messagingFeed'
import type { CognitiveState, CognitiveEvent } from '../services/domain/StreamingService'

/** The topics the trace panel needs: chat:* (the trace events). */
export const TRACE_TOPICS = 'chat:*'

export interface TraceEvent {
  kind?: string
  component?: string
  strategy?: string
  duration_ms?: number
  tokens_used?: number
  error?: string | null
  sources?: string[]
  metrics?: Record<string, unknown>
  trace?: Record<string, unknown>
}

const EMPTY: CognitiveState = {
  events: [],
  latestTrace: null,
  isActive: false,
  executorStage: 'idle',
}

/** The contract kinds -> the legacy cognitive event names. */
function mapKindToEvent(kind: string): string {
  const map: Record<string, string> = {
    context_built: 'cognitive_context_built',
    executor_started: 'cognitive_executor_started',
    executor_completed: 'cognitive_executor_completed',
    memory_updated: 'cognitive_memory_updated',
    response_formatted: 'cognitive_response_formatted',
    trace_complete: 'cognitive_trace_complete',
  }
  return map[kind] ?? kind
}

export function useTracePanel(sessionId?: string): CognitiveState {
  const [state, setState] = useState<CognitiveState>(EMPTY)

  // THE SESSION RESET (2026-09-02, the user's "it is still
  // running"): switching sessions must not carry the previous
  // session's busy state (isActive=true) into the new view — the
  // pump starts EMPTY for a fresh session.
  useEffect(() => {
    setState(EMPTY)
  }, [sessionId])

  useEffect(() => {
    if (!sessionId) return

    // the UI pump registration (the feed must carry chat:*)
    addTopics(TRACE_TOPICS)

    const unsub = eventBus.subscribe('chat:*', (payload) => {
      // THE KIND DISCRIMINATOR (the contract): the bus handler
      // can't see the topic — the backend's publish enriches the
      // payload with kind (executor_started vs executor_completed
      // both carry component='executor'; the kind tells them
      // apart). The direct stream keeps the plain payload (the
      // SSE stays byte-identical).
      const p = (payload ?? {}) as TraceEvent
      if (p.kind === undefined) return

      const kind = mapKindToEvent(p.kind)

      setState((prev) => {
        const event = {
          type: kind,
          component: p.component ?? '',
          strategy: p.strategy ?? '',
          duration_ms: p.duration_ms ?? 0,
          tokens_used: p.tokens_used ?? 0,
          error: p.error ?? null,
          metadata: p.sources ? { sources: p.sources } : undefined,
        }
        const events = [...prev.events.slice(-49), event as unknown as CognitiveEvent]
        return {
          ...prev,
          events,
          latestTrace: kind === 'cognitive_trace_complete'
            ? (p as unknown as CognitiveState['latestTrace'])
            : prev.latestTrace,
          isActive: kind !== 'cognitive_trace_complete',
          executorStage: kind === 'cognitive_executor_started'
            ? 'running'
            : kind === 'cognitive_trace_complete'
              ? 'completed'
              : prev.executorStage,
        }
      })
    })

    return () => {
      unsub()
      removeTopics(TRACE_TOPICS)
    }
  }, [sessionId])

  return state
}
