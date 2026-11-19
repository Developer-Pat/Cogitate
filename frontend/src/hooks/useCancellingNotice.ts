/**
 * useCancellingNotice — the orderly-shutdown notice (2026-08-24).
 *
 * The queued item: the backend publishes workflow:<id>:cancelling
 * when a cancel is REQUESTED (before the terminal status lands —
 * the workers bail cooperatively between batches). This hook hears
 * it and shows the 'shutting down gracefully…' toast, so the user
 * knows the kill signal is being honored — no silent hang.
 *
 * The topics: workflow:* (the cancelling events ride the same
 * stream as the lifecycle).
 */

import { useEffect } from 'react'
import { eventBus } from '../services/eventBus'
import { addTopics, removeTopics } from '../services/messagingFeed'
import { useNotificationStore } from '../stores/notificationStore'

interface CancellingPayload {
  workflow_id?: string
  reason?: string
  kind?: string
}

/** The topics the notice needs: workflow:* (the cancelling events). */
export const CANCELLING_TOPICS = 'workflow:*'

export function useCancellingNotice(enabled = true): void {
  const addInfo = useNotificationStore((s) => s.addInfo)

  useEffect(() => {
    if (!enabled) return
    addTopics(CANCELLING_TOPICS)

    const unsub = eventBus.subscribe('workflow:*', (payload) => {
      const p = (payload ?? {}) as CancellingPayload
      // THE KIND DISCRIMINATOR (2026-08-24, the test caught it):
      // the handler can't see the topic (eventBus delivers only the
      // payload), so started/completed/cancelling all look alike —
      // the backend publishes kind='cancelling'; only that shows
      // the notice.
      if (p.workflow_id === undefined || p.kind !== 'cancelling') return
      addInfo(
        'Shutting down gracefully…',
        `Workflow ${p.workflow_id} is stopping after the current batch.`,
        6000,
      )
    })

    return () => {
      unsub()
      removeTopics(CANCELLING_TOPICS)
    }
  }, [enabled, addInfo])
}
