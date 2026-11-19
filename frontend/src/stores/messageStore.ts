/**
 * messageStore — the system message queue (2026-08-25, the user's
 * Message Center design). The bus's notify:* payloads land here
 * (the bridge); the unread COUNT drives the chat's messages icon
 * + the dashboard card; the Message Center page renders the table.
 *
 * SUPERSEDES the exaUnreadStore (the pulse flag — the user's call:
 * the glowing agent button is replaced by the messages icon with
 * the count; the chat page de-clutters).
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface SystemMessage {
  id: string
  eventId?: string  // the bus-event id (2026-08-29): the center's
  // dedupe keys on it — the same content at a NEW event is a NEW
  // record! The replay (the same event_id) stays silent.
  kind: string
  source: string
  type: 'info' | 'success' | 'warning' | 'error'
  title: string
  message: string
  timestamp: number
  read: boolean
}

interface MessageState {
  messages: SystemMessage[]
  addMessage: (m: Omit<SystemMessage, 'id' | 'timestamp' | 'read'>) => void
  markAllRead: () => void
  deleteMessages: (ids: string[]) => void
  tombstoneKey: (key: string) => void
  tombstones: string[]
  /** key -> when it was tombstoned (the TTL check — 2026-09-05). */
  tombstoneTimestamps: Record<string, number>
  _key: (m: { eventId?: string; type?: string; source?: string; title: string; message: string }) => string
  clearAll: () => void
}

const MAX_MESSAGES = 500
// THE TOMBSTONE CAP (2026-08-25): the deleted-content keys retained
// — a cap bounds the storage growth.
const MAX_TOMBSTONES = 300
// THE TOMBSTONE TTL (2026-09-05, the user's 'new messages don't show
// up in the center' report): a tombstone suppresses the SAME content
// for an hour — long enough to cover the reload-catch-up replays it
// was built for — but a genuinely NEW occurrence (a fresh outage, a
// new Exa warning) records again. Before this, a clear() tombstoned
// every content key FOREVER: the 'Backend Unavailable' content the
// user deleted once silently ate every future occurrence.
const TOMBSTONE_TTL_MS = 60 * 60 * 1000

export const useMessageStore = create<MessageState>()(
  persist(
    (set, get) => ({
      messages: [],
      // THE TOMBSTONES (2026-08-25, the user's report: 'the messages
      // I deleted are back'): the deleted content keys — the source
      // events RE-FIRE on the reload (the products' toasts!), so a
      // plain deletion returns the moment the page reloads. The
      // tombstoned content stays deleted; the cap bounds the memory.
      // The timestamps (2026-09-05) bound the suppression's LIFE — the
      // TTL expiry lets the same content record again after an hour.
      tombstones: [] as string[],
      tombstoneTimestamps: {} as Record<string, number>,
      _key: (m: { eventId?: string; type?: string; source?: string; title: string; message: string }) =>
        m.eventId ? `evt:${m.eventId}` : `${m.type ?? ''}|${m.source ?? ''}|${m.title}|${m.message}`,
      addMessage: (m) => {
        const key = get()._key(m)
        // THE TOMBSTONE (re-enabled 2026-08-29 — the blip-debug's
        // done: the root-cause was the '//api'-URL, fixed! The
        // tombstone: the deleted content stays deleted across
        // reloads.)
        // THE DEDUPE REMOVED (2026-09-01, the Bob-errors dig — the
        // user's 'the center records every firing'): the same-key
        // skip ate the REPEAT messages — the center kept only the
        // first instance of each repeated warning. The ring-replay
        // stays quiet at the BRIDGE (the seen-check); the center is
        // the RECORD — every firing lands.
        // THE EVENT-ID DEDUPE (2026-09-05, the cross-tab triples —
        // the user's 'arriving three times for each message'): the
        // SAME bus event reaches a tab via the bridge AND the
        // cross-tab sync (every tab receives the SSE event + every
        // tab broadcasts its own copy to the others) — one record
        // per EVENT, not one per path. The no-eventId locals (the
        // Bob-errors doctrine — every firing lands) are untouched:
        // they carry no event id and always record.
        if (
          m.eventId &&
          get().messages.some((existing) => existing.eventId === m.eventId)
        ) {
          return
        }
        if (get().tombstones.includes(key)) {
          // THE TTL CHECK (2026-09-05): a tombstone without a
          // timestamp (the pre-TTL store's leftovers) counts as
          // ALREADY EXPIRED — the migration unblocks the center.
          const at = get().tombstoneTimestamps[key] ?? 0
          if (Date.now() - at < TOMBSTONE_TTL_MS) {
            return
          }
          // expired — prune the stale tombstone so this content
          // records again (and stays prunable on the next pass)
          set((s) => {
            const timestamps = { ...s.tombstoneTimestamps }
            delete timestamps[key]
            return {
              tombstones: s.tombstones.filter((k) => k !== key),
              tombstoneTimestamps: timestamps,
            }
          })
        }
        set((s) => ({
          messages: [
            {
              ...m,
              id: `msg-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
              timestamp: Date.now(),
              read: false,
            },
            ...s.messages,
          ].slice(0, MAX_MESSAGES),
        }))
      },
      markAllRead: () => set((s) => ({ messages: s.messages.map((m) => ({ ...m, read: true })) })),
      deleteMessages: (ids) =>
        set((s) => {
          const gone = s.messages.filter((m) => ids.includes(m.id))
          const keys = gone.map((m) => s._key(m))
          const now = Date.now()
          const timestamps = { ...s.tombstoneTimestamps }
          for (const k of keys) timestamps[k] = now
          const tombstoned = [...s.tombstones, ...keys].slice(-MAX_TOMBSTONES)
          // the timestamps follow the cap — orphaned entries pruned
          for (const k of Object.keys(timestamps)) {
            if (!tombstoned.includes(k)) delete timestamps[k]
          }
          return {
            messages: s.messages.filter((m) => !ids.includes(m.id)),
            tombstones: tombstoned,
            tombstoneTimestamps: timestamps,
          }
        }),
      // THE TOAST-✕ TOMBSTONE (2026-08-30, the Exa-diagnosed
      // replay-after-dismiss bug): the toast ✕ only removed the
      // toast-layer entry — the message-store tombstone was NEVER
      // written, so the SSE ring-replay re-toasted the sticky (and
      // restarted the 2s sound cycle). The ✕ now tombstones the
      // exact event key the bridge checks.
      tombstoneKey: (key) =>
        set((s) => {
          const tombstoned = [...s.tombstones, key].slice(-MAX_TOMBSTONES)
          const timestamps = { ...s.tombstoneTimestamps, [key]: Date.now() }
          for (const k of Object.keys(timestamps)) {
            if (!tombstoned.includes(k)) delete timestamps[k]
          }
          return { tombstones: tombstoned, tombstoneTimestamps: timestamps }
        }),
      clearAll: () =>
        set((s) => {
          const keys = s.messages.map((m) => s._key(m))
          const now = Date.now()
          const timestamps = { ...s.tombstoneTimestamps }
          for (const k of keys) timestamps[k] = now
          const tombstoned = [...s.tombstones, ...keys].slice(-MAX_TOMBSTONES)
          for (const k of Object.keys(timestamps)) {
            if (!tombstoned.includes(k)) delete timestamps[k]
          }
          return {
            messages: [],
            tombstones: tombstoned,
            tombstoneTimestamps: timestamps,
          }
        }),
    }),
    { name: 'cogitate-messages' },
  ),
)

// THE UNREAD COUNT — the derived selector for the indicators.
export const selectUnreadCount = (s: MessageState): number =>
  s.messages.filter((m) => !m.read).length

// THE CROSS-TAB SYNC (2026-09-26 — the standing "the badge says 1 while the
// center says 0" report). The store persists to localStorage, but a tab opened
// BEFORE messages accumulated keeps its own in-memory copy, so two tabs could
// disagree about the queue. `storage` fires in the OTHER tabs when one writes,
// which is what makes this cheap AND loop-free: the writing tab never receives
// its own event, so there is nothing to debounce and no echo to suppress.
if (typeof window !== 'undefined') {
  window.addEventListener('storage', (event) => {
    if (event.key !== 'cogitate-messages') return
    void useMessageStore.persist.rehydrate()
  })
}
