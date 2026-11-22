/**
 * Cognitive Hub Provider
 *
 * Boot initialization component for Cognitive Hub.
 * Mounts once at app root, hydrates state from persistence, polls provider health.
 *
 * This is a plain React component (NOT a context provider).
 * The Zustand store is the source of truth.
 *
 * @see docs/hub/PHASED-IMPLEMENTATION-PLAN.md
 */

import { useEffect, useRef } from 'react'
import { useCognitiveHubStore } from '../stores/cognitiveHubStore'
import { apiClient } from '../services/apiClient'
import { startRetryProcessor, stopRetryProcessor } from '../services/offlineSyncQueue'
import { IdService } from '../services/domain/IdService'

import { frontendLoggingService } from '../services/frontendLoggingService'
import type { Agent, ConversationSession } from '../types/agentInteraction'
import type { components } from '../types/api.generated'

interface CognitiveHubProviderProps {
  children: React.ReactNode
}

export function CognitiveHubProvider({ children }: CognitiveHubProviderProps) {
  const hubStore = useCognitiveHubStore()
  const hasHydratedRef = useRef(false)

  /**
   * Hydrate agent and session from persisted IDs on boot
   * This runs ONCE when app mounts (prevented by hasHydratedRef)
   */
  useEffect(() => {
    // Prevent re-hydration on re-renders
    if (hasHydratedRef.current) return
    hasHydratedRef.current = true

    const hydrate = async () => {
      // Access persisted state from the SAME storage the store writes to
      // (the per-tab doctrine, 2026-09-10: the hub store persists to
      // sessionStorage; reading localStorage here would desync the two
      // hydration paths).
      // Zustand persist stores data under the name we specified
      let persistedState: { activeAgentId?: string | null; activeSessionId?: string | null; persistenceScope?: string; agents?: unknown[] } | null = null

      try {
        const stored = sessionStorage.getItem('cogitate-hub-storage')
        if (stored) {
          // Handle corrupted localStorage data
          try {
            persistedState = JSON.parse(stored)
          } catch {
            // Corrupted data - clear it and start fresh
            sessionStorage.removeItem('cogitate-hub-storage')
          }
        }
      } catch {
        // Silently ignore - will use default state
      }

      if (!persistedState) {
        return
      }

      const { activeAgentId, activeSessionId, agents } = persistedState

      // Hydrate agents if persisted
      if (agents && agents.length > 0) {
        hubStore.setAgents(agents as Agent[])
      }

      // Hydrate active agent
      if (activeAgentId && hubStore.agents.length > 0) {
        const agent = hubStore.agents.find(a => IdService.equals(a.id, activeAgentId))
        if (agent) {
          hubStore.setActiveAgent(agent)
          
          // [TRACE] Agent loaded from localStorage
          // traceService.trace('CognitiveHubProvider', 'agentLoaded', {
            // agentId: activeAgentId,
            // agentName: agent.name,
            // model: agent.model,
            // provider: agent.provider,
            // source: 'localStorage',
            // isStale: true  // Mark as stale until refreshed
          // }, ['data', 'lifecycle'])
        }

        // FIX: Always refresh active agent from backend to ensure model is current
        // This prevents stale localStorage data from showing wrong model in metadata
        // See: wiki/dev-notes/agents/cognitive-hub.md
        try {
          const response = await apiClient.get<components['schemas']['AgentResponse']>(`/api/v1/agents/${activeAgentId}`)
          if (response.data) {
            const freshAgent: Agent = {
              id: IdService.toFrontend(String(response.data.id)),
              name: response.data.name,
              model: response.data.model,  // ✅ Always fresh from backend
              provider: response.data.provider,
              description: response.data.description || '',
              capabilities: [],
              parameters: response.data.parameters || {},
              isAvailable: response.data.is_active ?? true,
              // Freshness metadata
              loadedFrom: 'backend' as const,
              lastRefreshed: new Date().toISOString(),
              isStale: false
            }

            // Update in store
            const agents = hubStore.agents.map(a =>
              IdService.equals(a.id, activeAgentId) ? freshAgent : a
            )
            hubStore.setAgents(agents)
            hubStore.setActiveAgent(freshAgent)

            // [TRACE] Agent refreshed from backend
            // traceService.trace('CognitiveHubProvider', 'agentRefreshed', {
              // agentId: activeAgentId,
              // agentName: freshAgent.name,
              // oldModel: agent?.model,
              // newModel: freshAgent.model,
              // modelChanged: agent?.model !== freshAgent.model,
              // source: 'backend',
              // isStale: false
            // }, ['data', 'sync'])

            frontendLoggingService.info('CognitiveHubProvider', 'Refreshed agent from backend', {
              agentId: activeAgentId,
              model: freshAgent.model
            })
          }
        } catch (error) {
          // Silently ignore - localStorage version will be used
          frontendLoggingService.warning('CognitiveHubProvider', 'Failed to refresh agent from backend, using cached version', {
            agentId: activeAgentId,
            error: error instanceof Error ? error.message : 'Unknown error'
          })
        }
      } else if (activeAgentId && hubStore.agents.length === 0) {
        // Agents not in localStorage, load from backend
        try {
          const response = await apiClient.get<components['schemas']['AgentListResponse']>('/api/v1/agents')
          if (response.data?.agents) {
            const agentsList: Agent[] = response.data.agents.map((a: components['schemas']['AgentResponse']) => ({
              id: IdService.toFrontend(String(a.id)),
              name: a.name,
              model: a.model,
              provider: a.provider || 'ollama',
              description: a.description || '',
              capabilities: [],
              parameters: a.parameters || {},
              isAvailable: a.is_active ?? true,
              // Freshness metadata
              loadedFrom: 'backend' as const,
              lastRefreshed: new Date().toISOString(),
              isStale: false
            }))
            hubStore.setAgents(agentsList)

            // Now find the persisted agent
            const agent = agentsList.find((a: Agent) => IdService.equals(a.id, activeAgentId))
            if (agent) {
              hubStore.setActiveAgent(agent)
              
              // [TRACE] Agent loaded from backend
              // traceService.trace('CognitiveHubProvider', 'agentLoaded', {
                // agentId: activeAgentId,
                // agentName: agent.name,
                // model: agent.model,
                // provider: agent.provider,
                // source: 'backend',
                // isStale: false
              // }, ['data', 'lifecycle'])
            }
          }
        } catch {
          // Silently ignore - agent may not exist
        }
      }

      // Hydrate active session ONLY if not already set
      // Note: We don't auto-load the most recent session - user selects manually
      if (activeSessionId && !hubStore.activeSession) {
        try {
          const backendSession = await apiClient.get(`/api/v1/sessions/${activeSessionId}`)
          if (backendSession.data) {
            // FIX: Use the actual title, not a fallback
            // The title should already be unique (e.g., "New Session {timestamp}")
            const sessionData = backendSession.data as Record<string, unknown>
            const sessionTitle = sessionData.title as string || `New Session ${Date.now()}`
            
            const session = {
              id: IdService.toFrontend(sessionData.id as string),
              title: sessionTitle,
              agentId: IdService.toFrontend(sessionData.agent_id as string),
              messages: ((sessionData.messages as unknown as Record<string, unknown>[]) || []).map((msg: Record<string, unknown>) => {
                const m = msg as Record<string, unknown>
                return {
                  id: IdService.toFrontend(m.id as string),
                  role: m.role as string,
                  content: m.content as string,
                  timestamp: new Date(m.created_at as string),
                  agentId: IdService.toFrontend(sessionData.agent_id as string)
                }
              }),
              updatedAt: new Date(),
              createdAt: new Date()
            }
            hubStore.setActiveSession(session as ConversationSession)
            hubStore.upsertSession(session as ConversationSession)
          }
        } catch {
          // Session may have been deleted, clear persisted ID
          hubStore.setActiveSession(null)
        }
      }
    }

    hydrate()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  /**
   * Sync persistence scope to scoped storage
   */
  useEffect(() => {
    // This is handled automatically by Zustand persist middleware
  }, [hubStore.persistenceScope])

  /**
   * Start offline sync queue processor on mount
   */
  useEffect(() => {
    // Start retry processor
    startRetryProcessor()

    // Stop on unmount
    return () => {
      stopRetryProcessor()
    }
  }, [])

  return <>{children}</>
}

export default CognitiveHubProvider
