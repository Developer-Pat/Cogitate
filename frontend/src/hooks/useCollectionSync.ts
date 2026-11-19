/**
 * useCollectionSync — THE CROSS-WINDOW COLLECTION SYNC (2026-08-25,
 * the roadmap Phase 3): the collections' pages hold page-local
 * state (no shared store) — this hook subscribes the page to the
 * bus's collection:<id>:<event> announcements and calls the page's
 * reload. The backend's mutations now announce (the kits' CRUD —
 * the names feed the PackageTab + the pickers).
 */
import { useEffect } from 'react'
import { eventBus } from '../services/eventBus'
import { addTopics, removeTopics } from '../services/messagingFeed'

/** The topics the sync needs: collection:* (the mutation events). */
export const COLLECTION_SYNC_TOPICS = 'collection:*'

export function useCollectionSync(onEvent?: (payload: { collection_id?: string; event?: string; name?: string }) => void, enabled = true): void {
  useEffect(() => {
    if (!enabled) return

    addTopics(COLLECTION_SYNC_TOPICS)
    const unsub = eventBus.subscribe('collection:*', (payload) => {
      const p = (payload ?? {}) as { collection_id?: string; event?: string; name?: string }
      if (p.collection_id === undefined) return
      onEvent?.(p)
    })

    return () => {
      unsub()
      removeTopics(COLLECTION_SYNC_TOPICS)
    }
  }, [enabled, onEvent])
}
