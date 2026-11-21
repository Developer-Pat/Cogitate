import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@/test/test-utils'

// Mock the curated models service
vi.mock('@/services/domains/providers/curatedModelsService', () => ({
  fetchCuratedModels: vi.fn(),
  addCuratedModel: vi.fn(),
  updateCuratedModel: vi.fn(),
  removeCuratedModel: vi.fn(),
  verifyCuratedModelWindow: vi.fn(),
}))

// Toasts are how this component confirms a mutation (house rule: the toaster, never an inline
// alert), so the store is mocked to assert them — mounting the notification container just to
// read one line would test the container instead.
const notifier = vi.hoisted(() => ({ addSuccess: vi.fn(), addError: vi.fn() }))
vi.mock('@/stores/notificationStore', () => ({
  useNotificationStore: { getState: () => notifier },
}))

import {
  fetchCuratedModels,
  addCuratedModel,
  updateCuratedModel,
  removeCuratedModel,
  verifyCuratedModelWindow,
} from '@/services/domains/providers/curatedModelsService'
import CuratedModelsManager from '../CuratedModelsManager'

/**
 * The table's rendered order, read off each row's OWN identity — the `data-model-id` it carries.
 * NEVER a cell index: this phase moved the id from the first cell to the third when the columns
 * were reordered, and an index-based reader would have followed it silently to the provider.
 */
function rowIds(): (string | null)[] {
  return screen
    .getAllByRole('row')
    .slice(1)
    .map(r => r.getAttribute('data-model-id'))
}

const mockModels = [
  {
    id: 'nvidia/nemotron-3-super-120b-a12b:free',
    name: 'NVIDIA: Nemotron 3 Super',
    provider: 'openrouter',
    category: 'chat',
    isFree: true,
    verified: true,
    thinking: 'mandatory',
    location: 'cloud',
    curatedRowId: 1,
  },
  {
    id: 'deepseek-v4-flash',
    name: 'DeepSeek V4 Flash',
    provider: 'deepseek',
    category: 'code',
    isFree: false,
    verified: false,
    thinking: 'high',
    location: 'local',
    curatedRowId: 2,
  },
]

/** The verify endpoint's flat response, for a row whose number the provider overruled. */
const mockVerification = {
  curated_id: 1,
  provider: 'openrouter',
  model_id: 'nvidia/nemotron-3-super-120b-a12b:free',
  curated: 8192,
  discovered: 262144,
  window: 262144,
  verified: true,
  mismatch: true,
  stale: false,
  age_hours: 3.5,
  refreshed: false,
  thinking_curated: 'none',
  thinking_provider: 'reasoning: {mandatory: true}',
  max_completion: 32768,
  note: "adopted the provider's 262144 over this row's 8192",
  thinking_adopted: 'mandatory',
}

const mockProviders = [
  { id: 1, name: 'openrouter', display_name: 'OpenRouter', provider_type: 'openrouter' },
  { id: 2, name: 'deepseek', display_name: 'DeepSeek', provider_type: 'deepseek' },
] as never

describe('CuratedModelsManager', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(fetchCuratedModels).mockResolvedValue(mockModels as never)
  })

  it('renders curated models in a table', async () => {
    render(<CuratedModelsManager providers={mockProviders} loading={false} />)

    await waitFor(() => {
      expect(screen.getByText('NVIDIA: Nemotron 3 Super')).toBeInTheDocument()
      expect(screen.getByText('DeepSeek V4 Flash')).toBeInTheDocument()
    })
    expect(fetchCuratedModels).toHaveBeenCalled()
  })

  it('narrows to one provider through the select, whose options carry the counts', async () => {
    render(<CuratedModelsManager providers={mockProviders} loading={false} />)
    await waitFor(() => {
      expect(screen.getByText('DeepSeek V4 Flash')).toBeInTheDocument()
    })

    // The counts the pill row carried survive as option labels, and `All` is the default.
    const providerSelect = screen.getByLabelText('Filter by provider') as HTMLSelectElement
    expect([...providerSelect.options].map(o => o.textContent)).toEqual([
      'All (2)', 'deepseek (1)', 'openrouter (1)',
    ])
    expect(providerSelect.value).toBe('all')

    fireEvent.change(providerSelect, { target: { value: 'deepseek' } })
    expect(screen.getByText('DeepSeek V4 Flash')).toBeInTheDocument()
    expect(screen.queryByText('NVIDIA: Nemotron 3 Super')).not.toBeInTheDocument()
  })

  it('opens the add modal and creates a model', async () => {
    vi.mocked(addCuratedModel).mockResolvedValue(mockModels[0] as never)

    render(<CuratedModelsManager providers={mockProviders} loading={false} />)
    await waitFor(() => {
      expect(screen.getByText('NVIDIA: Nemotron 3 Super')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('+ Add Model'))
    expect(screen.getByText('Add Curated Model')).toBeInTheDocument()

    fireEvent.change(screen.getByPlaceholderText('e.g. nvidia/nemotron-3-super-120b-a12b:free'), {
      target: { value: 'ollama/llama3.3' },
    })
    fireEvent.change(screen.getByPlaceholderText('e.g. NVIDIA: Nemotron 3 Super'), {
      target: { value: 'Llama 3.3' },
    })
    fireEvent.click(screen.getByText('Add Model'))

    await waitFor(() => {
      expect(addCuratedModel).toHaveBeenCalledWith(
        expect.objectContaining({ id: 'ollama/llama3.3', name: 'Llama 3.3' })
      )
    })
  })

  it('leaves the descriptor unset on create, and can CLEAR it on edit', async () => {
    vi.mocked(addCuratedModel).mockResolvedValue(mockModels[0] as never)
    vi.mocked(updateCuratedModel).mockResolvedValue(mockModels[0] as never)

    render(<CuratedModelsManager providers={mockProviders} loading={false} />)
    await waitFor(() => {
      expect(screen.getByText('NVIDIA: Nemotron 3 Super')).toBeInTheDocument()
    })

    // CREATE: the category select opens on "not described" — a form that PRE-SELECTED a value
    // was the defect this replaced, so nothing is sent and the row stores nothing.
    fireEvent.click(screen.getByText('+ Add Model'))
    expect((screen.getByLabelText('Category') as HTMLSelectElement).value).toBe('')
    fireEvent.change(screen.getByPlaceholderText('e.g. nvidia/nemotron-3-super-120b-a12b:free'), {
      target: { value: 'ollama/llama3.3' },
    })
    fireEvent.change(screen.getByPlaceholderText('e.g. NVIDIA: Nemotron 3 Super'), {
      target: { value: 'Llama 3.3' },
    })
    fireEvent.click(screen.getByText('Add Model'))
    await waitFor(() => {
      const sent = vi.mocked(addCuratedModel).mock.calls[0][0] as Record<string, unknown>
      expect(sent.category).toBeUndefined()
    })

    // EDIT: the same empty selection is a real choice — an explicit null clears the descriptor,
    // because a field whose empty state cannot be reached is a field you can only ever fill in.
    const nvidiaRow = screen.getByText('NVIDIA: Nemotron 3 Super').closest('tr') as HTMLElement
    fireEvent.click(within(nvidiaRow).getByLabelText('Edit curated entry'))
    expect((screen.getByLabelText('Category') as HTMLSelectElement).value).toBe('chat')
    fireEvent.change(screen.getByLabelText('Category'), { target: { value: '' } })
    fireEvent.click(screen.getByText('Save Changes'))
    await waitFor(() => {
      expect(updateCuratedModel).toHaveBeenCalledWith(
        1, expect.objectContaining({ category: null }),
      )
    })
  })

  it('shows each row\'s declared label, and emphasises a mandatory driver', async () => {
    render(<CuratedModelsManager providers={mockProviders} loading={false} />)

    await waitFor(() => {
      expect(screen.getByText('NVIDIA: Nemotron 3 Super')).toBeInTheDocument()
    })

    // The stored value is what the table reads — not a form default.
    expect(screen.getByText('mandatory')).toBeInTheDocument()
    expect(screen.getByText('high')).toBeInTheDocument()
    expect(
      screen.getByText('mandatory').className,
    ).toContain('badge-warning')

    // The row's LOCATION is not a table column any more (every row here is `cloud`, and the
    // cell carried one value on every row) — the fact lives in the edit form the second half
    // of this file already exercises. Asserted here so a silent re-addition is caught.
    expect(screen.queryByText('local')).toBeNull()
    expect(screen.queryByText('cloud')).toBeNull()
  })

  it('loads a row\'s dimensions into the edit form and saves the change', async () => {
    vi.mocked(updateCuratedModel).mockResolvedValue(mockModels[1] as never)

    render(<CuratedModelsManager providers={mockProviders} loading={false} />)
    await waitFor(() => {
      expect(screen.getByText('DeepSeek V4 Flash')).toBeInTheDocument()
    })

    // The DEEPSEEK row, found by its own name. The default order is provider-then-id
    // (this arc's Phase 1), so a DOM INDEX here would quietly edit the other row.
    const deepseekRow = screen.getByText('DeepSeek V4 Flash').closest('tr') as HTMLElement
    fireEvent.click(within(deepseekRow).getByLabelText('Edit curated entry'))
    const editing = screen.getByLabelText('Thinking') as HTMLSelectElement
    expect(editing.value).toBe('high')
    // `auto` is a CREATE-time instruction — a stored row always carries a real level, so
    // offering "take the provider's claim" here would be a hidden no-op.
    expect([...editing.options].map(o => o.value)).toEqual([
      'none', 'low', 'medium', 'high', 'mandatory',
    ])
    expect((screen.getByLabelText('Location') as HTMLSelectElement).value).toBe('local')

    fireEvent.change(screen.getByLabelText('Thinking'), { target: { value: 'mandatory' } })
    fireEvent.click(screen.getByText('Save Changes'))

    await waitFor(() => {
      expect(updateCuratedModel).toHaveBeenCalledWith(
        2,
        expect.objectContaining({ thinking: 'mandatory', location: 'local' }),
      )
    })
  })

  it('offers the whole vocabulary on the create form and sends what was chosen', async () => {
    vi.mocked(addCuratedModel).mockResolvedValue(mockModels[0] as never)

    render(<CuratedModelsManager providers={mockProviders} loading={false} />)
    await waitFor(() => {
      expect(screen.getByText('NVIDIA: Nemotron 3 Super')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('+ Add Model'))

    const thinking = screen.getByLabelText('Thinking') as HTMLSelectElement
    expect([...thinking.options].map(o => o.value)).toEqual([
      'auto', 'none', 'low', 'medium', 'high', 'mandatory',
    ])
    expect([...(screen.getByLabelText('Location') as HTMLSelectElement).options].map(o => o.value)).toEqual([
      'local', 'cloud',
    ])
    // A fresh row starts on `auto`: nobody has chosen a level, so the API derives it from
    // the provider's own claim rather than this form inventing 'none'.
    expect(thinking.value).toBe('auto')

    fireEvent.change(screen.getByPlaceholderText('e.g. nvidia/nemotron-3-super-120b-a12b:free'), {
      target: { value: 'ollama/llama3.3' },
    })
    fireEvent.change(screen.getByPlaceholderText('e.g. NVIDIA: Nemotron 3 Super'), {
      target: { value: 'Llama 3.3' },
    })
    fireEvent.change(thinking, { target: { value: 'mandatory' } })
    fireEvent.change(screen.getByLabelText('Location'), { target: { value: 'local' } })
    fireEvent.click(screen.getByText('Add Model'))

    await waitFor(() => {
      expect(addCuratedModel).toHaveBeenCalledWith(
        expect.objectContaining({
          id: 'ollama/llama3.3',
          thinking: 'mandatory',
          location: 'local',
        }),
      )
    })
  })

  it('leaves thinking to the provider when the form sits on auto', async () => {
    vi.mocked(addCuratedModel).mockResolvedValue(mockModels[0] as never)

    render(<CuratedModelsManager providers={mockProviders} loading={false} />)
    await waitFor(() => {
      expect(screen.getByText('NVIDIA: Nemotron 3 Super')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('+ Add Model'))
    fireEvent.change(screen.getByPlaceholderText('e.g. nvidia/nemotron-3-super-120b-a12b:free'), {
      target: { value: 'ollama/llama3.3' },
    })
    fireEvent.change(screen.getByPlaceholderText('e.g. NVIDIA: Nemotron 3 Super'), {
      target: { value: 'Llama 3.3' },
    })
    fireEvent.click(screen.getByText('Add Model'))

    await waitFor(() => expect(addCuratedModel).toHaveBeenCalled())
    const payload = vi.mocked(addCuratedModel).mock.calls[0][0] as unknown as Record<string, unknown>
    // The COMPONENT's contribution is `undefined`; omitting the key from the request body
    // is the service's job (pinned in curatedModelsService.test.ts). Asserting each at its
    // own layer is what keeps the two from disagreeing silently.
    expect(payload.thinking).toBeUndefined()
    expect(payload.location).toBe('cloud')
  })

  it('removes a model with confirmation', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    vi.mocked(removeCuratedModel).mockResolvedValue(undefined)

    render(<CuratedModelsManager providers={mockProviders} loading={false} />)
    await waitFor(() => {
      expect(screen.getByText('NVIDIA: Nemotron 3 Super')).toBeInTheDocument()
    })

    // The NVIDIA row, by name — never by DOM index (see the edit test above).
    const nvidiaRow = screen.getByText('NVIDIA: Nemotron 3 Super').closest('tr') as HTMLElement
    fireEvent.click(within(nvidiaRow).getByLabelText('Remove curated entry'))

    await waitFor(() => {
      expect(removeCuratedModel).toHaveBeenCalledWith(1)
    })
  })

  it('shows each row\'s provider in its own column', async () => {
    render(<CuratedModelsManager providers={mockProviders} loading={false} />)
    await waitFor(() => {
      expect(screen.getByText('NVIDIA: Nemotron 3 Super')).toBeInTheDocument()
    })

    // The API already served this and the DTO already mapped it; the table simply never
    // rendered it. Each row says where it runs.
    const nvidiaRow = screen.getByText('NVIDIA: Nemotron 3 Super').closest('tr') as HTMLElement
    expect(within(nvidiaRow).getByText('openrouter')).toBeInTheDocument()
    const deepseekRow = screen.getByText('DeepSeek V4 Flash').closest('tr') as HTMLElement
    expect(within(deepseekRow).getByText('deepseek')).toBeInTheDocument()
  })

  it('orders by provider, then by name and model id, and a second press flips it', async () => {
    render(<CuratedModelsManager providers={mockProviders} loading={false} />)
    await waitFor(() => {
      expect(screen.getByText('NVIDIA: Nemotron 3 Super')).toBeInTheDocument()
    })

    // Default: provider ascending, the tie-break following the columns — name, then model id.
    // (These two rows differ on the provider, so the tie-break does not fire here; the sort of
    // a shared key is pinned by the thinking test below and by the api suite's matcher test.)
    expect(rowIds()).toEqual(['deepseek-v4-flash', 'nvidia/nemotron-3-super-120b-a12b:free'])

    const providerHeader = screen.getByLabelText('Sort by Provider').closest('th') as HTMLElement
    expect(providerHeader).toHaveAttribute('aria-sort', 'ascending')

    fireEvent.click(screen.getByLabelText('Sort by Provider'))
    expect(rowIds()).toEqual(['nvidia/nemotron-3-super-120b-a12b:free', 'deepseek-v4-flash'])
    expect(providerHeader).toHaveAttribute('aria-sort', 'descending')
  })

  it('sorts thinking by the vocabulary\'s own order, not the alphabet', async () => {
    // 'mandatory' sorts BEFORE 'none' alphabetically and AFTER it in the vocabulary —
    // the two orders disagree here on purpose.
    vi.mocked(fetchCuratedModels).mockResolvedValue([
      { ...mockModels[0], thinking: 'mandatory', curatedRowId: 11 },
      { ...mockModels[1], thinking: 'none', curatedRowId: 12 },
    ] as never)

    render(<CuratedModelsManager providers={mockProviders} loading={false} />)
    await waitFor(() => {
      expect(screen.getByText('DeepSeek V4 Flash')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByLabelText('Sort by Thinking'))
    expect(rowIds()).toEqual(['deepseek-v4-flash', 'nvidia/nemotron-3-super-120b-a12b:free'])
  })

  it('carries the cost fact in its own column, and Free, Sort, Featured, Location, Verify and Category are gone', async () => {
    render(<CuratedModelsManager providers={mockProviders} loading={false} />)
    await waitFor(() => {
      expect(screen.getByText('NVIDIA: Nemotron 3 Super')).toBeInTheDocument()
    })

    expect(screen.queryByRole('columnheader', { name: 'Free' })).toBeNull()
    expect(screen.queryByRole('columnheader', { name: 'Sort' })).toBeNull()
    // THE ARC'S PHASE 3: the app stopped featuring models, so the column that gathered the
    // picks together goes with the flag itself.
    expect(screen.queryByRole('columnheader', { name: 'Featured' })).toBeNull()
    // AND THE COLUMNS THAT READ ONE VALUE ON EVERY ROW GO WITH IT: the table lists rows from
    // every provider — all of them `cloud` here, and all of them already verified — so the
    // Location and Verify columns carried no information. The Verify ACTION stays, in Actions.
    expect(screen.queryByRole('columnheader', { name: 'Location' })).toBeNull()
    expect(screen.queryByRole('columnheader', { name: 'Verify' })).toBeNull()
    // THE CATEGORY IS OFF THE TABLE by the user's call: it is a descriptor of what a row is
    // FOR, not a scan column, and it stays a field the add/edit modal owns.
    expect(screen.queryByRole('columnheader', { name: 'Category' })).toBeNull()

    // R1's ONE COLUMN for the cost fact: the badge that used to ride beside the category now
    // says free OR paid on every row — a blank cell would be the ambiguity R1 removes.
    const nvidiaRow = screen.getByText('NVIDIA: Nemotron 3 Super').closest('tr') as HTMLElement
    expect(within(nvidiaRow).getByText('free')).toBeInTheDocument()
    const deepseekRow = screen.getByText('DeepSeek V4 Flash').closest('tr') as HTMLElement
    expect(within(deepseekRow).getByText('paid')).toBeInTheDocument()
  })

  it('reads the row note on the name tooltip — the description\'s only read path', async () => {
    // The note is real data on every live row (12 of 12 carry one), and nothing used to read it:
    // it was edited in the modal and displayed nowhere. It stays off the table as a column — the
    // user's ruling — so the name's tooltip is where it reads.
    vi.mocked(fetchCuratedModels).mockResolvedValue([
      { ...mockModels[0], description: 'Free, 262K context, 120B MoE. Strong general-purpose writer.' },
      { ...mockModels[1] },
    ] as never)

    render(<CuratedModelsManager providers={mockProviders} loading={false} />)

    await waitFor(() => {
      expect(screen.getByText('NVIDIA: Nemotron 3 Super')).toBeInTheDocument()
    })
    const withNote = screen.getByText('NVIDIA: Nemotron 3 Super').closest('[data-tip]') as HTMLElement
    expect(withNote.getAttribute('data-tip')).toContain('120B MoE')
    // A row with NO note reads as its name alone: nothing is invented for it.
    const bare = screen.getByText('DeepSeek V4 Flash').closest('[data-tip]') as HTMLElement
    expect(bare.getAttribute('data-tip')).toBe('DeepSeek V4 Flash')
  })

  it('says "unpriced" for a row the provider prices nowhere — the third state, not a paid claim', async () => {
    // Phase 4: the cost is DERIVED, and "nobody has priced this" is not the same statement as
    // "it costs money". Before the column could hold `null`, this row rendered as `paid`.
    vi.mocked(fetchCuratedModels).mockResolvedValue([
      ...mockModels,
      {
        id: 'zai/never-priced',
        name: 'Never Priced',
        provider: 'openrouter',
        isFree: null,
        verified: false,
        thinking: 'none',
        location: 'cloud',
        curatedRowId: 3,
      },
    ] as never)

    render(<CuratedModelsManager providers={mockProviders} loading={false} />)

    await waitFor(() => {
      expect(screen.getByText('Never Priced')).toBeInTheDocument()
    })
    const row = screen.getByText('Never Priced').closest('tr') as HTMLElement
    expect(within(row).getByText('unpriced')).toBeInTheDocument()
    // The two states beside it still read as they did — the third one did not blur them.
    const nvidiaRow = screen.getByText('NVIDIA: Nemotron 3 Super').closest('tr') as HTMLElement
    expect(within(nvidiaRow).getByText('free')).toBeInTheDocument()
  })

  it('reads Provider · Name · Model · Cost, and carries each long value whole in a tooltip', async () => {
    render(<CuratedModelsManager providers={mockProviders} loading={false} />)
    await waitFor(() => {
      expect(screen.getByText('NVIDIA: Nemotron 3 Super')).toBeInTheDocument()
    })

    // The order is the scan order: which provider, what we call it, its exact spelling.
    expect(screen.getAllByRole('columnheader').map(h => h.textContent)).toEqual([
      'Provider ↑', 'Name', 'Model', 'Cost', 'Thinking', 'Actions',
    ])

    // jsdom has no layout, so the TRUNCATION is measured in the browser rather than here — what
    // is testable is that the full value is on the cell's tooltip, which is where a clipped name
    // or id is read. Both are asserted, because a truncated id is the case that costs the most.
    const nvidiaRow = screen.getByText('NVIDIA: Nemotron 3 Super').closest('tr') as HTMLElement
    expect(nvidiaRow.querySelector('[data-tip="NVIDIA: Nemotron 3 Super"]')).not.toBeNull()
    expect(
      nvidiaRow.querySelector('[data-tip="nvidia/nemotron-3-super-120b-a12b:free"]'),
    ).not.toBeNull()
  })

  it('copies the row\'s FULL model id, and says so in a toast', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText } })

    render(<CuratedModelsManager providers={mockProviders} loading={false} />)
    await waitFor(() => {
      expect(screen.getByText('NVIDIA: Nemotron 3 Super')).toBeInTheDocument()
    })

    const nvidiaRow = screen.getByText('NVIDIA: Nemotron 3 Super').closest('tr') as HTMLElement
    fireEvent.click(within(nvidiaRow).getByLabelText('Copy model id for NVIDIA: Nemotron 3 Super'))

    // The row's OWN value, not the truncated cell's text — that difference IS the button.
    await waitFor(() => expect(writeText).toHaveBeenCalledWith('nvidia/nemotron-3-super-120b-a12b:free'))
    expect(notifier.addSuccess).toHaveBeenCalledWith(
      'Copied', 'Model id copied: nvidia/nemotron-3-super-120b-a12b:free',
    )
  })

  it('opens the Verify dialog and reads our own record', async () => {
    vi.mocked(verifyCuratedModelWindow).mockResolvedValue(mockVerification as never)
    render(<CuratedModelsManager providers={mockProviders} loading={false} />)
    await waitFor(() => {
      expect(screen.getByText('NVIDIA: Nemotron 3 Super')).toBeInTheDocument()
    })

    const nvidiaRow = screen.getByText('NVIDIA: Nemotron 3 Super').closest('tr') as HTMLElement
    fireEvent.click(within(nvidiaRow).getByLabelText('Verify NVIDIA: Nemotron 3 Super'))

    // The dialog names the ROW'S WINDOW and says which check this is — not connectivity.
    expect(screen.getByRole('dialog', { name: 'Verify NVIDIA: Nemotron 3 Super' })).toBeInTheDocument()

    fireEvent.click(screen.getByText('Read our own record'))
    await waitFor(() => expect(verifyCuratedModelWindow).toHaveBeenCalledWith(1, false))

    // The result states the disagreement and the note verbatim: a check that adopted the
    // provider's number must not read as a no-op.
    expect(await screen.findByText(/The two numbers disagreed/)).toBeInTheDocument()
    expect(screen.getByText(/adopted the provider's 262144/)).toBeInTheDocument()
    // A dated claim says its age in words a person reads — not a raw float.
    expect(screen.getByText(/3\.5h old/)).toBeInTheDocument()
    // The row may have been adopted onto, so the list is re-read after the check.
    expect(fetchCuratedModels).toHaveBeenCalledTimes(2)
  })

  it('asks the provider again when that is the question chosen', async () => {
    vi.mocked(verifyCuratedModelWindow).mockResolvedValue({ ...mockVerification, refreshed: true, age_hours: 0.0001 } as never)
    render(<CuratedModelsManager providers={mockProviders} loading={false} />)
    await waitFor(() => {
      expect(screen.getByText('NVIDIA: Nemotron 3 Super')).toBeInTheDocument()
    })

    const nvidiaRow = screen.getByText('NVIDIA: Nemotron 3 Super').closest('tr') as HTMLElement
    fireEvent.click(within(nvidiaRow).getByLabelText('Verify NVIDIA: Nemotron 3 Super'))
    fireEvent.click(screen.getByText('Ask the provider again'))

    await waitFor(() => expect(verifyCuratedModelWindow).toHaveBeenCalledWith(1, true))
    expect(await screen.findByText(/a fresh provider fetch/)).toBeInTheDocument()
    // A fresh fetch is "just now" — the raw 0.0001h would read as a machine talking.
    expect(screen.getByText(/just now/)).toBeInTheDocument()
  })

  it('reports a check that could not run instead of crashing the row', async () => {
    vi.mocked(verifyCuratedModelWindow).mockRejectedValue(new Error('Curated model not found'))
    render(<CuratedModelsManager providers={mockProviders} loading={false} />)
    await waitFor(() => {
      expect(screen.getByText('NVIDIA: Nemotron 3 Super')).toBeInTheDocument()
    })

    const nvidiaRow = screen.getByText('NVIDIA: Nemotron 3 Super').closest('tr') as HTMLElement
    fireEvent.click(within(nvidiaRow).getByLabelText('Verify NVIDIA: Nemotron 3 Super'))
    fireEvent.click(screen.getByText('Read our own record'))

    // An honest report, never a crash: the dialog stays open and says what went wrong.
    expect(await screen.findByRole('alert')).toHaveTextContent('Curated model not found')
    expect(screen.getByRole('dialog', { name: 'Verify NVIDIA: Nemotron 3 Super' })).toBeInTheDocument()
  })

  it('refuses to invent a provider on an install that has none', async () => {
    // Measured on a from-zero install (2026-11-21): this list fabricated four providers with
    // `openrouter` first and pre-filled it in the form, so the first "Add Model" posted a curated
    // model for a provider that did not exist — `400 Provider not found: openrouter`.
    vi.mocked(fetchCuratedModels).mockResolvedValue([] as never)
    render(<CuratedModelsManager providers={[]} loading={false} />)

    await waitFor(() => {
      expect(screen.getByText(/No provider on this install yet/)).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: /Add Model/ })).toBeDisabled()
  })
})
