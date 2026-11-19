/**
 * useMacroSync — THE CROSS-WINDOW MACRO SYNC (2026-08-25, the
 * roadmap Phase 5): the macro sets + the meta-topics' CRUD now
 * announce on the bus; this hook (mounted in the AppSyncBridge —
 * the macro store's SHARED, unlike the page-local collections!)
 * reloads the store in every open tab.
 */
import { useEffect } from 'react'
import { eventBus } from '../services/eventBus'
import { addTopics, removeTopics } from '../services/messagingFeed'
import { useSystemMacrosStore } from '../stores/macroSetsStore'

/** The topics the sync needs: the macro sets + the meta-topics. */
export const MACRO_SYNC_TOPICS = 'macro:*,meta-topic:*'

export function useMacroSync(enabled = true): void {
  useEffect(() => {
    if (!enabled) return

    addTopics(MACRO_SYNC_TOPICS)

    const unsubA = eventBus.subscribe('macro:*', () => {
      void useSystemMacrosStore.getState().reloadMacros()
    })
    const unsubB = eventBus.subscribe('meta-topic:*', () => {
      void useSystemMacrosStore.getState().reloadMacros()
    })

    return () => {
      unsubA()
      unsubB()
      removeTopics(MACRO_SYNC_TOPICS)
    }
  }, [enabled])
}
