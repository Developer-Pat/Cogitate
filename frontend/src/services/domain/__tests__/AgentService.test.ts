import { describe, it, expect, beforeEach, vi } from 'vitest'
import { AgentService } from '../AgentService'
import type { Agent } from '@/types/agentInteraction'

// Mock profileService - MUST be before any imports that use it
vi.mock('../ProfileService', () => ({
  profileService: {
    loadFromBackend: vi.fn(),
    getProfiles: vi.fn(),
    clearAll: vi.fn(),
    convertProfileToAgent: vi.fn((profile: Record<string, unknown>) => ({
      id: profile.id,
      name: profile.name,
      description: profile.description,
      capabilities: profile.tools || [],
      provider: profile.provider,
      model: profile.model,
      parameters: {
        // MIRRORS THE REAL MAPPER (G4): an undeclared field stays UNDECLARED. There is no
        // `|| 0.7` fallback here, because the arc removed exactly that from the mapper this
        // stands in for — and a truthiness check would also drop a legal temperature of 0.
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        temperature: (profile.parameters as any)?.temperature,
        // No budget: the client's Agent shape carries sampling settings only.
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        topP: (profile.parameters as any)?.top_p
      },
      isAvailable: true,
      profileImageUrl: profile.image_url
    }))
  }
}))

// Now import profileService to get the mocked version
import { profileService } from '../ProfileService'
import type { Profile } from '../ProfileService'

// Mock sessionStorage — the per-tab selection store (2026-09-10:
// the selection moved off localStorage so parallel tabs stop clobbering
// each other's agent)
const sessionStorageMock = {
  store: {} as Record<string, string>,
  getItem: vi.fn(function(this: { store: Record<string, string> }, key: string) { return this.store[key] || null }),
  setItem: vi.fn(function(this: { store: Record<string, string> }, key: string, value: string) { this.store[key] = value }),
  removeItem: vi.fn(function(this: { store: Record<string, string> }, key: string) { delete this.store[key] }),
  clear: vi.fn(function(this: { store: Record<string, string> }) { this.store = {} })
}

Object.defineProperty(globalThis, 'sessionStorage', {
  value: sessionStorageMock
})

// Mock frontendLoggingService
vi.mock('@/services/frontendLoggingService', () => ({
  frontendLoggingService: {
    debug: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
    error: vi.fn()
  }
}))

describe('AgentService', () => {
  let service: AgentService

  beforeEach(() => {
    service = new AgentService()
    vi.clearAllMocks()
    sessionStorageMock.clear()
  })

  describe('getAgents', () => {
    const mockProfiles: Profile[] = [
      {
        id: 'agent-1',
        name: 'Assistant',
        description: 'A helpful assistant',
        provider: 'openai',
        model: 'gpt-4',
        system_prompt: 'You are helpful',
        tools: ['search'],
        memory: true,
        // THE FIXTURE DECLARES WHAT THE ASSERTION EXPECTS (G4): this pair used to be
        // half-written (temperature only) and the expectation still read 0.9 for `topP`,
        // which only passed because the mapper invented it. A profile that declares both
        // is a profile whose pair survives the conversion intact.
        parameters: {
          temperature: 0.7,
          top_p: 0.9
        }
      },
      {
        id: 'agent-2',
        name: 'Coder',
        description: 'A coding assistant',
        provider: 'anthropic',
        model: 'claude-3',
        system_prompt: 'You code well',
        tools: ['editor'],
        memory: false,
        parameters: {
          temperature: 0.5
        }
      }
    ]

    it('should fetch and convert profiles to agents', async () => {
      vi.mocked(profileService.loadFromBackend).mockResolvedValue(undefined)
      vi.mocked(profileService.loadFromBackend).mockResolvedValue(undefined)
      vi.mocked(profileService.getProfiles).mockReturnValue(mockProfiles)

      const agents = await service.getAgents()

      expect(agents).toHaveLength(2)
      expect(agents[0]).toMatchObject({
        id: 'agent-1',
        name: 'Assistant',
        description: 'A helpful assistant',
        capabilities: ['search'],
        provider: 'openai',
        model: 'gpt-4',
        parameters: {
          temperature: 0.7,
          topP: 0.9
        },
        isAvailable: true,
        profileImageUrl: undefined
      })
      expect(agents[1].id).toBe('agent-2')
      expect(profileService.loadFromBackend).toHaveBeenCalledTimes(1)
    })

    it('reads through to the profiles on every call (no local cache by design)', async () => {
      // There is deliberately NO local copy of the agents (see getAgents():
      // "derive, don't duplicate"). Every call must go back to the ONE home,
      // so loadFromBackend is expected on BOTH calls — caching here was
      // removed because a second copy went stale when an image or name changed.
      vi.mocked(profileService.loadFromBackend).mockResolvedValue(undefined)
      vi.mocked(profileService.getProfiles).mockReturnValue(mockProfiles)

      await service.getAgents()
      await service.getAgents()

      expect(profileService.loadFromBackend).toHaveBeenCalledTimes(2)
    })

    it('should clear cache when clearCache is called', async () => {
      vi.mocked(profileService.loadFromBackend).mockResolvedValue(undefined)
      vi.mocked(profileService.getProfiles).mockReturnValue(mockProfiles)

      await service.getAgents()
      service.clearCache()
      await service.getAgents()

      expect(profileService.loadFromBackend).toHaveBeenCalledTimes(2)
    })

    it('should handle empty profiles list', async () => {
      vi.mocked(profileService.loadFromBackend).mockResolvedValue(undefined)
      vi.mocked(profileService.getProfiles).mockReturnValue([])

      const agents = await service.getAgents()

      expect(agents).toHaveLength(0)
    })

    it('should throw error when profileService fails', async () => {
      vi.mocked(profileService.loadFromBackend).mockRejectedValue(new Error('Network error'))

      await expect(service.getAgents()).rejects.toThrow('Failed to load agent profiles')
    })

    it('carries no sampling when the profile declares none', async () => {
      const minimalProfile: Profile = {
        id: 'minimal',
        name: 'Minimal',
        description: 'No params',
        provider: 'openai',
        model: 'gpt-3.5',
        system_prompt: 'Be minimal',
        tools: [],
        memory: false
      }

      vi.mocked(profileService.loadFromBackend).mockResolvedValue(undefined)
      vi.mocked(profileService.getProfiles).mockReturnValue([minimalProfile])

      const agents = await service.getAgents()

      // NOTHING DECLARED CARRIES NOTHING (G4): this used to assert a 0.7/0.9 pair, which
      // was the mapper's own invention rather than anything the row said. An agent that
      // declares no sampling reaches the UI with neither field set, and the server's
      // resolution (the provider's own default) is what a turn runs on.
      expect(agents[0].parameters.temperature).toBeUndefined()
      expect(agents[0].parameters.topP).toBeUndefined()
    })

    it('should include profile image URL when available', async () => {
      const profileWithImage: Profile = {
        ...mockProfiles[0],
        image_url: '/images/agent.png'
      }

      vi.mocked(profileService.loadFromBackend).mockResolvedValue(undefined)
      vi.mocked(profileService.getProfiles).mockReturnValue([profileWithImage])

      const agents = await service.getAgents()

      expect(agents[0].profileImageUrl).toBe('/images/agent.png')
    })
  })

  describe('selectAgent', () => {
    const mockAgents: Agent[] = [
      {
        id: 'agent-1',
        name: 'Assistant',
        description: 'A helpful assistant',
        capabilities: ['search'],
        provider: 'openai',
        model: 'gpt-4',
        parameters: {
          temperature: 0.7,
          topP: 0.9
        },
        isAvailable: true
      },
      {
        id: 'agent-2',
        name: 'Coder',
        description: 'A coding assistant',
        capabilities: ['editor'],
        provider: 'anthropic',
        model: 'claude-3',
        parameters: {
          temperature: 0.5,
          topP: 0.9
        },
        isAvailable: true
      }
    ]

    beforeEach(() => {
      vi.mocked(profileService.loadFromBackend).mockResolvedValue(undefined)
      vi.mocked(profileService.getProfiles).mockReturnValue([
        {
          id: 'agent-1',
          name: 'Assistant',
          description: 'A helpful assistant',
          provider: 'openai',
          model: 'gpt-4',
          system_prompt: 'You are helpful',
          tools: ['search'],
          memory: true,
          parameters: { temperature: 0.7 }
        },
        {
          id: 'agent-2',
          name: 'Coder',
          description: 'A coding assistant',
          provider: 'anthropic',
          model: 'claude-3',
          system_prompt: 'You code well',
          tools: ['editor'],
          memory: false,
          parameters: { temperature: 0.5 }
        }
      ])
    })

    it('should select valid agent and persist to sessionStorage', async () => {
      await service.getAgents()

      const selected = await service.selectAgent('agent-1')

      expect(selected.id).toBe('agent-1')
      expect(selected.name).toBe('Assistant')
      expect(sessionStorageMock.setItem).toHaveBeenCalledWith(
        'agent-store',
        expect.stringContaining('agent-1')
      )
    })

    it('should throw error for invalid agent ID', async () => {
      await service.getAgents()

      await expect(service.selectAgent('non-existent')).rejects.toThrow(
        'Agent with ID "non-existent" not found'
      )
    })

    it('should accept optional agents array to avoid re-fetching', async () => {
      const selected = await service.selectAgent('agent-2', mockAgents)

      expect(selected.id).toBe('agent-2')
      expect(profileService.loadFromBackend).not.toHaveBeenCalled()
    })

    it('should fetch agents if cache is empty and no agents provided', async () => {
      const selected = await service.selectAgent('agent-1')

      expect(profileService.loadFromBackend).toHaveBeenCalledTimes(1)
      expect(selected.id).toBe('agent-1')
    })

    it('should handle string ID comparison correctly', async () => {
      await service.getAgents()

      // Should work with string comparison
      const selected = await service.selectAgent('agent-1')

      expect(selected).toBeDefined()
    })
  })

  describe('getSelectedAgentId', () => {
    it('should return null when no agent is selected', () => {
      const selectedId = service.getSelectedAgentId()
      expect(selectedId).toBeNull()
    })

    it('should return cached ID after selection', async () => {
      vi.mocked(profileService.loadFromBackend).mockResolvedValue(undefined)
      vi.mocked(profileService.getProfiles).mockReturnValue([
        {
          id: 'agent-1',
          name: 'Assistant',
          description: 'A helpful assistant',
          provider: 'openai',
          model: 'gpt-4',
          system_prompt: 'You are helpful',
          tools: ['search'],
          memory: true,
          parameters: { temperature: 0.7 }
        }
      ])

      await service.selectAgent('agent-1')

      const selectedId = service.getSelectedAgentId()
      expect(selectedId).toBe('agent-1')
    })

    it('should restore ID from sessionStorage', () => {
      sessionStorageMock.setItem(
        'agent-store',
        JSON.stringify({ selectedAgentId: 'restored-agent' })
      )

      const selectedId = service.getSelectedAgentId()
      expect(selectedId).toBe('restored-agent')
    })
  })

  describe('getSelectedAgent', () => {
    const mockAgents: Agent[] = [
      {
        id: 'agent-1',
        name: 'Assistant',
        description: 'A helpful assistant',
        capabilities: ['search'],
        provider: 'openai',
        model: 'gpt-4',
        parameters: {
          temperature: 0.7,
          topP: 0.9
        },
        isAvailable: true
      }
    ]

    it('should return null when no agent is selected', async () => {
      const selected = await service.getSelectedAgent()
      expect(selected).toBeNull()
    })

    it('should return selected agent after selection', async () => {
      vi.mocked(profileService.loadFromBackend).mockResolvedValue(undefined)
      vi.mocked(profileService.getProfiles).mockReturnValue([
        {
          id: 'agent-1',
          name: 'Assistant',
          description: 'A helpful assistant',
          provider: 'openai',
          model: 'gpt-4',
          system_prompt: 'You are helpful',
          tools: ['search'],
          memory: true,
          parameters: { temperature: 0.7 }
        }
      ])

      await service.selectAgent('agent-1')

      const selected = await service.getSelectedAgent()
      expect(selected?.id).toBe('agent-1')
      expect(selected?.name).toBe('Assistant')
    })

    it('should accept optional agents array', async () => {
      sessionStorageMock.setItem(
        'agent-store',
        JSON.stringify({ selectedAgentId: 'agent-1' })
      )

      const selected = await service.getSelectedAgent(mockAgents)

      expect(selected?.id).toBe('agent-1')
    })

    it('should clear selection if persisted agent not found', async () => {
      sessionStorageMock.setItem(
        'agent-store',
        JSON.stringify({ selectedAgentId: 'non-existent' })
      )

      vi.mocked(profileService.loadFromBackend).mockResolvedValue(undefined)
      vi.mocked(profileService.getProfiles).mockReturnValue([
        {
          id: 'agent-1',
          name: 'Assistant',
          description: 'A helpful assistant',
          provider: 'openai',
          model: 'gpt-4',
          system_prompt: 'You are helpful',
          tools: ['search'],
          memory: true,
          parameters: { temperature: 0.7 }
        }
      ])

      const selected = await service.getSelectedAgent()

      expect(selected).toBeNull()
      expect(sessionStorageMock.removeItem).toHaveBeenCalledWith('agent-store')
    })
  })

  describe('clearSelection', () => {
    it('should clear selected agent ID and sessionStorage', async () => {
      vi.mocked(profileService.loadFromBackend).mockResolvedValue(undefined)
      vi.mocked(profileService.getProfiles).mockReturnValue([
        {
          id: 'agent-1',
          name: 'Assistant',
          description: 'A helpful assistant',
          provider: 'openai',
          model: 'gpt-4',
          system_prompt: 'You are helpful',
          tools: ['search'],
          memory: true,
          parameters: { temperature: 0.7 }
        }
      ])

      await service.selectAgent('agent-1')
      service.clearSelection()

      expect(service.getSelectedAgentId()).toBeNull()
      expect(sessionStorageMock.removeItem).toHaveBeenCalledWith('agent-store')
    })
  })

  describe('integration: full workflow', () => {
    it('should load agents, select one, and restore on new instance', async () => {
      const mockProfiles: Profile[] = [
        {
          id: 'agent-1',
          name: 'Assistant',
          description: 'A helpful assistant',
          provider: 'openai',
          model: 'gpt-4',
          system_prompt: 'You are helpful',
          tools: ['search'],
          memory: true,
          parameters: { temperature: 0.7 }
        }
      ]

      vi.mocked(profileService.loadFromBackend).mockResolvedValue(undefined)
      vi.mocked(profileService.getProfiles).mockReturnValue(mockProfiles)

      // First service instance: load and select
      const service1 = new AgentService()
      const agents = await service1.getAgents()
      await service1.selectAgent('agent-1')

      // Second service instance: should restore selection
      const service2 = new AgentService()
      const restoredId = service2.getSelectedAgentId()
      expect(restoredId).toBe('agent-1')

      // Get selected agent with agents array
      const selected = await service2.getSelectedAgent(agents)
      expect(selected?.id).toBe('agent-1')
    })

    it('should handle cache invalidation correctly', async () => {
      const mockProfiles: Profile[] = [
        {
          id: 'agent-1',
          name: 'Assistant',
          description: 'A helpful assistant',
          provider: 'openai',
          model: 'gpt-4',
          system_prompt: 'You are helpful',
          tools: ['search'],
          memory: true,
          parameters: { temperature: 0.7 }
        }
      ]

      vi.mocked(profileService.loadFromBackend).mockResolvedValue(undefined)
      vi.mocked(profileService.getProfiles).mockReturnValue(mockProfiles)

      // Load agents
      await service.getAgents()
      expect(profileService.loadFromBackend).toHaveBeenCalledTimes(1)

      // Clear cache
      service.clearCache()

      // Load again - should fetch from backend
      await service.getAgents()
      expect(profileService.loadFromBackend).toHaveBeenCalledTimes(2)
    })
  })
})
