import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@/test/test-utils'

// Mock the apiClient
vi.mock('@/services/apiClient', () => ({
  apiClient: {
    get: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

import { apiClient } from '@/services/apiClient'
import ProviderKeyManager from '../ProviderKeyManager'

const mockRows = {
  providers: [
    { provider_id: 1, provider_name: 'ollama', provider_type: 'ollama', key_source: 'none', has_key: false },
    { provider_id: 2, provider_name: 'openrouter', provider_type: 'openrouter', key_source: 'env', has_key: true },
    { provider_id: 3, provider_name: 'deepseek', provider_type: 'deepseek', key_source: 'db', has_key: true },
  ],
}

describe('ProviderKeyManager', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockRows } as never)
  })

  it('renders providers with key-source badges', async () => {
    render(<ProviderKeyManager />)
    await waitFor(() => {
      expect(screen.getAllByText('openrouter').length).toBeGreaterThan(0)
    })
    expect(screen.getByText('Env (.env)')).toBeInTheDocument()
    expect(screen.getByText('Stored (DB)')).toBeInTheDocument()
    expect(screen.getByText('None')).toBeInTheDocument()
  })

  it('opens the set-key modal and stores a key', async () => {
    vi.mocked(apiClient.put).mockResolvedValue({ data: {} } as never)
    render(<ProviderKeyManager />)
    await waitFor(() => {
      expect(screen.getAllByText('openrouter').length).toBeGreaterThan(0)
    })

    fireEvent.click(screen.getByText('Set Key'))
    expect(screen.getByText(/Set API Key — openrouter/)).toBeInTheDocument()

    fireEvent.change(screen.getByPlaceholderText('sk-... or Bearer key'), {
      target: { value: 'new-secret-key' },
    })
    fireEvent.click(screen.getByText('Store Key'))

    await waitFor(() => {
      expect(apiClient.put).toHaveBeenCalledWith(
        '/api/v1/providers/managed/2/key',
        { api_key: 'new-secret-key' }
      )
    })
  })

  it('clears a stored key with confirmation', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    vi.mocked(apiClient.delete).mockResolvedValue({ data: {} } as never)
    render(<ProviderKeyManager />)
    await waitFor(() => {
      expect(screen.getAllByText('deepseek').length).toBeGreaterThan(0)
    })

    fireEvent.click(screen.getByText('Clear'))
    await waitFor(() => {
      expect(apiClient.delete).toHaveBeenCalledWith('/api/v1/providers/managed/3/key')
    })
  })
})
