/**
 * useRunEstimator — the run-time estimate (Phase F2, 2026-08-24).
 *
 * The monitoring idea made real: consumes the bus's batch:done
 * events (which carry batch_id + total_batches + the timestamp)
 * and computes:
 *   - done / total (the progress fraction)
 *   - elapsed (from the first batch:done)
 *   - per-batch rate (elapsed / done)
 *   - remaining estimate (total - done) x rate
 *
 * Subscribes on mount, cleans up on unmount (the MVVM rule).
 * Pure computation — no DOM, no store: the caller renders.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { eventBus } from '../services/eventBus'
import { addTopics, removeTopics } from '../services/messagingFeed'

/** The topics the estimator needs: batch:* + workflow:* (the
 * batch:done events + the lifecycle). */
export const ESTIMATOR_TOPICS = 'batch:*,workflow:*'

export interface RunEstimate {
  workflowId: string
  done: number
  total: number
  elapsedSec: number
  rateSec: number
  remainingSec: number
  progress: number // 0..1
  finished: boolean
}

interface BatchDone {
  batch_id?: number
  total_batches?: number
  workflow_id?: string
  at?: string
}

export function useRunEstimator(workflowId?: string): RunEstimate | null {
  const [estimate, setEstimate] = useState<RunEstimate | null>(null)
  const stateRef = useRef<{
    startMs: number | null
    done: number
    total: number
    lastBatchMs: number | null
  }>({ startMs: null, done: 0, total: 0, lastBatchMs: null })

  const compute = useCallback(() => {
    const s = stateRef.current
    if (s.startMs === null || s.total === 0) return
    const now = Date.now()
    const elapsedSec = (now - s.startMs) / 1000
    const rateSec = s.done > 0 ? elapsedSec / s.done : 0
    const remainingSec = rateSec * (s.total - s.done)
    setEstimate({
      workflowId: workflowId ?? '',
      done: s.done,
      total: s.total,
      elapsedSec,
      rateSec,
      remainingSec,
      progress: s.done / s.total,
      finished: s.done >= s.total,
    })
  }, [workflowId])

  useEffect(() => {
    if (!workflowId) return
    const s = stateRef.current
    s.startMs = null
    s.done = 0
    s.total = 0

    // THE FEED REGISTRATION (2026-08-24, the UI wiring): the bus
    // only receives events the messagingFeed is bridged to — the
    // estimator registers its topics so batch:done + the lifecycle
    // actually arrive.
    addTopics(ESTIMATOR_TOPICS)

    const unsub = eventBus.subscribe(`workflow:${workflowId}:*`, () => {
      // the lifecycle events arrive too — recompute (the completed
      // event marks the run done)
      compute()
    })

    // the wildcard only matches a trailing '*' — subscribe to
    // 'batch:*' and FILTER the ':done' suffix in the handler (the
    // honest multi-segment topic handling)
    const unsubBatch = eventBus.subscribe(`batch:*`, (payload) => {
      const p = (payload ?? {}) as BatchDone
      const wid = p.workflow_id
      if (wid && wid !== workflowId) return
      if (p.batch_id === undefined) return // not a batch:done event
      const now = Date.now()
      s.startMs = s.startMs ?? now
      s.lastBatchMs = now
      s.done += 1
      s.total = p.total_batches ?? s.total
      compute()
    })

    const unsubStarted = eventBus.subscribe(`workflow:${workflowId}:started`, () => {
      s.startMs = Date.now()
      s.done = 0
      s.total = 0
    })

    return () => {
      unsub()
      unsubBatch()
      unsubStarted()
      removeTopics(ESTIMATOR_TOPICS)
    }
  }, [workflowId, compute])

  return estimate
}
