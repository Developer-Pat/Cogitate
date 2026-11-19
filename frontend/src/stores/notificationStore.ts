import { create } from 'zustand'
import { useMessageStore } from './messageStore'
import { useNotificationConfigStore } from './notificationConfigStore'
import { crossTab } from '../services/crossTab/crossTab'

export interface Notification {
  /** THE SOURCE (2026-08-25): the message center's discriminator —
      the bus payloads carry 'exa'; the local errors default 'app'. */
  source?: string
  /** THE AIRPLANE-MODE BYPASS (2026-08-29): the flip-announcement
      (the mute-restore toast) shows even while the stale local
      config still says suppressed. */
  bypassSuppression?: boolean
  /** THE STICKY TOAST (2026-08-30, the user's ask): stays until
      dismissed (no auto-remove) — the attention events the user
      must acknowledge; the container cycles its sound every 2s. */
  sticky?: boolean
  eventId?: string
  id: string
  type: 'success' | 'error' | 'warning' | 'info'
  title: string
  message?: string
  timestamp: number
  duration?: number
  action?: {
    label: string
    href?: string
    onClick?: () => void
  }
}

/**
 * THE DEDUPE WINDOW (2026-08-24, QW4): the SSE bridge replays the
 * ring on every reconnect, so the same event can arrive twice (once
 * live, once via the catch-up — the double-cancelling-toast). A
 * notification identical to one added within the window is skipped.
 */

interface NotificationStore {
  notifications: Notification[]
  // THE TOAST SOUND-MUTE (2026-08-31, the sticky dig's fix): the
  // per-toast sound-off — the sticky's cycle respects it (the
  // toast STAYS, the sound stops — the 'stop the wav' without the
  // permanent dismiss).
  soundMutedIds: string[]
  toggleToastSound: (id: string) => void
  addNotification: (notification: Omit<Notification, 'id' | 'timestamp'>) => void
  removeNotification: (id: string) => void
  clearNotifications: () => void
  addSuccess: (title: string, message?: string, duration?: number, action?: Notification['action'], source?: string, eventId?: string) => void
  addError: (title: string, message?: string, duration?: number, action?: Notification['action'], source?: string, eventId?: string) => void
  addWarning: (title: string, message?: string, duration?: number, action?: Notification['action'], source?: string, eventId?: string) => void
  addInfo: (title: string, message: string, duration?: number, action?: Notification['action'], source?: string, eventId?: string) => void
}

export const useNotificationStore = create<NotificationStore>((set, get) => ({
  notifications: [],
  soundMutedIds: [],

  addNotification: (notification) => {
    // THE DEDUPE REMOVED (2026-09-01, the user's ask — the Bob-
    // error dig): the identical-within-window skip ate the REPEAT
    // firings — the user saw the toast but the center never
    // recorded the subsequent ones ('most of the warnings and
    // errors are not appearing in the message center'). The ring-
    // replay's guard is the BRIDGE's seen-check (the already-
    // recorded content stays silent) — the store-level dedupe was
    // the redundant second gate that hid real repeats.
    const now = Date.now()
    const id = Math.random().toString(36).substring(2, 9)
    const timestamp = now
    const newNotification: Notification = {
      ...notification,
      id,
      timestamp,
      duration: notification.duration ?? 5000
    }

    // THE AIRPLANE-MODE GATE (2026-08-29, the notifications-upgrade):
    // the suppressed config mutes the TOAST display only — the
    // message center + the cross-tab broadcast continue (the queue
    // + the counts persist — the viewable-queue doctrine). The
    // bypass flag rides the flip-announcements (the restore toast
    // must show even while the stale local config says suppressed).
    const suppressed =
      !newNotification.bypassSuppression &&
      useNotificationConfigStore.getState().config?.suppressed === true

    if (!suppressed) {
      set((state) => ({
        notifications: [...state.notifications, newNotification]
      }))
    }

    // THE MESSAGE CENTER CHOKE POINT (2026-08-25, the user's
    // report: 'none of these errors show up in the message
    // center'): EVERY toast also lands in the message store —
    // the frontend-local errors (the apiClient, the components)
    // previously lived only in the toast list and never reached
    // the center (the bridge only captured the backend bus).
    try {
      useMessageStore.getState().addMessage({
        eventId: notification.eventId,
        kind: notification.source === 'exa' ? 'exa-notify' : 'app-notify',
        source: notification.source ?? 'app',
        type: newNotification.type,
        title: newNotification.title,
        message: newNotification.message ?? '',
      })
    } catch {
      // the message store must never break the toasts
    }

    // THE CROSS-TAB BROADCAST (2026-08-29, the user's report: the
    // local errors don't reach the center in OTHER tabs — the
    // message store is per-tab!): the OTHER tabs' centers add this
    // too. The receiver's addMessage does NOT re-broadcast (the
    // addMessage's direct — no loop!)
    try {
      crossTab.publishNotify({
        eventId: notification.eventId,
        kind: notification.source === 'exa' ? 'exa-notify' : 'app-notify',
        source: notification.source ?? 'app',
        messageType: newNotification.type,
        title: newNotification.title,
        message: newNotification.message ?? '',
      })
    } catch {
      // the broadcast must never break the toasts
    }

    // Auto-remove after duration (only when the toast was shown —
    // the sticky toasts stay until dismissed: no timer)
    if (!suppressed && !newNotification.sticky && newNotification.duration && newNotification.duration > 0) {
      setTimeout(() => {
        get().removeNotification(id)
      }, newNotification.duration)
    }
  },

  toggleToastSound: (id) =>
    set((s) => ({
      soundMutedIds: s.soundMutedIds.includes(id)
        ? s.soundMutedIds.filter((x) => x !== id)
        : [...s.soundMutedIds, id],
    })),
  removeNotification: (id) => {
    set((state) => ({
      notifications: state.notifications.filter((n) => n.id !== id)
    }))
  },

  clearNotifications: () => {
    set({ notifications: [] })
  },

  addSuccess: (title, message, duration, action, source, eventId) => {
    get().addNotification({ type: 'success', title, message, duration, action, source, eventId })
  },

  addError: (title, message, duration, action, source, eventId) => {
    get().addNotification({ type: 'error', title, message, duration, action, source, eventId })
  },

  addWarning: (title, message, duration, action, source, eventId) => {
    get().addNotification({ type: 'warning', title, message, duration, action, source, eventId })
  },

  addInfo: (title, message, duration, action, source, eventId) => {
    get().addNotification({ type: 'info', title, message, duration, action, source, eventId })
  }
}))