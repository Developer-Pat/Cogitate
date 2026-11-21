/** The Setup page renders the READINESS verdict — it does not compute one (2026-11-20).
 *
 * It used to draw its own checklist from three browser calls (a POST to provider id 1 to
 * guess whether Ollama was up, `agentReady: true`), which made it report FACTS where it
 * should have reported DEFECTS: "0 of 0 providers have keys", and a stranger told to pick
 * a profile while none could exist. The facts are measured once in the backend now, and
 * this page is one of the two surfaces that render them.
 *
 * These tests hold that line: every text here comes from the readiness payload, an item
 * navigates to where it is FIXED, and a failed check says it cannot say — it does not
 * fall back to a guess.
 */

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

const REPORT = {
  ready: false,
  remaining: 2,
  items: [
    {
      key: 'provider', label: 'Provider + key', state: 'unmet',
      detail: 'No provider yet. Add one on the Provider Dashboard.',
      href: '/provider-dashboard', counted: true,
    },
    {
      key: 'chat', label: 'Chat model', state: 'unmet',
      detail: 'Nothing answers chat yet. Set a default provider and model.',
      href: '/provider-dashboard', counted: true,
    },
    {
      key: 'agents', label: 'Agents', state: 'blocked',
      detail: 'Bob and Lois arrive once a chat model resolves.',
      href: '/agent-profiles', counted: true,
    },
    {
      key: 'runtime', label: 'Exa runtime (optional)', state: 'optional',
      detail: 'Exa needs an external runtime.',
      href: '/exa', counted: false,
    },
  ],
}

const READY = {
  ready: true,
  remaining: 0,
  items: [{ ...REPORT.items[0], state: 'ok', detail: '1 of 1 provider(s) can be dialled.' }],
}

describe('SetupPage renders the readiness verdict', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(apiClient.get).mockImplementation(async (url: string) => {
      if (url.includes('/setup/readiness')) return { data: REPORT } as never
      if (url.includes('/managed/keys')) return { data: { providers: [] } } as never
      return { data: {} } as never
    })
    vi.mocked(apiClient.post).mockResolvedValue({ data: {} } as never)
  })

  it('draws the checklist from the payload, and the verdict as the number', async () => {
    render(<SetupPage />)

    await waitFor(() => expect(screen.getByText('Provider + key')).toBeInTheDocument())
    expect(screen.getByText('Chat model')).toBeInTheDocument()
    expect(screen.getByText('Agents')).toBeInTheDocument()
    expect(screen.getByText('Exa runtime (optional)')).toBeInTheDocument()
    expect(screen.getByText('2 things left before an agent can answer.')).toBeInTheDocument()
    // the detail is the backend's sentence, verbatim
    expect(screen.getByText('No provider yet. Add one on the Provider Dashboard.')).toBeInTheDocument()
  })

  it('marks the optional runtime as not counted, and never as a failure', async () => {
    render(<SetupPage />)

    await waitFor(() => expect(screen.getByText('Exa runtime (optional)')).toBeInTheDocument())
    expect(screen.getByText('optional')).toBeInTheDocument()
  })

  it('an item navigates to where it is FIXED (no tab-jumping)', async () => {
    render(<SetupPage />)

    const item = await screen.findByText('Provider + key')
    const link = item.closest('a')
    expect(link?.getAttribute('href')).toBe('/provider-dashboard')

    const blocked = screen.getByText('Agents').closest('a')
    expect(blocked?.getAttribute('href')).toBe('/agent-profiles')
  })

  it('a ready install says so instead of listing work', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: READY } as never)
    render(<SetupPage />)

    await waitFor(() =>
      expect(
        screen.getByText('Everything this app needs is configured — you can go to Chat.')
      ).toBeInTheDocument()
    )
  })

  it('a failed check says it cannot say — never a guessed verdict', async () => {
    vi.mocked(apiClient.get).mockRejectedValue(new Error('offline'))
    render(<SetupPage />)

    await waitFor(() =>
      expect(
        screen.getByText('The setup check did not answer — this page cannot say what is configured.')
      ).toBeInTheDocument()
    )
    expect(screen.getByText(/Nothing here is a verdict about your install/)).toBeInTheDocument()
    expect(screen.queryByText(/things left before an agent can answer/)).toBeNull()
  })

  it('shows all five tabs, and the Local LLM tab is instructions, not a status probe', async () => {
    render(<SetupPage />)
    await waitFor(() => expect(screen.getByText('Overview')).toBeInTheDocument())
    for (const label of ['Local LLM', 'API Keys', 'Default Model', 'Agent']) {
      expect(screen.getByText(label)).toBeInTheDocument()
    }

    fireEvent.click(screen.getByText('Local LLM'))
    await waitFor(() =>
      expect(screen.getAllByText(/ollama serve/).length).toBeGreaterThan(0)
    )
    // the old page reported a live "✅ Running"; the page states the commands now
    expect(screen.queryByText('✅ Running')).toBeNull()
  })

  it('reuses the Keys manager on the API Keys tab', async () => {
    render(<SetupPage />)
    await waitFor(() => expect(screen.getByText('Overview')).toBeInTheDocument())

    fireEvent.click(screen.getByText('API Keys'))
    await waitFor(() => expect(screen.getByText('Provider API Keys')).toBeInTheDocument())
  })
})
