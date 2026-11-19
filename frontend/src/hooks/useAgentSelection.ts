/**
 * Hook for managing agent loading and selection
 * Handles fetching available agents from backend and managing selection state
 */

import { useCallback, useEffect, useRef } from 'react'
import { frontendLoggingService } from '../services/frontendLoggingService'
import { useCognitiveHubStore } from '../stores/cognitiveHubStore'
import { AgentService } from '../services/domain/AgentService'

import type { Agent } from '../types/agentInteraction'


interface UseAgentSelectionReturn {
  agents: Agent[]
  isLoadingAgents: boolean
  selectedAgent: Agent | null
  error: string | null
  selectAgent: (agent: Agent) => void
  reloadAgents: () => Promise<void>
}

export function useAgentSelection(): UseAgentSelectionReturn {
  // Use cognitive hub store for shared state (single source of truth)
  const selectedAgent = useCognitiveHubStore((state) => state.activeAgent)
  const agents = useCognitiveHubStore((state) => state.agents)
  const isLoadingAgents = useCognitiveHubStore((state) => state.isLoadingAgents)
  const error = useCognitiveHubStore((state) => state.agentError)
  const setSelectedAgent = useCognitiveHubStore((state) => state.setActiveAgent)
  const setAgents = useCognitiveHubStore((state) => state.setAgents)
  const setLoadingAgents = useCognitiveHubStore((state) => state.setLoadingAgents)
  const setError = useCognitiveHubStore((state) => state.setAgentError)

  // Service instance (created once per hook instance)
  const agentServiceRef = useRef(new AgentService())

  // Ref to track if initial setup is done
  const initialSetupDoneRef = useRef(false)

  /**
   * Load agents from backend
   */
  const loadAgents = useCallback(async () => {
    try {
      setLoadingAgents(true)
      setError(null)

      const agentsList = await agentServiceRef.current.getAgents()
      setAgents(agentsList)

      setError(null)
    } catch (err) {
      // [TRACE] Log profile loading error
      frontendLoggingService.error('AgentSelection', 'Failed to load profiles', err)
      setError('Failed to load agent profiles')
    } finally {
      setLoadingAgents(false)
    }
  }, [setLoadingAgents, setError, setAgents])

  /**
   * Select an agent
   */
  const handleSelectAgent = useCallback(async (agent: Agent) => {
    // [TRACE] Agent selected
    // traceService.trace('AgentSelection', 'agentSelected', {
      // agentId: agent.id,
      // agentName: agent.name,
      // model: agent.model,
      // provider: agent.provider,
      // source: 'user-action'
    // }, ['data', 'user-action'])

    // Set agent immediately for responsive UI
    setSelectedAgent(agent)
    frontendLoggingService.info('AgentSelection', `Selected agent: ${agent.name}`, {
      agentId: agent.id,
      agentName: agent.name,
      provider: agent.provider,
      model: agent.model
    })

    // FIX: Refresh agent from backend in background to ensure model is current
    // This prevents stale localStorage data from showing wrong model
    // Don't await - let it update in background
    agentServiceRef.current.getAgent(agent.id)
      .then(freshAgent => {
        if (freshAgent) {
          // [TRACE] Agent refresh started
          // traceService.trace('AgentSelection', 'agentRefreshStarted', {
            // agentId: agent.id,
            // cachedModel: agent.model
          // }, ['data', 'sync'])

          if (freshAgent) {
            setSelectedAgent(freshAgent)
            
            // [TRACE] Agent refreshed from backend
            // traceService.trace('AgentSelection', 'agentRefreshed', {
              // agentId: freshAgent.id,
              // agentName: freshAgent.name,
              // provider: freshAgent.provider,
              // model: freshAgent.model,
              // modelChanged: agent.model !== freshAgent.model,
              // source: 'backend'
            // }, ['data', 'sync'])
            
            frontendLoggingService.debug('AgentSelection', `Agent refreshed from backend: ${freshAgent.name}`, {
              agentId: freshAgent.id,
              agentName: freshAgent.name,
              provider: freshAgent.provider,
              model: freshAgent.model
            })
          }
        }
      })
      .catch(error => {
        // Fallback to cached agent if backend unavailable
        frontendLoggingService.warning('AgentSelection', 'Failed to refresh agent from backend, using cached', {
          agentId: agent.id,
          agentName: agent.name,
          error: error instanceof Error ? error.message : 'Unknown error'
        })
      })
  }, [setSelectedAgent])

  /**
   * Reload agents
   */
  const reloadAgents = useCallback(async () => {
    agentServiceRef.current.clearCache()
    await loadAgents()
  }, [loadAgents])

  // Load agents on mount
  useEffect(() => {
    loadAgents()
  }, [loadAgents])

  // Auto-select first agent when agents are loaded (if not already selected)
  // Also restore persisted agent selection
  useEffect(() => {
    if (agents.length > 0 && !initialSetupDoneRef.current && !isLoadingAgents) {
      initialSetupDoneRef.current = true

      // Try to restore previously selected agent
      const restoreAgentSelection = async () => {
        const hubState = useCognitiveHubStore.getState()
        
        // Check if there's an activeAgentId in the store (from localStorage persistence)
        // Note: activeAgent might not be set yet if it's being restored from activeAgentId
        const activeAgentId = hubState.activeAgent?.id
        const persistedActiveAgentId = (hubState as unknown as Record<string, unknown>).activeAgentId as string | undefined
        
        if (activeAgentId) {
          // Agent is already restored, verify it's in the agents list
          const agentStillExists = agents.some(a => String(a.id) === String(activeAgentId))

          if (agentStillExists) {
            // Agent is valid, keep it selected
            // [TRACE] Agent restored from localStorage
            // traceService.trace('AgentSelection', 'agentRestored', {
              // agentId: activeAgentId,
              // agentName: hubState.activeAgent?.name,
              // model: hubState.activeAgent?.model,
              // provider: hubState.activeAgent?.provider,
              // source: 'localStorage',
              // isStale: true  // Mark as stale until refreshed
            // }, ['data', 'lifecycle'])
            
            frontendLoggingService.info('AgentSelection', 'Agent restored from localStorage', {
              agentId: activeAgentId,
              agentName: hubState.activeAgent?.name
            })
            return
          } else {
            // Persisted agent no longer exists in the list, clear it
            frontendLoggingService.warning('AgentSelection', 'Persisted agent no longer available', {
              agentId: activeAgentId
            })
            setSelectedAgent(null)
          }
        } else if (persistedActiveAgentId) {
          // activeAgentId exists but activeAgent not set yet - restore it
          const agentToRestore = agents.find(a => String(a.id) === String(persistedActiveAgentId))
          if (agentToRestore) {
            setSelectedAgent(agentToRestore)
            
            // [TRACE] Agent restored from activeAgentId
            // traceService.trace('AgentSelection', 'agentRestored', {
              // agentId: persistedActiveAgentId,
              // agentName: agentToRestore.name,
              // model: agentToRestore.model,
              // provider: agentToRestore.provider,
              // source: 'localStorage',
              // isStale: true
            // }, ['data', 'lifecycle'])
            
            frontendLoggingService.info('AgentSelection', 'Agent restored from activeAgentId', {
              agentId: persistedActiveAgentId,
              agentName: agentToRestore.name
            })
            return
          }
        }

        // Try to restore from AgentService persistence
        const selectedAgentFromService = await agentServiceRef.current.getSelectedAgent(agents)
        if (selectedAgentFromService) {
          setSelectedAgent(selectedAgentFromService)
          frontendLoggingService.info('AgentSelection', 'Agent restored from AgentService persistence', {
            agentId: selectedAgentFromService.id,
            agentName: selectedAgentFromService.name
          })
        } else if (agents.length > 0) {
          // If restore didn't set an agent, auto-select first
          setSelectedAgent(agents[0])
          frontendLoggingService.info('AgentSelection', `Auto-selected first agent: ${agents[0].name}`)
        } else {
          frontendLoggingService.info('AgentSelection', 'Agents loaded, ready for selection')
        }
      }

      restoreAgentSelection()
    }
  }, [agents, isLoadingAgents, setSelectedAgent])

  return {
    agents,
    isLoadingAgents,
    selectedAgent,
    error,
    selectAgent: handleSelectAgent,
    reloadAgents
  }
}

export default useAgentSelection
