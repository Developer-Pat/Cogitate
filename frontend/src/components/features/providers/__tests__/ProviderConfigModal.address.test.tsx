import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@/test/test-utils'

// The address prefill reads the registry at GET /api/v1/providers — the ONE home for a
// type's address. A type with no row there (llama.cpp: a server the user runs) gets no
// prefill, so the form must ask for the address instead of promising one.
const CATALOG = {
  providers: [
    { id: 'ollama', base_url: 'http://localhost:11434' },
    { id: 'deepseek', base_url: 'https://api.deepseek.com' },
  ],
}

vi.mock('@/services/apiClient', () => {
  // The form imports the DEFAULT client (ProviderKeyManager uses the named one).
  const client = { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() }
  return { apiClient: client, default: client }
})

import { apiClient } from '@/services/apiClient'
import ProviderConfigModal from '../ProviderConfigModal'

describe('ProviderConfigModal — the address a type does not have', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(apiClient.get).mockResolvedValue({ data: CATALOG } as never)
  })

  const renderAdd = () =>
    render(
      <ProviderConfigModal provider={null} mode="add" onSave={vi.fn()} onCancel={vi.fn()} />
    )

  it('asks for the address on llama.cpp, which has no registry row', async () => {
    renderAdd()
    await waitFor(() => expect(apiClient.get).toHaveBeenCalledWith('/api/v1/providers'))

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'llama' } })

    await waitFor(() => {
      expect(
        screen.getByText("No address on file for this type — enter the server's address.")
      ).toBeInTheDocument()
    })
    // ...and the promise it used to make is gone for this type.
    expect(screen.queryByText(/The name and address fill in from the type/)).not.toBeInTheDocument()
  })

  it('clears the previous type\'s prefilled address when the new type has none', async () => {
    // Measured live 2026-11-21: switching ollama → llama.cpp left `http://localhost:11434` in
    // the field while the note asked for the server's address — a llama row pointing at
    // ollama's port, which no check would ever report.
    renderAdd()
    await waitFor(() => expect(apiClient.get).toHaveBeenCalledWith('/api/v1/providers'))

    const select = screen.getByRole('combobox')
    await waitFor(() => expect(screen.getByDisplayValue('http://localhost:11434')).toBeInTheDocument())

    fireEvent.change(select, { target: { value: 'llama' } })

    await waitFor(() => {
      expect(screen.getByPlaceholderText('e.g., https://api.openai.com/v1')).toHaveValue('')
    })
    expect(screen.getByPlaceholderText('e.g., openai, ollama')).toHaveValue('')
  })

  it('keeps a hand-typed address when the type changes', async () => {
    renderAdd()
    await waitFor(() => expect(apiClient.get).toHaveBeenCalledWith('/api/v1/providers'))
    const url = screen.getByPlaceholderText('e.g., https://api.openai.com/v1')
    fireEvent.change(url, { target: { value: 'http://10.0.0.5:8080' } })

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'llama' } })

    await waitFor(() => expect(url).toHaveValue('http://10.0.0.5:8080'))
  })
})
