import type { Agent } from '@/types/agentInteraction'
import { profileService } from './ProfileService'
import { frontendLoggingService } from '../frontendLoggingService'

const AGENT_SELECTION_STORAGE_KEY = 'agent-store'

/**
 * AgentService - Manage agent selection and persistence
 *
 * Handles fetching agents from backend, selection logic, and localStorage persistence.
 * Extracted from useAgentSelection.ts
 *
 * @example
 * ```typescript
 * const agentService = new AgentService()
 * const agents = await agentService.getAgents()
 * await agentService.selectAgent('agent-123')
 * const selected = agentService.getSelectedAgent()
 * ```
 */
export class AgentService {
  private selectedAgentId: string | null = null

  /**
   * Get all available agents
   * Caches results to avoid redundant API calls
   *
   * @returns Array of available agents
   */
  async getAgents(): Promise<Agent[]> {
    // NO LOCAL CACHE (2026-09-10). The profiles are the ONE home —
    // ProfileService keeps them in step with the backend. A second copy
    // here went stale the moment an image or a name changed anywhere
    // else, which is exactly how the avatar showed on the profiles page
    // and stayed missing in the chat. Derive, don't duplicate.
    try {
      const loadStartTime = performance.now()
      // Ensure profiles are loaded from backend
      await profileService.loadFromBackend()
      const profiles = profileService.getProfiles()
      const loadDuration = performance.now() - loadStartTime

      // Convert profiles to agents
      const agents = profiles.map(profile => {
        const agent = profileService.convertProfileToAgent(profile)
        // Add freshness metadata for backend-loaded agents
        return {
          ...agent,
          loadedFrom: 'backend' as const,
          lastRefreshed: new Date().toISOString(),
          isStale: false
        }
      })


      frontendLoggingService.debug('AgentService', `Loaded ${profiles.length} profiles`, {
        profileCount: profiles.length,
        duration: loadDuration,
        profiles: profiles.map(p => ({ id: p.id, name: p.name, provider: p.provider, model: p.model }))
      })

      return agents
    } catch (error) {
      frontendLoggingService.error('AgentService', 'Failed to load profiles', error)
      throw new Error('Failed to load agent profiles')
    }
  }

  /**
   * Select an agent by ID
   * Persists selection to localStorage
   *
   * @param agentId - The ID of the agent to select
   * @param agents - Optional agents array (avoids re-fetching)
   * @returns The selected agent
   * @throws Error if agent ID is invalid or not found
   */
  async selectAgent(agentId: string, agents?: Agent[]): Promise<Agent> {
    const agentsList = agents ?? await this.getAgents()

    const agent = agentsList.find(a => String(a.id) === String(agentId))

    if (!agent) {
      frontendLoggingService.error('AgentService', 'Invalid agent ID', { agentId })
      throw new Error(`Agent with ID "${agentId}" not found`)
    }

    this.selectedAgentId = agentId
    this.persistSelection(agentId)

    frontendLoggingService.info('AgentService', `Selected agent: ${agent.name}`, {
      agentId: agent.id,
      agentName: agent.name,
      provider: agent.provider,
      model: agent.model
    })

    return agent
  }

  /**
   * Get the currently selected agent ID
   * Restores from localStorage if available
   *
   * @returns The selected agent ID, or null if none selected
   */
  getSelectedAgentId(): string | null {
    // Return cached ID if available
    if (this.selectedAgentId) {
      return this.selectedAgentId
    }

    // Try to restore from localStorage
    const restored = this.restoreSelectionFromStorage()
    return restored
  }

  /**
   * Get the currently selected agent
   *
   * @param agents - Optional agents array (avoids re-fetching)
   * @returns The selected agent, or null if none selected
   */
  async getSelectedAgent(agents?: Agent[]): Promise<Agent | null> {
    const agentId = this.getSelectedAgentId()
    if (!agentId) {
      return null
    }

    const agentsList = agents ?? await this.getAgents()
    const agent = agentsList.find(a => String(a.id) === String(agentId))

    if (!agent) {
      // Persisted agent no longer exists, clear it
      frontendLoggingService.warning('AgentService', 'Persisted agent not found, clearing', {
        agentId
      })
      this.clearSelection()
      return null
    }

    return agent
  }

  /**
   * Get a single agent by ID (fresh from backend)
   *
   * @param agentId - The ID of the agent to fetch
   * @returns The agent, or null if not found
   */
  async getAgent(agentId: string): Promise<Agent | null> {
    try {
      const profiles = await profileService.getProfiles()
      const profile = profiles.find(p => String(p.id) === String(agentId))

      if (!profile) {
        frontendLoggingService.warning('AgentService', 'Agent not found', { agentId })
        return null
      }

      const agent = profileService.convertProfileToAgent(profile)
      
      // Add freshness metadata
      const freshAgent: Agent = {
        ...agent,
        loadedFrom: 'backend' as const,
        lastRefreshed: new Date().toISOString(),
        isStale: false
      }
      
      frontendLoggingService.debug('AgentService', 'Fetched agent', {
        agentId: freshAgent.id,
        agentName: freshAgent.name,
        model: freshAgent.model,
        loadedFrom: freshAgent.loadedFrom,
        isStale: freshAgent.isStale
      })

      return freshAgent
    } catch (error) {
      frontendLoggingService.error('AgentService', 'Failed to fetch agent', { agentId, error })
      return null
    }
  }

  /**
   * Clear the cache
   * Forces fresh fetch on next getAgents() call
   */
  clearCache(): void {
    // there is no local copy any more — clearing means clearing the ONE
    // home (the next getAgents() refetches from the backend)
    profileService.clearAll()
    frontendLoggingService.debug('AgentService', 'Profile cache cleared')
  }

  /**
   * Clear the selection
   * Removes persisted selection from localStorage
   */
  clearSelection(): void {
    this.selectedAgentId = null
    sessionStorage.removeItem(AGENT_SELECTION_STORAGE_KEY)
    frontendLoggingService.debug('AgentService', 'Selection cleared')
  }

  /**
   * Persist agent selection to localStorage
   */
  private persistSelection(agentId: string): void {
    try {
      const persistedState = {
        selectedAgentId: agentId
      }
      sessionStorage.setItem(AGENT_SELECTION_STORAGE_KEY, JSON.stringify(persistedState))
      frontendLoggingService.debug('AgentService', 'Selection persisted', { agentId })
    } catch (error) {
      frontendLoggingService.warning('AgentService', 'Failed to persist selection', error as unknown as Record<string, unknown>)
    }
  }

  /**
   * Restore agent selection from localStorage
   */
  private restoreSelectionFromStorage(): string | null {
    try {
      const stored = sessionStorage.getItem(AGENT_SELECTION_STORAGE_KEY)
      if (stored) {
        const parsed = JSON.parse(stored)
        const agentId = parsed.selectedAgentId
        if (agentId) {
          this.selectedAgentId = agentId
          frontendLoggingService.debug('AgentService', 'Selection restored from storage', {
            agentId
          })
          return agentId
        }
      }
    } catch (error) {
      frontendLoggingService.warning('AgentService', 'Failed to restore selection', error as unknown as Record<string, unknown>)
    }
    return null
  }
}
