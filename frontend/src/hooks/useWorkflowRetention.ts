/**
 * useWorkflowRetention — the retention card's data half.
 *
 * Page → hook → service, the house layering: the card renders, this hook owns the calls and the
 * in-flight guards, the service owns the transport. Nothing here decides a window; the values come
 * from the backend (which resolves them from the app settings), so the surface edits config rather
 * than restating it.
 */

import { useCallback, useEffect, useRef, useState } from 'react'

import { frontendLoggingService } from '../services/frontendLoggingService'
import { workflowService } from '../services/domains/llm/workflowService'
import { useNotificationStore } from '../stores/notificationStore'
import type {
  RetentionPolicy,
  RetentionReport,
  RetentionStats,
} from '../types/workflows'

export interface UseWorkflowRetentionReturn {
  policy: RetentionPolicy | null
  defaults: RetentionPolicy | null
  stats: RetentionStats | null
  /** The last preview (or applied prune). Nulled whenever the policy changes. */
  report: RetentionReport | null
  loading: boolean
  busy: boolean
  error: string | null
  refresh: () => Promise<void>
  save: (partial: Partial<RetentionPolicy>) => Promise<boolean>
  preview: () => Promise<void>
  prune: () => Promise<boolean>
}

export function useWorkflowRetention(): UseWorkflowRetentionReturn {
  const addError = useNotificationStore((state) => state.addError)

  const [policy, setPolicy] = useState<RetentionPolicy | null>(null)
  const [defaults, setDefaults] = useState<RetentionPolicy | null>(null)
  const [stats, setStats] = useState<RetentionStats | null>(null)
  const [report, setReport] = useState<RetentionReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // A ref, not state: the guard must be readable inside the same tick that starts the request.
  const inFlight = useRef(false)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await workflowService.getRetention()
      if (res.error || !res.data) {
        throw new Error(res.error?.message || 'Could not read the retention policy')
      }
      setPolicy(res.data.policy)
      setDefaults(res.data.defaults)
      setStats(res.data.stats)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Could not read the retention policy'
      setError(message)
      addError('Workflow runs', message)
    } finally {
      setLoading(false)
    }
  }, [addError])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const save = useCallback(
    async (partial: Partial<RetentionPolicy>) => {
      if (inFlight.current) return false
      inFlight.current = true
      setBusy(true)
      setError(null)
      try {
        const res = await workflowService.updateRetention(partial)
        if (res.error || !res.data) {
          throw new Error(res.error?.message || 'Could not save the retention policy')
        }
        setPolicy(res.data.policy)
        // the windows moved, so any preview on screen is now about a different policy
        setReport(null)
        return true
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Could not save the retention policy'
        setError(message)
        addError('Workflow runs', message)
        return false
      } finally {
        inFlight.current = false
        setBusy(false)
      }
    },
    [addError]
  )

  const preview = useCallback(async () => {
    if (inFlight.current) return
    inFlight.current = true
    setBusy(true)
    setError(null)
    try {
      const res = await workflowService.pruneRetention(true)
      if (res.error || !res.data) {
        throw new Error(res.error?.message || 'Could not preview the prune')
      }
      setReport(res.data)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Could not preview the prune'
      setError(message)
      addError('Workflow runs', message)
    } finally {
      inFlight.current = false
      setBusy(false)
    }
  }, [addError])

  const prune = useCallback(async () => {
    if (inFlight.current) return false
    inFlight.current = true
    setBusy(true)
    setError(null)
    try {
      const res = await workflowService.pruneRetention(false)
      if (res.error || !res.data) {
        throw new Error(res.error?.message || 'The prune was refused')
      }
      setReport(res.data)
      // THE VISIBLE RESULT IS THE CONFIRMATION (the house rule): the readout below refreshes, so
      // this is a log rather than a toast. The log names what went, per the same rule.
      frontendLoggingService.info('useWorkflowRetention', 'Retention prune applied', {
        rows: res.data.rows_pruned,
        threads: res.data.threads_pruned,
        snapshots: res.data.snapshots_stripped,
        bytesFreed: res.data.snapshot_bytes_freed,
        abandoned: res.data.abandoned_marked,
      })
      await refresh()
      return true
    } catch (err) {
      const message = err instanceof Error ? err.message : 'The prune was refused'
      setError(message)
      addError('Workflow runs', message)
      return false
    } finally {
      inFlight.current = false
      setBusy(false)
    }
  }, [addError, refresh])

  return { policy, defaults, stats, report, loading, busy, error, refresh, save, preview, prune }
}
