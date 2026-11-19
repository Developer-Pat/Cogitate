/**
 * useSessionSync — THE CROSS-WINDOW SESSION SYNC (2026-08-25, the
 * user's audit catch: the sessions' mutations update the same-page
 * surfaces but the OTHER TABS stay stale). Hears the bus's
 * session:<id>:<event> announcements (the backend's router now
 * publishes them — the agents' adopt-announce pattern) and applies
 * them to the shared hub store, so every open tab converges.
 */
import { useEffect } from 'react'
import { eventBus } from '../services/eventBus'
import { addTopics, removeTopics } from '../services/messagingFeed'
import { useCognitiveHubStore } from '../stores/cognitiveHubStore'
import { sessionsService } from '../services/domain/SessionsService'
import { frontendLoggingService } from '../services/frontendLoggingService'

/** The topics the sync needs: session:* (the mutation events). */
export const SESSION_SYNC_TOPICS = 'session:*'

interface SessionEvent {
  session_id?: string | number
  title?: string
  event?: string
}

export function useSessionSync(enabled = true): void {
  useEffect(() => {
    if (!enabled) return

    addTopics(SESSION_SYNC_TOPICS)

    const unsub = eventBus.subscribe('session:*', (payload) => {
      const p = (payload ?? {}) as SessionEvent

      // THE BULK WIPE COMES FIRST (2026-09-19): session:all:cleared /
      // session:all:deleted_all carries no single session id, so the id
      // guard below would silently drop it — and a Clear All in another
      // window would leave this tab rendering rows that no longer exist.
      // A bulk wipe means the list itself changed: reload it.
      if (p.event === 'cleared' || p.event === 'deleted_all') {
        void sessionsService.loadFromBackend(false).catch((err) => {
          frontendLoggingService.error(
            'SessionSync',
            'Failed to refresh after a bulk session wipe in another window',
            err
          )
        })
        return
      }

      const id = p.session_id
      if (id === undefined) return

      // THE EVENT SWITCH: apply the mutation to the shared store —
      // every open tab (this window + the others) converges.
      switch (p.event) {
        case 'deleted':
          useCognitiveHubStore.getState().removeSession(String(id))
          break
        case 'updated':
          if (p.title) {
            useCognitiveHubStore.getState().renameSessionById(String(id), p.title)
          }
          break
        case 'created':
          // the other window's new session — refresh the list
          void sessionsService.loadFromBackend(false).catch((err) => {
            frontendLoggingService.error('SessionSync', 'Failed to refresh after a session created elsewhere', err)
          })
          break
        default:
          // the unknown event — a refresh is the safe fallback
          void sessionsService.loadFromBackend(false).catch(() => {})
      }
    })

    return () => {
      unsub()
      removeTopics(SESSION_SYNC_TOPICS)
    }
  }, [enabled])
}
