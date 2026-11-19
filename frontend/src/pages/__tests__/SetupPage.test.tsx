import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@/test/test-utils'

vi.mock('@/services/apiClient', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

import { apiClient } from '@/services/apiClient'
import SetupPage from '../SetupPage'

describe('SetupPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(apiClient.get).mockResolvedValue({
      data: {
        providers: [
          { provider_id: 1, provider_name: 'ollama', key_source: 'none', has_key: false },
          { provider_id: 2, provider_name: 'openrouter', key_source: 'env', has_key: true },
        ],
      },
    } as never)
    vi.mocked(apiClient.post).mockResolvedValue({
      data: { status: 'connected' },
    } as never)
  })

  it('renders the checklist with statuses', async () => {
    render(<SetupPage />)
    await waitFor(() => {
      expect(screen.getByText('Local LLM running')).toBeInTheDocument()
    })
    expect(screen.getByText('API keys')).toBeInTheDocument()
    expect(screen.getByText('Default model')).toBeInTheDocument()
    expect(screen.getByText('Starter agent')).toBeInTheDocument()
    expect(screen.getByText(/providers have keys/)).toBeInTheDocument()
  })

  it('shows all five tabs', async () => {
    render(<SetupPage />)
    await waitFor(() => {
      expect(screen.getByText('Overview')).toBeInTheDocument()
    })
    expect(screen.getByText('Local LLM')).toBeInTheDocument()
    expect(screen.getByText('API Keys')).toBeInTheDocument()
    expect(screen.getByText('Default Model')).toBeInTheDocument()
    expect(screen.getByText('Agent')).toBeInTheDocument()
  })

  it('switches to the Local LLM tab and shows Ollama status', async () => {
    render(<SetupPage />)
    await waitFor(() => {
      expect(screen.getByText('Overview')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText('Local LLM'))
    await waitFor(() => {
      expect(screen.getAllByText(/ollama serve/).length).toBeGreaterThan(0)
    })
    expect(screen.getByText('✅ Running')).toBeInTheDocument()
  })

  it('reuses the Keys manager on the API Keys tab', async () => {
    render(<SetupPage />)
    await waitFor(() => {
      expect(screen.getByText('Overview')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText('API Keys'))
    await waitFor(() => {
      expect(screen.getByText('Provider API Keys')).toBeInTheDocument()
    })
  })

  it('clicking a checklist item jumps to its tab', async () => {
    render(<SetupPage />)
    await waitFor(() => {
      expect(screen.getByText('Local LLM running')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText('Local LLM running'))
    await waitFor(() => {
      expect(screen.getAllByText(/ollama serve/).length).toBeGreaterThan(0)
    })
  })
})
