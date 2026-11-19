/**
 * useNotifyBridge — the toaster OPT-IN (Phase E consumer, 2026-08-24).
 *
 * The messaging service's first UI consumer: subscribes the
 * eventBus's 'notify:*' channel into the notification store (the
 * toaster). The pipeline/agents publish 'notify:<kind>' -> the
 * toast renders app-wide.
 *
 * The backend's publish tool validates the notify: namespace; this
 * bridge maps the payload to a toast:
 *   { title, message?, type? ('info'|'success'|'warning'|'error'),
 *     duration?, action?: {label, href} }
 *
 * Mounted once in the app shell (the useWorkflowToasts pattern).
 * The toaster itself is UNTOUCHED — it remains a consumer.
 */

import { useEffect } from 'react'
import { eventBus } from '../services/eventBus'
import { addTopics, removeTopics } from '../services/messagingFeed'
import { useNotificationStore } from '../stores/notificationStore'
import { useMessageStore } from '../stores/messageStore'
import { useNotificationConfigStore } from '../stores/notificationConfigStore'

interface NotifyPayload {
  title?: string
  message?: string
  type?: 'info' | 'success' | 'warning' | 'error'
  duration?: number
  /** THE STICKY FLAG (2026-08-30): the toast stays until dismissed
      + the container cycles the sound every 2s — the attention
      events the user must acknowledge. */
  sticky?: boolean
  action?: { label: string; href?: string; onClick?: () => void }
  from?: string
  kind?: string
}

/** The topics the bridge needs: notify:* (the toaster's channel). */
export const BRIDGE_TOPICS = 'notify:*'



export function useNotifyBridge(enabled = true): void {
  const addInfo = useNotificationStore((s) => s.addInfo)
  const addSuccess = useNotificationStore((s) => s.addSuccess)
  const addWarning = useNotificationStore((s) => s.addWarning)
  const addError = useNotificationStore((s) => s.addError)

  useEffect(() => {
    if (!enabled) return

    // register the bridge's topics (the feed maintains the union)
    addTopics(BRIDGE_TOPICS)

    const unsub = eventBus.subscribe('notify:*', (payload) => {
      const p = (payload ?? {}) as NotifyPayload
      const title = p.title ?? 'Notification'
      const message = p.message ?? ''
      const duration = p.duration
      const action = p.action
      const adders: Record<string, (t: string, m: string, d?: number, a?: typeof action, source?: string, eventId?: string) => void> = {
        info: addInfo,
        success: addSuccess,
        warning: addWarning,
        error: addError,
      }
      // THE MUTE-RESTORE ANNOUNCEMENT (2026-08-29, the scheduled-
      // mute): the backend's expiry restores suppressed=false at the
      // source + publishes this event. The local config copy is
      // stale (still suppressed) — force-reload it so the FOLLOWING
      // events are unsuppressed, and add this toast with the bypass
      // flag (it must show regardless — the flip announcement).
      const isRestore = p.kind === 'notifications-restored'
      if (isRestore) {
        useNotificationConfigStore.getState().load(true)
      }
      const adder = adders[p.type ?? 'info'] ?? addInfo
      // THE SOURCE PASS-THROUGH (2026-08-25): the notification
      // store's addNotification writes the toast AND the message
      // store (the single choke point — the local errors now land
      // in the center too). The bus payloads pass their source
      // (the 'exa' discriminator) through the adder.
      const source = p.from === 'exa' ? 'exa' : p.kind === 'system-sweep' ? 'system' : p.kind ?? 'app'
      // THE REPLAY SEEN-CHECK (2026-08-25, the ring-replay gap): the
      // SSE's initial payload replays the ring's recent events — the
      // SAME content the queue already holds, or deleted. Without
      // this check the replayed old news RE-TOASTS on every reconnect
      // (the toast fires before the store's dedupe). The seen content
      // stays silent — the queue is the record, the toast is for NEW
      // attention.
      // THE EVENT-ID KEY (2026-08-29): the bus-events carry the
      // event_id — the replay (the same event) is silent, but the
      // SAME content at a NEW event toasts + records (the center's
      // the record — the content-keyed dedupe ate the new events!)
      const eventId = (p as { event_id?: string }).event_id
      const key = useMessageStore.getState()._key({ eventId, type: p.type, source, title, message })
      const st = useMessageStore.getState()
      // THE STICKY RE-TOAST EXEMPTION (2026-08-30, the user's
      // reload-catch-up bug): the sticky toasts are the ATTENTION
      // contract — they stay until the ✕. A reload clears the
      // in-memory toasts and the seen-check (the center's record)
      // would EAT the replay — the sticky must re-toast on the
      // replay until explicitly dismissed. The TOMBSTONE (the ✕)
      // still suppresses forever; the non-sticky stay ephemeral.
      const tombstoned = st.tombstones.includes(key)
      const alreadyRecorded = st.messages.some((m) => st._key(m) === key)
      if (tombstoned || (alreadyRecorded && !p.sticky)) {
        return
      }
      // THE SOURCE (2026-08-26): the adders' signatures are
      // (t, m, d?, a?) — the source rides the STORE's notification
      // object (the choke point), not the adder's args.
      // THE EVENT-ID rides the NOTIFICATION (the store's choke point)!
      if (isRestore) {
        useNotificationStore.getState().addNotification({
          type: p.type ?? 'info',
          title,
          message,
          duration,
          action,
          source,
          eventId,
          bypassSuppression: true,
        })
      } else if (p.sticky) {
        // THE STICKY (2026-08-30): direct through the choke point —
        // the sticky flag rides the notification (the adders'
        // signatures stay stable — the eventId-drop lesson).
        useNotificationStore.getState().addNotification({
          type: p.type ?? 'info',
          title,
          message,
          duration,
          action,
          source,
          eventId,
          sticky: true,
        })
      } else if (action) {
        adder(title, message, duration, action, undefined, eventId)
      } else {
        adder(title, message, duration, undefined, undefined, eventId)
      }
    })

    // THE CLEANUP RULE (the MVVM lesson): every subscribe has its
    // unsubscribe; the stream closes on unmount.
    return () => {
      unsub()
      removeTopics(BRIDGE_TOPICS)
    }
  }, [enabled, addInfo, addSuccess, addWarning, addError])
}
