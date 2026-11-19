/**
 * THE BANK SELECTORS tests (2026-09-03, the akeys Phase 5b — the
 * keyboard-attached direct selection).
 *
 * Pin the behaviors:
 * 1. The MacroKeyboard renders BOTH bank selectors (F after the M
 *    group, A beside the A keys).
 * 2. Picking in the F-selector changes the F-side selection only.
 * 3. Picking in the A-selector PERSISTS the A source (select = the
 *    new default — no separate step).
 * 4. The selectors are surface-scoped through the store (agent vs
 *    exa isolation holds at the keyboard too).
 */
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, beforeEach } from 'vitest';
import MacroKeyboard from '../MacroKeyboard';
import { useSystemMacrosStore } from '@/stores/macroSetsStore';
import { loadAKeysSourceId } from '@/utils/aKeysSource';
import { F_SELECTION_BASE_KEY, loadScopedId } from '@/utils/macroSurface';

const noop = () => {};

const MACRO_SETS = [
  {
    id: 1,
    mode_slug: 'agent',
    topic: 'Greetings',
    name: 'Greetings & Check-ins',
    description: 'conversational openers',
    is_active: true,
    f1_macro: 'Hello',
    f2_macro: 'Are you OK?',
    f3_macro: '',
    f4_macro: '',
    f5_macro: '',
  },
]

const TOPICS = [
  {
    id: 1,
    name: 'System Guide',
    slug: 'system-guide',
    description: 'the default',
    namespace: 'agent',
    topic_mappings: [{ topic: 'Greetings', slot_start: 'M1' }],
  },
  {
    id: 2,
    name: 'Coding',
    slug: 'coding',
    description: 'programming',
    namespace: 'agent',
    topic_mappings: [],
  },
  {
    id: 3,
    name: 'A-Key Macros',
    slug: 'a-key-macros',
    description: 'the action bank',
    namespace: 'agent',
    topic_mappings: [{ topic: 'Greetings', slot_start: 'A1' }],
  },
]

beforeEach(() => {
  localStorage.clear()
  // persist the initial states too — the isolation assertions read
  // the STORAGE keys, not just the store state
  localStorage.setItem('cogitate_selected_meta_topic', '1')
  localStorage.setItem('cogitate_akeys_meta_topic', '3')
  useSystemMacrosStore.setState({
    metaTopics: TOPICS as any, // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
    selectedMetaTopicId: 1,
    aKeysMetaTopicId: 3,
    surface: 'agent',
    isLoadingMetaTopics: false,
  })
})

function renderKeyboard() {
  return render(
    <MacroKeyboard
      onMacroSelect={noop}
      compact={true}
      metaTopics={TOPICS as any} // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
      selectedMetaTopicId={1}
      selectMetaTopic={noop}
      macros={MACRO_SETS as any} // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
      aKeysMetaTopicId={3}
    />,
  )
}

describe('The bank selectors (the keyboard-attached direct selection)', () => {
  it('renders the F-selector AND the A-selector icons on the keyboard', () => {
    renderKeyboard()
    expect(screen.getByLabelText(/F topic:/)).toBeTruthy()
    expect(screen.getByLabelText(/A source:/)).toBeTruthy()
  })

  it("the tooltips carry the STATE readouts (2026-09-05, the user's ask: which topic is loaded)", () => {
    renderKeyboard()
    const fBtn = screen.getByLabelText(/F topic:/)
    const aBtn = screen.getByLabelText(/A source:/)
    // the visible tooltip = the state readout (F topic: X / A source: Y)
    expect(fBtn.parentElement?.getAttribute('data-tip')).toBe('F topic: System Guide')
    expect(aBtn.parentElement?.getAttribute('data-tip')).toBe('A source: A-Key Macros')
    // the aria-label carries the same state (a11y)
    expect(fBtn.getAttribute('aria-label')).toContain('System Guide')
    expect(aBtn.getAttribute('aria-label')).toContain('A-Key Macros')
  })

  it("an empty F selection reads 'none' — the empty F-keys explained", () => {
    // the TopicFlyoutButton reads the STORE (the MacroKeyboard props
    // only drive the key content) — clear the selection first.
    useSystemMacrosStore.setState({ selectedMetaTopicId: null })
    render(
      <MacroKeyboard
        onMacroSelect={noop}
        compact={true}
        metaTopics={TOPICS as any} // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
        selectedMetaTopicId={null}
        selectMetaTopic={noop}
        macros={MACRO_SETS as any} // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
        aKeysMetaTopicId={3}
      />,
    )
    const fBtn = screen.getByLabelText(/F topic:/)
    expect(fBtn.parentElement?.getAttribute('data-tip')).toBe('F topic: none')
  })

  it('the flyouts carry the STATE LINE in the header + ONE marker grammar (no star/default UI)', async () => {
    renderKeyboard()
    // open the F flyout
    fireEvent.click(screen.getByLabelText(/F topic:/))
    // assert against the listbox's textContent — the topic name sits
    // in a nested span; getByText only matches direct text nodes
    let flyout = await screen.findByRole('listbox')
    expect(flyout.textContent).toContain('Current: System Guide')
    expect(screen.queryByText('Set as default')).toBeNull()
    expect(screen.queryByText(/Default topic/)).toBeNull()
    expect(screen.getByText('Active')).toBeTruthy()
    fireEvent.keyDown(document.body, { key: 'Escape' })
    // open the A flyout
    fireEvent.click(screen.getByLabelText(/A source:/))
    flyout = await screen.findByRole('listbox')
    expect(flyout.textContent).toContain('Current: A-Key Macros')
    expect(screen.getByText('Source')).toBeTruthy()
  })

  it('an empty F-bank flyout says the keys are empty (the none-state line)', async () => {
    useSystemMacrosStore.setState({ selectedMetaTopicId: null })
    renderKeyboard()
    fireEvent.click(screen.getByLabelText(/F topic: none/))
    const flyout = await screen.findByRole('listbox')
    expect(flyout.textContent).toContain('Current: none')
  })

  it('the A-selector PERSISTS its pick as the A source (select = default)', async () => {
    renderKeyboard()
    // open the A flyout and pick 'Coding'
    const aBtn = screen.getByLabelText(/A source:/)
    fireEvent.click(aBtn)
    const coding = await screen.findByText('Coding')
    fireEvent.click(coding)
    // the storage key now holds the pick for the agent surface
    expect(loadAKeysSourceId('agent')).toBe(2)
  })

  it('the F-selector writes the F-side key only — never the A key', async () => {
    renderKeyboard()
    const fBtn = screen.getByLabelText(/F topic:/)
    fireEvent.click(fBtn)
    const coding = await screen.findByText('Coding')
    fireEvent.click(coding)
    // F-side selection persisted; the A source untouched
    expect(loadScopedId(F_SELECTION_BASE_KEY, 'agent')).toBe(2)
    expect(loadAKeysSourceId('agent')).toBe(3)
  })
})
