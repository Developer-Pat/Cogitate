/**
 * THE A-KEY BANK tests (2026-09-03, the akeys roadmap Phase 2).
 *
 * Pin the MacroKeyboard A-section behaviors:
 * 1. A seeded A-source renders its mapped macro sets as A1-A5 flyouts.
 * 2. An empty slot (no mapping / no macro set / no items) disables.
 * 3. No A-source (aKeysMetaTopicId null or unknown) deactivates the
 *    whole A-row with the visible reason — never arbitrary content.
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import MacroKeyboard from '../MacroKeyboard';

const noop = () => {};

// A meta-topic + two macro sets: 'Greetings' (A1's mapped set) with
// f1-f2 populated + f3-f5 empty; 'Diagnostics' (A2's mapped set) with
// f1 populated. The A source maps to both.
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
  {
    id: 2,
    mode_slug: 'agent',
    topic: 'Diagnostics',
    name: 'Diagnostics',
    description: 'probe questions',
    is_active: true,
    f1_macro: 'What tools do you have access to?',
    f2_macro: '',
    f3_macro: '',
    f4_macro: '',
    f5_macro: '',
  },
]

const A_SOURCE = {
  id: 10,
  name: 'A-Key Macros',
  slug: 'a-key-macros',
  description: 'the action bank',
  namespace: 'agent',
  topic_mappings: [
    { topic: 'Greetings', slot_start: 'A1' },
    { topic: 'Diagnostics', slot_start: 'A2' },
    // A3-A5 map to nothing (empty slots)
  ],
}

const EMPTY_SOURCE = {
  id: 11,
  name: 'Some Other Topic',
  slug: 'other',
  description: '',
  namespace: 'agent',
  topic_mappings: [],
}

describe('The A-key bank (the data-driven flyouts)', () => {
  it('renders the A-source mapped set prompts in the A1/A2 flyouts', () => {
    render(
      <MacroKeyboard
        onMacroSelect={noop}
        compact={true}
        metaTopics={[A_SOURCE]}
        selectedMetaTopicId={1}
        selectMetaTopic={noop}
        macros={MACRO_SETS}
        aKeysMetaTopicId={10}
      />,
    )
    // the flyout items are present in the DOM (the dropdown content)
    expect(screen.getByText('Hello')).toBeTruthy()
    expect(screen.getByText('Are you OK?')).toBeTruthy()
    expect(screen.getByText('What tools do you have access to?')).toBeTruthy()
  })

  it('empty slots render as disabled buttons with Empty tooltips — no phantom content', () => {
    render(
      <MacroKeyboard
        onMacroSelect={noop}
        compact={true}
        metaTopics={[A_SOURCE]}
        selectedMetaTopicId={1}
        selectMetaTopic={noop}
        macros={MACRO_SETS}
        aKeysMetaTopicId={10}
      />,
    )
    const buttons = screen.getAllByRole('button', { name: /^A[1-5]$/ })
    expect(buttons).toHaveLength(5)
    // A3-A5 have no mapping -> disabled (the empty slots)
    const a3 = screen.getByRole('button', { name: 'A3' })
    expect((a3 as HTMLButtonElement).disabled).toBe(true)
  })

  it('no A-source deactivates the row with the visible reason (never arbitrary content)', () => {
    render(
      <MacroKeyboard
        onMacroSelect={noop}
        compact={true}
        metaTopics={[A_SOURCE, EMPTY_SOURCE]}
        selectedMetaTopicId={1}
        selectMetaTopic={noop}
        macros={MACRO_SETS}
        aKeysMetaTopicId={null}
      />,
    )
    // the row shows the disabled placeholder + the reason tooltip text
    expect(screen.getByText('A-keys')).toBeTruthy()
    expect(screen.getByText('No Action-key source — set one on the Macros page')).toBeTruthy()
    // none of the mapped prompts leak through — no arbitrary content
    expect(screen.queryByText('Hello')).toBeNull()
  })

  it('an unknown A-source id deactivates the row too', () => {
    render(
      <MacroKeyboard
        onMacroSelect={noop}
        compact={true}
        metaTopics={[A_SOURCE]}
        selectedMetaTopicId={1}
        selectMetaTopic={noop}
        macros={MACRO_SETS}
        aKeysMetaTopicId={999}
      />,
    )
    expect(screen.getByText('No Action-key source — set one on the Macros page')).toBeTruthy()
  })
})
