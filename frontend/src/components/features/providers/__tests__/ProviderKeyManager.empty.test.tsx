import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@/test/test-utils'

vi.mock('@/services/apiClient', () => {
  // ProviderKeyManager imports the NAMED client; the add form (ProviderConfigModal) imports
  // the DEFAULT one. Both must be the same mocked object or the form's catalog read throws.
  const client = { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() }
  return { apiClient: client, default: client }
})

import { apiClient } from '@/services/apiClient'
import ProviderKeyManager from '../ProviderKeyManager'

// THE FIRST PROVIDER (2026-11-21): a fresh install has no provider rows at all, and this
// tab lists keys ON rows — so it rendered an empty table and there was no way to get the
// first row from the place the readiness item sends you to.
describe('ProviderKeyManager — no providers yet', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(apiClient.get).mockResolvedValue({ data: { providers: [] } } as never)
  })

  it('offers to create the first provider instead of an empty table', async () => {
    render(<ProviderKeyManager />)
    await waitFor(() => {
      expect(screen.getByText(/No provider on this install yet/)).toBeInTheDocument()
    })
    expect(screen.getByText('Add your first provider')).toBeInTheDocument()
    // The empty table's headers must not be the only thing on screen.
    expect(screen.queryByText('Key Source')).not.toBeInTheDocument()
  })

  it('creates the provider with its key in one form and reloads the rows', async () => {
    vi.mocked(apiClient.get)
      .mockResolvedValueOnce({ data: { providers: [] } } as never) // the keys list
      .mockResolvedValueOnce({ data: { providers: [] } } as never) // the address catalog
      .mockResolvedValueOnce({
        data: {
          providers: [
            { provider_id: 9, provider_name: 'deepseek', provider_type: 'deepseek', key_source: 'db', has_key: true },
          ],
        },
      } as never) // the reload
    vi.mocked(apiClient.post).mockResolvedValue({ data: { id: 9 } } as never)

    render(<ProviderKeyManager />)
    await waitFor(() => expect(screen.getByText('Add your first provider')).toBeInTheDocument())
    fireEvent.click(screen.getByText('Add your first provider'))

    await waitFor(() => expect(screen.getByRole('button', { name: 'Add Provider' })).toBeInTheDocument())
    fireEvent.change(screen.getByPlaceholderText('e.g., openai, ollama'), {
      target: { value: 'deepseek' },
    })
    fireEvent.change(screen.getByPlaceholderText('sk-...'), {
      target: { value: 'sk-live-key' },
    })
    const submit = screen.getByRole('button', { name: 'Add Provider' })
    await waitFor(() => expect(submit).toBeEnabled())
    fireEvent.click(submit)

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith(
        '/api/v1/providers/config',
        expect.objectContaining({ name: 'deepseek', api_key: 'sk-live-key' })
      )
    })
    await waitFor(() => expect(screen.getByText('Stored (DB)')).toBeInTheDocument())
  })

  it('does not invite the first provider on a page whose filter simply matched nothing', async () => {
    // The local page filters the cloud rows out — an install WITH providers must not be told
    // it has none, and its own Add Provider button is the page's business.
    vi.mocked(apiClient.get).mockResolvedValue({
      data: {
        providers: [
          { provider_id: 2, provider_name: 'deepseek', provider_type: 'deepseek', key_source: 'env', has_key: true },
        ],
      },
    } as never)
    render(<ProviderKeyManager location="local" />)
    await waitFor(() => expect(apiClient.get).toHaveBeenCalled())
    await waitFor(() => {
      expect(screen.queryByText('Add your first provider')).not.toBeInTheDocument()
    })
  })
})
