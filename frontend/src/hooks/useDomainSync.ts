/**
 * useDomainSync — THE CROSS-WINDOW PAGE-LEVEL SYNC (2026-08-25, the
 * roadmap Phase 6): the generic form of useCollectionSync /
 * useTeamSync for the remaining page-local domains (the tools, the
 * agent lists, the registry, the packages, the permissions, the
 * workflow lists). The pages hold local state — this hook
 * subscribes them to the bus's <domain>:<id>:<event> announcements
 * and calls the page's reload.
 */
import { useEffect } from 'react'
import { eventBus } from '../services/eventBus'
import { addTopics, removeTopics } from '../services/messagingFeed'

/** The topics the sync needs: <domain>:* (the mutation events). */
export const DOMAIN_SYNC_TOPICS = {
  tool: 'tool:*,tool-category:*',
  'agent-list': 'agent-list:*',
  'agent-registry': 'agent-registry:*',
  'agent-package': 'agent-package:*',
  'tool-permission': 'tool-permission:*',
  'workflow-list': 'workflow-list:*',
  // The trash: a purge or an empty in one tab must not leave another rendering a
  // row that is gone. The payload's `id` is the SHELF and its `event` is
  // restored/purged/emptied — the kind rides in the payload because the bus hands
  // a handler only the payload, so a `trash:*` subscriber could not tell them
  // apart otherwise.
  trash: 'trash:*',
} as const

export function useDomainSync(
  domain: keyof typeof DOMAIN_SYNC_TOPICS,
  onEvent?: (payload: { id?: string | number; event?: string; name?: string }) => void,
  enabled = true,
): void {
  useEffect(() => {
    if (!enabled) return

    const topics = DOMAIN_SYNC_TOPICS[domain]
    addTopics(topics)
    const unsub = eventBus.subscribe(`${domain}:*`, (payload) => {
      const p = (payload ?? {}) as { id?: string | number; event?: string; name?: string }
      if (p.id === undefined) return
      onEvent?.(p)
    })

    return () => {
      unsub()
      removeTopics(topics)
    }
  }, [domain, enabled, onEvent])
}
