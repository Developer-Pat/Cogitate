import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@/test/test-utils'

vi.mock('@/services/apiClient', () => {
  const client = { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() }
  return { apiClient: client, default: client }
})

import { apiClient } from '@/services/apiClient'
import { DefaultProviderConfig } from '../DefaultProviderConfig'

// MEASURED ON A FROM-ZERO INSTALL (2026-11-21): this component is also how a fresh install CHOOSES
// its default — there is no `currentProviderId` then — and it used to seed itself with provider `1`
// and the model `llama3.2:latest`. Neither is a guess a component is entitled to make about a
// machine nobody has looked at: the install's own first provider is.
describe('DefaultProviderConfig — an install with no default yet', () => {
  const onProviderChange = vi.fn()
  const onModelChange = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(apiClient.get).mockImplementation(async (url: string) => {
      if (url === '/api/v1/providers/managed') {
        return {
          data: {
            providers: [
              { id: 7, name: 'deepseek', provider_type: 'deepseek', is_active: true, is_default: false },
              { id: 8, name: 'groq', provider_type: 'groq', is_active: true, is_default: false },
            ],
          },
        } as never
      }
      if (url === '/api/v1/providers/managed/7/models') {
        return {
          data: { models: [{ name: 'deepseek-flash', display_name: 'Deepseek Flash' }] },
        } as never
      }
      return { data: { models: [] } } as never
    })
  })

  it('takes the install\'s first provider instead of a hardcoded id', async () => {
    render(<DefaultProviderConfig onProviderChange={onProviderChange} onModelChange={onModelChange} />)

    await waitFor(() => {
      expect(onProviderChange).toHaveBeenCalledWith(7, 'deepseek', 'deepseek')
    })
    // the provider select shows what was chosen, and the model list came from THAT provider
    // (a model is never auto-picked: the search box + list are the choice, so the option must be
    // there and the selection must still be empty)
    expect(await screen.findByRole('option', { name: 'Deepseek Flash' })).toBeInTheDocument()
    expect(screen.getByDisplayValue('Select a model...')).toBeInTheDocument()
    expect(apiClient.get).toHaveBeenCalledWith('/api/v1/providers/managed/7/models')
  })

  it('invents no model: the model list is empty until a provider answers', async () => {
    vi.mocked(apiClient.get).mockImplementation(async (url: string) => {
      if (url === '/api/v1/providers/managed') {
        return {
          data: {
            providers: [{ id: 9, name: 'llama', provider_type: 'llama', is_active: true, is_default: false }],
          },
        } as never
      }
      return { data: { models: [] } } as never
    })

    render(<DefaultProviderConfig onProviderChange={onProviderChange} onModelChange={onModelChange} />)

    await waitFor(() => expect(onProviderChange).toHaveBeenCalledWith(9, 'llama', 'llama'))
    // "No models available" is the honest state — never a `llama3.2:latest` nobody chose.
    expect(await screen.findByText('No models available')).toBeInTheDocument()
  })
})
