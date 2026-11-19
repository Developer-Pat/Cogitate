import { describe, it, expect, beforeEach, vi } from 'vitest'

// Mock apiClient + logging before importing the service
vi.mock('@/services/apiClient', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn()
  }
,
  API_BASE_URL: 'http://test'
}))

vi.mock('@/services/frontendLoggingService', () => ({
  frontendLoggingService: {
    debug: vi.fn(),
    info: vi.fn(),
    error: vi.fn(),
    warning: vi.fn()
  }
}))

import { profileService } from '../ProfileService'

describe('ProfileService health mapping (F3)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('convertProfileToAgent', () => {
    it('maps backend health (snake_case) to AgentHealth (camelCase)', () => {
      const profile = {
        id: '36',
        name: 'Lois Lane',
        description: '',
        provider: 'deepseek',
        model: 'deepseek-v4-flash',
        system_prompt: '',
        parameters: { temperature: 0.7, max_tokens: 2000, top_p: 0.9 },
        tools: [],
        memory: false,
        health: {
          status: 'warn' as const,
          consecutive_failures: 0,
          last_error: 'Model not found',
          last_failure_at: '2026-08-03T14:54:27',
          failures_7d: 1
        }
      }

      const agent = (profileService as unknown as {
        convertProfileToAgent(p: typeof profile): {
          health?: { status: string; consecutiveFailures: number; lastError?: string | null; failures7d: number }
        }
      }).convertProfileToAgent(profile)

      expect(agent.health).toBeDefined()
      expect(agent.health?.status).toBe('warn')
      expect(agent.health?.consecutiveFailures).toBe(0)
      expect(agent.health?.lastError).toBe('Model not found')
      expect(agent.health?.failures7d).toBe(1)
    })

    it('maps fallback config (F4) with safe defaults', () => {
      const profile = {
        id: '1',
        name: 'Test',
        description: '',
        provider: 'deepseek',
        model: 'deepseek-v4-flash',
        system_prompt: '',
        parameters: { temperature: 0.7, max_tokens: 2000, top_p: 0.9 },
        tools: [],
        memory: false,
        fallback_enabled: true,
        preferred_providers: ['ollama', 'openrouter']
      }

      const agent = (profileService as unknown as {
        convertProfileToAgent(p: typeof profile): {
          fallbackEnabled?: boolean
          preferredProviders?: string[]
        }
      }).convertProfileToAgent(profile)

      expect(agent.fallbackEnabled).toBe(true)
      expect(agent.preferredProviders).toEqual(['ollama', 'openrouter'])
    })

    it('defaults fallback off when backend omits it (F4 opt-in)', () => {
      const profile = {
        id: '1',
        name: 'Test',
        description: '',
        provider: 'deepseek',
        model: 'deepseek-v4-flash',
        system_prompt: '',
        parameters: { temperature: 0.7, max_tokens: 2000, top_p: 0.9 },
        tools: [],
        memory: false
      }

      const agent = (profileService as unknown as {
        convertProfileToAgent(p: typeof profile): {
          fallbackEnabled?: boolean
          preferredProviders?: string[]
        }
      }).convertProfileToAgent(profile)

      expect(agent.fallbackEnabled).toBe(false)
      expect(agent.preferredProviders).toEqual([])
    })

    it('leaves health undefined when backend omits it', () => {
      const profile = {
        id: '1',
        name: 'Test',
        description: '',
        provider: 'deepseek',
        model: 'deepseek-v4-flash',
        system_prompt: '',
        parameters: { temperature: 0.7, max_tokens: 2000, top_p: 0.9 },
        tools: [],
        memory: false
      }

      const agent = (profileService as unknown as {
        convertProfileToAgent(p: typeof profile): { health?: unknown }
      }).convertProfileToAgent(profile)

      expect(agent.health).toBeUndefined()
    })
  })
})
