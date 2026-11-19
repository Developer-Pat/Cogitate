/**
 * useAgentSync — the cross-window sync consumer (2026-08-24).
 *
 * The user's use case: agent profiles open in one window, the chat
 * page in another — changing an agent config here updates the chat
 * page there. Each window has its own SSE connection to the
 * backend (the single source of truth); the backend publishes
 * 'agent:<id>:updated'; this hook hears it and invalidates the
 * React Query cache — every page using the agent keys refetches.
 *
 * Mounted once in the app shell (the useNotifyBridge pattern).
 * The invalidation: ['agents'] (the list) + ['agent', id] (the
 * detail) + ['agent-metrics', id] (the metrics).
 */

import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { eventBus } from '../services/eventBus'
import { addTopics, removeTopics } from '../services/messagingFeed'
import { apiClient } from '../services/apiClient'
import { useCognitiveHubStore } from '../stores/cognitiveHubStore'
import { IdService } from '../services/domain/IdService'
import type { Agent } from '../types/agentInteraction'

interface AgentUpdated {
  agent_id?: number
  agent_name?: string
  event?: string
}

/** The topics the sync needs: agent:* (the update events). */
export const SYNC_TOPICS = 'agent:*'

export function useAgentSync(enabled = true): void {
  const queryClient = useQueryClient()

  useEffect(() => {
    if (!enabled) return

    // register the sync topics (the feed maintains the union)
    addTopics(SYNC_TOPICS)

    // the wildcard matches 'agent:<id>:updated' (a trailing '*')
    const unsub = eventBus.subscribe('agent:*', (payload) => {
      const p = (payload ?? {}) as AgentUpdated
      const id = p.agent_id
      if (id === undefined) return

      // THE EVENT SWITCH (2026-08-25, the roadmap Phase 2): the
      // backend now announces created/updated/deleted — the deleted
      // agent must LEAVE the shared store, not just refresh.
      if (p.event === 'deleted') {
        const hub = useCognitiveHubStore.getState()
        hub.setAgents(hub.agents.filter(a => !IdService.equals(a.id, String(id))))
        queryClient.invalidateQueries({ queryKey: ['agents'] })
        return
      }

      // THE CROSS-WINDOW REFRESH: invalidate the agent queries —
      // every open page (this window + the others) refetches.
      queryClient.invalidateQueries({ queryKey: ['agents'] })
      queryClient.invalidateQueries({ queryKey: ['agent', id] })
      queryClient.invalidateQueries({ queryKey: ['agent-metrics', id] })

      // THE STORE WIRING (2026-08-24, the live-test gap): the chat
      // page's agent list comes from the CognitiveHubStore (Zustand),
      // NOT the React Query keys — the invalidation alone had
      // nothing mounted to refetch. Fetch the changed agent fresh +
      // update the store in place (the CognitiveHubProvider's
      // mapping), so the visible list updates.
      void refreshHubAgent(id)
    })

    // THE CLEANUP RULE: unsubscribe + disconnect on unmount.
    return () => {
      unsub()
      removeTopics(SYNC_TOPICS)
    }
  }, [enabled, queryClient])
}

/** Fetch the changed agent + update the hub store in place. */
async function refreshHubAgent(agentId: number): Promise<void> {
  try {
    const res = await apiClient.get<{
      id: number; name: string; model: string; provider?: string;
      description?: string; parameters?: Record<string, unknown>;
      is_active?: boolean;
    }>(`/api/v1/agents/${agentId}`)
    if (!res.data) return
    const d = res.data
    const fresh: Agent = {
      id: IdService.toFrontend(String(d.id)),
      name: d.name,
      model: d.model,
      provider: d.provider || 'ollama',
      description: d.description || '',
      capabilities: [],
      parameters: d.parameters || {},
      isAvailable: d.is_active ?? true,
      loadedFrom: 'backend' as const,
      lastRefreshed: new Date().toISOString(),
      isStale: false,
    }
    const hub = useCognitiveHubStore.getState()
    hub.setAgents(hub.agents.map(a => (IdService.equals(a.id, fresh.id) ? fresh : a)))
    if (hub.activeAgent && IdService.equals(hub.activeAgent.id, fresh.id)) {
      hub.setActiveAgent(fresh)
    }
  } catch (e) {
    // the sync must never break the app — log + move on
    console.warn('[useAgentSync] hub refresh failed for agent', agentId, e)
  }
}
