import { beforeEach, describe, expect, it } from 'vitest'
import {
  usePromptHistoryStore,
  MAX_HISTORY,
  matchKey,
  sortPrompts,
  dedupePrompts,
  type HistoryPrompt,
} from '../promptHistoryStore'

/**
 * THE PROMPT HISTORY STORE (2026-09-15, reworked 2026-09-17).
 *
 * Why this test exists at all: the store's write side is called from the send path,
 * and exercising THAT means firing a real LLM request. The user's standing rule is to
 * announce live calls and wait, so the routing is checked here instead — the trimming,
 * the ORDERING, the dedup, the ids, and the cap are all pure functions of the store.
 *
 * WHAT CHANGED AND WHY THE OLD EXPECTATIONS ARE GONE. This store was newest-first and
 * kept a row per send, deliberately: "retrying a prompt is normal, so two sends of the
 * SAME text are two entries". The user asked for the opposite — a prompt already in
 * the list is not added again, and the list is kept alphabetical. So the test that
 * asserted two identical sends produce two entries is not a regression to fix; its
 * premise was reversed on purpose, and it is now a DEDUP test.
 *
 * The one thing these tests deliberately CANNOT prove: that the page calls `addPrompt`
 * on send. That is a two-line call site, verified by reading it.
 */
describe('the prompt history store', () => {
  beforeEach(() => {
    usePromptHistoryStore.setState({ prompts: [] })
  })

  const { addPrompt, removePrompt, clearAll } = usePromptHistoryStore.getState()

  it('keeps the list ALPHABETICAL', () => {
    addPrompt('second', '16')
    addPrompt('first', '16')
    const { prompts } = usePromptHistoryStore.getState()
    expect(prompts.map((p) => p.text)).toEqual(['first', 'second'])
  })

  it('sorts case-insensitively — a capitalised prompt does not jump the queue', () => {
    addPrompt('banana', '16')
    addPrompt('Apple', '16')
    addPrompt('cherry', '16')
    expect(usePromptHistoryStore.getState().prompts.map((p) => p.text)).toEqual([
      'Apple',
      'banana',
      'cherry',
    ])
  })

  it('records the originating session so a scope filter stays possible', () => {
    addPrompt('a prompt', '42')
    expect(usePromptHistoryStore.getState().prompts[0].sessionId).toBe('42')
  })

  it('accepts a null session (the page has no current session)', () => {
    addPrompt('a prompt', null)
    expect(usePromptHistoryStore.getState().prompts[0].sessionId).toBeNull()
  })

  it('trims the stored text', () => {
    addPrompt('   padded prompt   ', '16')
    expect(usePromptHistoryStore.getState().prompts[0].text).toBe('padded prompt')
  })

  // An attachments-only send carries empty text. Storing it would put a blank row in
  // the history that the user cannot account for.
  it('ignores a blank prompt rather than storing an empty row', () => {
    addPrompt('', '16')
    addPrompt('   ', '16')
    expect(usePromptHistoryStore.getState().prompts).toHaveLength(0)
  })

  // ── the dedup (2026-09-17) ────────────────────────────────────────────────

  it('does not add a prompt it already holds', () => {
    addPrompt('explain the conduit', '16')
    addPrompt('explain the conduit', '16')
    const { prompts } = usePromptHistoryStore.getState()
    expect(prompts).toHaveLength(1)
    expect(prompts[0].text).toBe('explain the conduit')
  })

  it('treats case and whitespace differences as the SAME prompt', () => {
    // what the eye reads as one prompt must not become two rows
    addPrompt('Explain   The   Conduit', '16')
    addPrompt('explain the conduit', '16')
    addPrompt('  EXPLAIN THE CONDUIT  ', '16')
    expect(usePromptHistoryStore.getState().prompts).toHaveLength(1)
  })

  it('does NOT move an existing prompt when it is sent again', () => {
    addPrompt('zzz last alphabetically', '16')
    addPrompt('aaa first alphabetically', '16')
    const before = usePromptHistoryStore.getState().prompts.find((p) => p.text === 'zzz last alphabetically')!

    addPrompt('zzz last alphabetically', '16')

    const after = usePromptHistoryStore.getState().prompts.find((p) => p.text === 'zzz last alphabetically')!
    // "do not add" means the entry keeps its place and its original timestamp —
    // a repeat is not treated as "recently used".
    expect(after.id).toBe(before.id)
    expect(after.createdAt).toBe(before.createdAt)
    expect(usePromptHistoryStore.getState().prompts).toHaveLength(2)
  })

  it('removes only the targeted entry — there is no shadow dismissed set', () => {
    addPrompt('keep me', '16')
    addPrompt('remove me', '16')
    const target = usePromptHistoryStore.getState().prompts.find((p) => p.text === 'remove me')!
    removePrompt(target.id)
    const { prompts } = usePromptHistoryStore.getState()
    expect(prompts.map((p) => p.text)).toEqual(['keep me'])
  })

  it('removing an unknown id is a no-op', () => {
    addPrompt('only one', '16')
    removePrompt('no-such-id')
    expect(usePromptHistoryStore.getState().prompts).toHaveLength(1)
  })

  it('clears everything', () => {
    addPrompt('one', '16')
    addPrompt('two', '16')
    clearAll()
    expect(usePromptHistoryStore.getState().prompts).toHaveLength(0)
  })

  // The cap drops the OLDEST, not the alphabetically-last: with an alphabetical list,
  // slicing the tail would throw away the end of the alphabet and keep ancient rows.
  it(`caps at ${MAX_HISTORY}, dropping the OLDEST and keeping the list sorted`, () => {
    for (let i = 0; i < MAX_HISTORY + 5; i++) addPrompt(`prompt ${i}`, '16')
    const { prompts } = usePromptHistoryStore.getState()

    expect(prompts).toHaveLength(MAX_HISTORY)
    // the five oldest are the ones gone
    for (let i = 0; i < 5; i++) {
      expect(prompts.some((p) => p.text === `prompt ${i}`)).toBe(false)
    }
    // and the newest survived
    expect(prompts.some((p) => p.text === `prompt ${MAX_HISTORY + 4}`)).toBe(true)
    // still sorted, without hardcoding which text lands first
    const texts = prompts.map((p) => p.text)
    expect(texts).toEqual([...texts].sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base' })))
  })
})

describe('the pure helpers behind it', () => {
  const entry = (text: string, createdAt = 1): HistoryPrompt => ({
    id: `id-${text}`,
    text,
    sessionId: null,
    createdAt,
  })

  it('matchKey ignores case and collapses whitespace', () => {
    expect(matchKey('  Explain   The  Thing ')).toBe('explain the thing')
    expect(matchKey('explain the thing')).toBe(matchKey('EXPLAIN THE THING'))
  })

  it('matchKey does not merge genuinely different prompts', () => {
    expect(matchKey('explain the conduit')).not.toBe(matchKey('explain the pipeline'))
  })

  it('sortPrompts is alphabetical and leaves the input alone', () => {
    const input = [entry('banana'), entry('Apple'), entry('cherry')]
    expect(sortPrompts(input).map((p) => p.text)).toEqual(['Apple', 'banana', 'cherry'])
    // not in place: the caller's array is not a side effect
    expect(input.map((p) => p.text)).toEqual(['banana', 'Apple', 'cherry'])
  })

  it('dedupePrompts keeps the FIRST occurrence', () => {
    const first = entry('same text', 100)
    const later = entry('same text', 200)
    const out = dedupePrompts([first, later, entry('other')])
    expect(out.map((p) => p.text)).toEqual(['same text', 'other'])
    expect(out[0].createdAt).toBe(100)
  })
})

/**
 * THE REHYDRATE MIGRATION. A list persisted BEFORE dedup/ordering existed still holds
 * its repeats and its newest-first order in sessionStorage. Without the migration the
 * new behaviour would appear not to have taken effect: the user would reload, still
 * see duplicates, and conclude the change did nothing.
 */
describe('the rehydrate migration', () => {
  it('normalises a list persisted before dedup and ordering existed', async () => {
    // version 0 was the old shape: repeats kept, newest-first.
    sessionStorage.setItem(
      'cogitate-prompt-history',
      JSON.stringify({
        state: {
          prompts: [
            { id: 'a', text: 'zebra', sessionId: null, createdAt: 3 },
            { id: 'b', text: 'apple', sessionId: null, createdAt: 2 },
            { id: 'c', text: 'Apple', sessionId: null, createdAt: 1 },
          ],
        },
        version: 0,
      }),
    )

    await usePromptHistoryStore.persist.rehydrate()

    const texts = usePromptHistoryStore.getState().prompts.map((p) => p.text)
    // deduped (first occurrence wins) AND alphabetical
    expect(texts).toEqual(['apple', 'zebra'])
    sessionStorage.removeItem('cogitate-prompt-history')
  })
})
