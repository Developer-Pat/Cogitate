/**
 * useTeamSync — THE CROSS-WINDOW TEAM SYNC (2026-08-25, the roadmap
 * Phase 4): the teams' page holds page-local state — this hook
 * subscribes it to the bus's team:<id>:<event> announcements and
 * calls the page's reload (the same shape as useCollectionSync).
 */
import { useEffect } from 'react'
import { eventBus } from '../services/eventBus'
import { addTopics, removeTopics } from '../services/messagingFeed'

/** The topics the sync needs: team:* (the mutation events). */
export const TEAM_SYNC_TOPICS = 'team:*'

export function useTeamSync(onEvent?: (payload: { team_id?: string; event?: string; name?: string }) => void, enabled = true): void {
  useEffect(() => {
    if (!enabled) return

    addTopics(TEAM_SYNC_TOPICS)
    const unsub = eventBus.subscribe('team:*', (payload) => {
      const p = (payload ?? {}) as { team_id?: string; event?: string; name?: string }
      if (p.team_id === undefined) return
      onEvent?.(p)
    })

    return () => {
      unsub()
      removeTopics(TEAM_SYNC_TOPICS)
    }
  }, [enabled, onEvent])
}
