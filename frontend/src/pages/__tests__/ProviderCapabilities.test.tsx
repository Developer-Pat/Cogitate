/**
 * The capabilities read-out page and its editor — phase 6, group 2.
 *
 * The read-out's tests pin the two things it must not get wrong: it shows WHICH rung answered (a
 * chain with no reason is the ambiguity the page exists to remove), and it says plainly that it
 * speaks for the capability rather than for an agent's turn (the two legitimately differ).
 *
 * The editor's tests pin the contract with the API: **the WHOLE chain is sent, in the order shown,
 * built from the STORED rows** — not from the resolution, which can be an agent's declaration, can
 * expand a class into several rows, and leaves out the rows switched off.
 *
 * Since phase 7 the page also ORIENTS the reader — what a capability is, that its chain is tried in
 * order, and why one would be configured — and that copy is pinned here, because copy nobody asserts
 * is copy the next edit can drop.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@/test/test-utils'
import ProviderCapabilities from '../ProviderCapabilities'
import type { CapabilityReadoutResponse } from '@/types/capabilities'
import type { ProviderConfigListResponse } from '@/types/providers'

const { getCapabilities, updateCapability, getProviders, listAgents, fetchCurated } = vi.hoisted(
  () => ({
    getCapabilities: vi.fn(),
    updateCapability: vi.fn(),
    getProviders: vi.fn(),
    listAgents: vi.fn(),
    fetchCurated: vi.fn(),
  }),
)

vi.mock('@/services/domains/providers/capabilitiesService', () => ({
  capabilitiesService: { getCapabilities, updateCapability },
}))

vi.mock('@/services/domains/providers/providerConfigService', () => ({
  providerConfigService: { getProviders },
}))

vi.mock('@/services/domains/agents/agentRosterService', () => ({
  agentRosterService: { listAgents },
}))

// The editor's model picker reads the curated list; a provider with none keeps free text.
vi.mock('@/services/domains/providers/curatedModelsService', () => ({
  fetchCuratedModels: fetchCurated,
}))

/** The picker's roster, as the roster service answers it (the BACKEND id beside the name). */
const AGENTS = [
  { id: 19, name: 'Bob' },
  { id: 56, name: 'Lois' },
]

const PROVIDERS = {
  providers: [
    { id: 3, name: 'deepseek', display_name: 'DeepSeek', provider_type: 'deepseek', is_active: true },
    { id: 5, name: 'llama', display_name: 'llama.cpp', provider_type: 'openai', is_active: true },
  ],
  total: 2,
} as unknown as ProviderConfigListResponse

const READOUT: CapabilityReadoutResponse = {
  kinds: ['llm', 'speech', 'process'],
  total: 3,
  capabilities: [
    {
      key: 'title',
      label: 'Title service',
      kind: 'llm',
      enabled: true,
      reason: 'capability config',
      chain: 'deepseek/deepseek-v4-flash -> llama/Bonsai-27B-Q1_0.gguf',
      primary: {
        ordinal: 0,
        provider: 'deepseek',
        provider_id: 3,
        model: 'deepseek-v4-flash',
        location: 'cloud',
        source: 'row',
        availability_state: 'available',
        available: true,
        availability_reason: 'the provider answers and catalogues 2 model(s)',
        checked_at: '2026-10-05T12:23:07.045Z',
      },
      backups: [
        {
          ordinal: 1,
          provider: 'llama',
          provider_id: 5,
          model: 'Bonsai-27B-Q1_0.gguf',
          location: 'local',
          source: 'row',
          availability_state: 'down',
          available: false,
          availability_reason: 'the local server is not running and no local server answers',
          checked_at: '2026-10-05T12:23:06.609Z',
        },
      ],
      configured: [
        {
          ordinal: 0,
          provider_id: 3,
          model: 'deepseek-v4-flash',
          thinking: null,
          enabled: true,
          source: 'stored',
        },
        { ordinal: 1, require_location: 'local', enabled: true, source: 'stored' },
      ],
    },
    {
      key: 'chat',
      label: 'Agent chat',
      kind: 'llm',
      enabled: true,
      reason: 'global default',
      chain: 'llama/Bonsai-27B-Q1_0.gguf',
      primary: {
        // The LIVE shape: the seeded capability's own chain is the BACKUP layer, so its one
        // candidate is STORED as a backup while being the first attempt with no agent on the ladder.
        ordinal: 1,
        provider: 'llama',
        model: 'Bonsai-27B-Q1_0.gguf',
        location: 'local',
        source: 'default',
      },
      backups: [],
      configured: [{ ordinal: 1, provider_id: 5, enabled: true, source: 'stored' }],
    },
    {
      key: 'summary',
      label: 'Summaries',
      kind: 'llm',
      enabled: false,
      reason: 'disabled',
      chain: '(nothing configured)',
      primary: null,
      backups: [],
      configured: [{ ordinal: 0, service_name: 'zz-off-engine', enabled: false, source: 'stored' }],
    },
  ],
}

describe('ProviderCapabilities (the read-out)', () => {
  beforeEach(() => {
    getCapabilities.mockReset()
    updateCapability.mockReset()
    getProviders.mockReset()
    listAgents.mockReset()
    fetchCurated.mockReset()
    getProviders.mockResolvedValue(PROVIDERS)
    listAgents.mockResolvedValue(AGENTS)
    // Default: no curated rows, so every attempt's model field stays free text.
    fetchCurated.mockResolvedValue([])
  })

  it('shows each capability with its chain, the role of every attempt and the rung that answered', async () => {
    getCapabilities.mockResolvedValue(READOUT)

    render(<ProviderCapabilities />)

    // scoped to ONE card: the same chain text legitimately appears on more than one capability
    const titleCard = within(await screen.findByLabelText('Title service'))
    expect(titleCard.getByText('deepseek/deepseek-v4-flash')).toBeTruthy()
    expect(titleCard.getByText('llama/Bonsai-27B-Q1_0.gguf')).toBeTruthy()
    expect(titleCard.getByText('primary')).toBeTruthy()
    expect(titleCard.getByText('backup #1')).toBeTruthy()
    expect(titleCard.getByText('capability config')).toBeTruthy()

    // WHY it answered — a candidate from a rung ABOVE the capability says so
    const chatCard = within(screen.getByLabelText('Agent chat'))
    expect(chatCard.getByText('global default')).toBeTruthy()
    expect(chatCard.getByText('(from the default row)')).toBeTruthy()
    // the role is the ATTEMPT's place in the resolved chain, and a stored ordinal that disagrees
    // is named beside it rather than silently contradicting the order
    expect(chatCard.getByText(/primary \(stored #2\)/)).toBeTruthy()

    // only the one capability is configured; the other two resolved elsewhere or are off
    expect(screen.getAllByText('capability config')).toHaveLength(1)
    expect(screen.getAllByText('primary')).toHaveLength(1)
  })

  it('says which view it is showing — the capability, not an agent turn', async () => {
    getCapabilities.mockResolvedValue(READOUT)

    render(<ProviderCapabilities />)

    await screen.findByText('Title service')
    expect(screen.getByText(/is in play only where a live turn passes one/)).toBeTruthy()
  })

  it('orients the reader — what a capability is, that the chain is tried in order, and why configure one', async () => {
    getCapabilities.mockResolvedValue(READOUT)

    render(<ProviderCapabilities />)

    await screen.findByText('Title service')
    // what a capability IS (the page's own words, not the read-out's)
    expect(screen.getByText(/A capability is a job the app needs done/)).toBeTruthy()
    // that the chain is tried in ORDER — the fact the read-out alone does not state
    expect(screen.getByText(/tries its chain in order/)).toBeTruthy()
    // and both reasons to configure one: the local preference and the fallback
    expect(
      screen.getByText(/prefer a local engine, or to give a capability somewhere to fall back/),
    ).toBeTruthy()
  })

  it('names the card’s key readout, so it does not read as a stray word', async () => {
    getCapabilities.mockResolvedValue(READOUT)

    render(<ProviderCapabilities />)

    const card = within(await screen.findByLabelText('Title service'))
    expect(card.getByLabelText('Capability key: title')).toBeTruthy()
  })

  it('opens its own help context from the banner, not the drawer’s index fallback', async () => {
    getCapabilities.mockResolvedValue(READOUT)
    // the slug is the contract with the WIKI: the backend matches a help page's frontmatter
    // `category` EXACTLY, so a page mounting the wrong slug silently opens the index instead.
    const opened: unknown[] = []
    const listener = (event: Event) => opened.push((event as CustomEvent).detail?.context)

    window.addEventListener('open-help-modal', listener)
    try {
      render(<ProviderCapabilities />)
      await screen.findByText('Title service')

      fireEvent.click(screen.getByRole('button', { name: /help/i }))

      expect(opened).toEqual(['providers-capabilities'])
    } finally {
      window.removeEventListener('open-help-modal', listener)
    }
  })

  it('resolves for an agent only when one is picked, and defaults to the sessionless view', async () => {
    getCapabilities.mockResolvedValue(READOUT)

    render(<ProviderCapabilities />)

    const picker = (await screen.findByLabelText(
      'Resolve the capabilities for an agent',
    )) as HTMLSelectElement

    // the default IS the sessionless view, labelled as such, and rung 2 was not asked for
    expect(picker.value).toBe('')
    expect(screen.getByText(/No agent — each capability’s own chain/)).toBeTruthy()
    expect(getCapabilities).toHaveBeenCalledWith(null)

    // THE OPTION MUST EXIST FIRST (2026-11-22). The picker renders with the page; its options come
    // from the agent roster read, which settles LATER. Firing a change into a select that has no
    // `56` option leaves its value '' — the page then reads with `null` and this test failed under
    // full-suite load with no behavioural cause (passed 19/19 alone). Wait for the option.
    await waitFor(() => expect(screen.getByRole('option', { name: 'Lois' })).toBeTruthy())

    // picking an agent re-reads THROUGH the agent rung, with the BACKEND id
    fireEvent.change(picker, { target: { value: '56' } })
    await waitFor(() => expect(getCapabilities).toHaveBeenCalledWith(56))
    expect(await screen.findByText(/For Lois/)).toBeTruthy()
  })

  it('reports a switched-OFF capability as off, with no attempt to show', async () => {
    getCapabilities.mockResolvedValue(READOUT)

    render(<ProviderCapabilities />)

    await screen.findByText('Summaries')
    const card = screen.getByLabelText('Summaries')
    expect(card.textContent).toContain('Off — nothing resolves for this capability.')
    expect(card.textContent).toContain('disabled')
    expect(card.textContent).not.toContain('primary')
  })

  it('shows what the availability read found on each attempt, and WHEN it looked', async () => {
    getCapabilities.mockResolvedValue(READOUT)

    render(<ProviderCapabilities />)

    const titleCard = within(await screen.findByLabelText('Title service'))

    // The state is ON the row (never hover-only), and the two states are distinguishable:
    // the local backup is `down`, not the same word as a cloud row that cannot be attempted.
    expect(titleCard.getByText('up')).toBeTruthy()
    expect(titleCard.getByText('down')).toBeTruthy()

    // The read's own reason rides the chip, and the staleness window is VISIBLE — a state with no
    // age reads as a fact rather than as a reading.
    expect(
      titleCard.getByLabelText(
        /Available — the provider answers and catalogues 2 model\(s\) \(checked 2026-10-05T12:23:07.045Z\)/,
      ),
    ).toBeTruthy()
    expect(titleCard.getByLabelText(/Not available — the local server is not running/)).toBeTruthy()
    expect(titleCard.getAllByText(/^checked /)).toHaveLength(2)
  })

  it('claims nothing for a service nobody checked', async () => {
    getCapabilities.mockResolvedValue(READOUT)

    render(<ProviderCapabilities />)

    // The `chat` card's candidate carries no availability reading (`unknown`): no chip, no stamp.
    // Painting it would call an unprobed service broken — the exact false signal to avoid.
    const chatCard = within(await screen.findByLabelText('Agent chat'))
    expect(chatCard.queryByText('up')).toBeNull()
    expect(chatCard.queryByText('down')).toBeNull()
    expect(chatCard.queryByText(/^checked /)).toBeNull()
  })

  it('shows the failure and offers a retry instead of rendering an empty grid', async () => {
    getCapabilities.mockRejectedValueOnce(new Error('Could not read the capabilities — boom'))
    getCapabilities.mockResolvedValue(READOUT)

    render(<ProviderCapabilities />)

    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('boom')
    expect(screen.queryByText('Title service')).toBeNull()

    // the retry re-reads and the page recovers
    screen.getByRole('button', { name: 'Retry' }).click()
    await waitFor(() => expect(getCapabilities).toHaveBeenCalledTimes(2))
    expect(await screen.findByText('Title service')).toBeTruthy()
    expect(screen.queryByRole('alert')).toBeNull()
  })
})

describe('ProviderCapabilities (the editor)', () => {
  beforeEach(() => {
    getCapabilities.mockReset()
    updateCapability.mockReset()
    getProviders.mockReset()
    listAgents.mockReset()
    fetchCurated.mockReset()
    getCapabilities.mockResolvedValue(READOUT)
    getProviders.mockResolvedValue(PROVIDERS)
    listAgents.mockResolvedValue(AGENTS)
    fetchCurated.mockResolvedValue([])
  })

  async function openEditor() {
    render(<ProviderCapabilities />)
    const card = within(await screen.findByLabelText('Title service'))
    fireEvent.click(card.getByRole('button', { name: 'Edit' }))
    return card
  }

  it('opens on the STORED chain, not on the resolution', async () => {
    const card = await openEditor()

    // two stored rows: the provider row, then the CLASS (not the two rows the class expanded into)
    expect(card.getByLabelText('Attempt 1: provider')).toBeTruthy()
    const classSelect = card.getByLabelText('Attempt 2: class') as HTMLSelectElement
    expect(classSelect.value).toBe('local')
    expect(card.queryByLabelText('Attempt 3: provider')).toBeNull()
  })

  it('edits in a MODAL, leaving the readout visible behind it', async () => {
    const card = await openEditor()

    // the draft lives in a native dialog, open — one capability per modal
    const cardEl = screen.getByLabelText('Title service') as HTMLElement
    const dialog = cardEl.querySelector('dialog') as HTMLDialogElement | null
    expect(dialog).toBeTruthy()
    expect(dialog!.open).toBe(true)
    // the editor's own controls are INSIDE it, and the readout it replaced inline is NOT
    expect(dialog!.contains(card.getByRole('button', { name: 'Save' }))).toBe(true)
    expect(dialog!.contains(card.getByLabelText('Attempt 1: provider'))).toBe(true)
    expect(dialog!.contains(card.getByLabelText('Off'))).toBe(true)

    // the chain readout stays on the card, so dismissing returns to the list as it was
    expect(card.getByText('primary')).toBeTruthy()
    expect(card.getByText('deepseek/deepseek-v4-flash')).toBeTruthy()
  })

  it('picks an attempt’s MODEL from the curated list for its provider, sending the model id', async () => {
    fetchCurated.mockResolvedValue([
      { id: 'deepseek-v4-flash', name: 'DeepSeek V4 Flash', provider: 'deepseek', isFree: false, verified: true },
      { id: 'deepseek-v4-pro', name: 'DeepSeek V4 Pro', provider: 'deepseek', isFree: false, verified: false },
    ])
    updateCapability.mockResolvedValue(READOUT)
    const card = await openEditor()

    // attempt 1 names provider id 3 (deepseek) — the curated list answers for it, so the field is a
    // PICKER; the stored model is carried by the list, so it is selected with no extra option, and
    // the empty option is what "the provider row's own default" has always meant
    const select = (await card.findByLabelText('Attempt 1: model')) as HTMLSelectElement
    expect(select.tagName).toBe('SELECT')
    expect(select.value).toBe('deepseek-v4-flash')
    expect([...select.options].map((option) => option.value)).toEqual([
      '',
      'deepseek-v4-flash',
      'deepseek-v4-pro',
    ])
    // the LABEL is the human name; the VALUE is the model id the provider's API and the chain use
    expect(select.options[1].textContent).toBe('DeepSeek V4 Flash ✓')

    fireEvent.change(select, { target: { value: 'deepseek-v4-pro' } })
    fireEvent.click(card.getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(updateCapability).toHaveBeenCalledTimes(1))
    const payload = updateCapability.mock.calls[0][1] as { candidates: { model: string | null }[] }
    expect(payload.candidates[0].model).toBe('deepseek-v4-pro')
  })

  it('keeps an attempt’s model that the curated list does not carry, rather than dropping it', async () => {
    fetchCurated.mockResolvedValue([
      { id: 'deepseek-v4-flash', name: 'DeepSeek V4 Flash', provider: 'deepseek', isFree: false, verified: true },
    ])
    getCapabilities.mockResolvedValue({
      ...READOUT,
      capabilities: READOUT.capabilities.map((capability) =>
        capability.key !== 'title'
          ? capability
          : {
              ...capability,
              configured: [
                { ordinal: 0, provider_id: 3, model: 'legacy-model', thinking: null, enabled: true, source: 'stored' },
              ],
            },
      ),
    })
    const card = await openEditor()

    // the stored model is not in the curated list: it stays selectable as its own option, so opening
    // the editor and saving cannot silently replace it with the provider row's default
    const select = (await card.findByLabelText('Attempt 1: model')) as HTMLSelectElement
    expect(select.value).toBe('legacy-model')
    expect([...select.options].map((option) => option.value)).toEqual([
      '',
      'legacy-model',
      'deepseek-v4-flash',
    ])
    expect(select.options[1].textContent).toBe('legacy-model (not in the curated list)')
  })

  it('sends the WHOLE chain, in the order shown, with the forms the API accepts', async () => {
    updateCapability.mockResolvedValue(READOUT)
    const card = await openEditor()

    fireEvent.change(card.getByLabelText('Attempt 1: model'), {
      target: { value: 'deepseek-v4-flash' },
    })
    fireEvent.change(card.getByLabelText('Attempt 2: model'), { target: { value: 'bespoke' } })
    fireEvent.change(card.getByLabelText('Attempt 2: thinking'), { target: { value: 'mandatory' } })
    fireEvent.click(card.getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(updateCapability).toHaveBeenCalledTimes(1))
    expect(updateCapability).toHaveBeenCalledWith('title', {
      enabled: true,
      candidates: [
        { provider_id: 3, require_location: null, service_name: null, model: 'deepseek-v4-flash', thinking: null, enabled: true },
        { provider_id: null, require_location: 'local', service_name: null, model: 'bespoke', thinking: 'mandatory', enabled: true },
      ],
    })
  })

  it('reorders the chain with the Up/Down controls', async () => {
    updateCapability.mockResolvedValue(READOUT)
    const card = await openEditor()

    fireEvent.click(card.getByRole('button', { name: 'Move attempt 2 earlier' }))
    fireEvent.click(card.getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(updateCapability).toHaveBeenCalledTimes(1))
    const payload = updateCapability.mock.calls[0][1] as { candidates: { require_location: string | null }[] }
    expect(payload.candidates[0].require_location).toBe('local')
    expect(payload.candidates[1].require_location).toBeNull()
  })

  it('keeps the end-row Up/Down tips reachable while those controls are DISABLED', async () => {
    const card = await openEditor()

    // row 1 is first: its Up is disabled, so the tip has to live on a WRAPPER — a disabled button
    // fires no hover — and it says WHY rather than repeating an action that cannot be taken
    const firstUp = card.getByLabelText('Move attempt 1 earlier') as HTMLButtonElement
    expect(firstUp.disabled).toBe(true)
    expect(firstUp.hasAttribute('data-tip')).toBe(false)
    expect(firstUp.parentElement?.getAttribute('data-tip')).toBe('Already first')

    // row 2's Up is live, so it carries its OWN tip and gets no wrapper (a wrapper around a live
    // control is a stray element in the row)
    const secondUp = card.getByLabelText('Move attempt 2 earlier') as HTMLButtonElement
    expect(secondUp.disabled).toBe(false)
    expect(secondUp.getAttribute('data-tip')).toBe('Move this attempt earlier')
    expect(secondUp.parentElement?.getAttribute('data-tip')).toBeNull()

    // and the LAST row is the other end
    const lastDown = card.getByLabelText('Move attempt 2 later') as HTMLButtonElement
    expect(lastDown.disabled).toBe(true)
    expect(lastDown.parentElement?.getAttribute('data-tip')).toBe('Already last')
  })

  it('switches the capability OFF through the same write', async () => {
    updateCapability.mockResolvedValue({ ...READOUT.capabilities[0], enabled: false, reason: 'disabled' })
    const card = await openEditor()

    fireEvent.click(card.getByLabelText('Off'))
    fireEvent.click(card.getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(updateCapability).toHaveBeenCalledTimes(1))
    expect(updateCapability.mock.calls[0][1]).toMatchObject({ enabled: false })
  })

  it('keeps the editor open with the server’s own refusal, so the offending attempt can be fixed', async () => {
    updateCapability.mockRejectedValue(new Error('candidate 0: no provider with id 999999'))
    const card = await openEditor()

    fireEvent.click(card.getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(updateCapability).toHaveBeenCalledTimes(1))
    expect(await card.findByText(/no provider with id 999999/)).toBeTruthy()
    // still editing: the Save control is there and the read-only chain is not
    expect(card.getByRole('button', { name: 'Save' })).toBeTruthy()
  })
})
