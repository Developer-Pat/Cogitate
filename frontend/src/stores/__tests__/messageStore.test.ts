import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useNotificationStore } from '../notificationStore'
import { useMessageStore } from '../messageStore'

describe('the message-center choke point (2026-08-25)', () => {
  beforeEach(() => {
    useMessageStore.getState().clearAll()
    useNotificationStore.getState().clearNotifications()
  })

  it('the frontend-local error toast lands in the message store', () => {
    // the user's report: the local errors never reached the center
    useNotificationStore.getState().addError('Backend Unavailable', 'Cannot connect', 0, undefined, 'app')
    const msgs = useMessageStore.getState().messages
    expect(msgs.length).toBe(1)
    expect(msgs[0].title).toBe('Backend Unavailable')
    expect(msgs[0].source).toBe('app')
    expect(msgs[0].type).toBe('error')
    expect(msgs[0].read).toBe(false)
  })

  it('the exa-source passes through the adder', () => {
    useNotificationStore.getState().addWarning('Exa: queue cleared', '1 needs attention', 0, undefined, 'exa')
    const msgs = useMessageStore.getState().messages
    expect(msgs[0].source).toBe('exa')
    expect(msgs[0].type).toBe('warning')
  })
  it('records the REPEAT messages too (the center-dedupe removed — the Bob-errors dig)', () => {
    const store = useMessageStore.getState()
    const m = { kind: 'app-notify' as const, type: 'warning' as const, source: 'app', title: 'Bob failed', message: 'the primary failed' }
    store.addMessage({ ...m })
    store.addMessage({ ...m })
    const all = useMessageStore.getState().messages.filter((x) => x.title === 'Bob failed')
    expect(all).toHaveLength(2)
  })

})

describe('the tombstone TTL (2026-09-05 — the deleted-forever eater)', () => {
  beforeEach(() => {
    // a REAL reset — clearAll only ADDS tombstones; the suites must
    // not leak keys (and their fresh timestamps) across tests
    useMessageStore.setState({ messages: [], tombstones: [], tombstoneTimestamps: {} })
  })

  const msg = { kind: 'app-notify' as const, type: 'error' as const, source: 'app', title: 'Backend Unavailable', message: 'Cannot connect to backend server. Some features may not work.' }

  it('a FRESH tombstone still suppresses the same content (the reload-replay purpose holds)', () => {
    const store = useMessageStore.getState()
    store.addMessage({ ...msg })
    const first = useMessageStore.getState().messages[0]
    useMessageStore.getState().deleteMessages([first.id])
    // deleted now — the same content stays gone while fresh
    useMessageStore.getState().addMessage({ ...msg })
    expect(useMessageStore.getState().messages).toHaveLength(0)
  })

  it('an EXPIRED tombstone lets the same content record again + prunes', () => {
    vi.useFakeTimers()
    try {
      const store = useMessageStore.getState()
      store.addMessage({ ...msg })
      const first = useMessageStore.getState().messages[0]
      useMessageStore.getState().deleteMessages([first.id])
      // an hour later — the SAME content is a genuinely new event
      vi.setSystemTime(Date.now() + 61 * 60 * 1000)
      useMessageStore.getState().addMessage({ ...msg })
      const state = useMessageStore.getState()
      expect(state.messages).toHaveLength(1)
      expect(state.messages[0].title).toBe('Backend Unavailable')
      // the tombstone pruned — the next add is unhindered too
      expect(state.tombstones.some((k) => k.includes('Backend Unavailable'))).toBe(false)
    } finally {
      vi.useRealTimers()
    }
  })

  it('the MIGRATION: a pre-TTL tombstone (no timestamp) counts as expired', () => {
    const state = useMessageStore.getState()
    // simulate the old store's leftovers: a key without a timestamp
    const staleKey = state._key(msg)
    useMessageStore.setState({
      messages: [],
      tombstones: [...state.tombstones, staleKey],
      tombstoneTimestamps: state.tombstoneTimestamps, // no entry for staleKey
    })
    useMessageStore.getState().addMessage({ ...msg })
    const after = useMessageStore.getState()
    expect(after.messages).toHaveLength(1)
    expect(after.tombstones.includes(staleKey)).toBe(false)
  })
})

describe('the messageStore eventId dedupe (the cross-tab triples, 2026-09-05)', () => {
  const dedupeMsg = {
    kind: 'app-notify' as const,
    type: 'warning' as const,
    source: 'app' as const,
    title: 'Triple test',
    message: 'the same event via every path',
  }

  beforeEach(() => {
    // FULL reset — the tombstones must not leak between the tests
    useMessageStore.setState({
      messages: [],
      tombstones: [],
      tombstoneTimestamps: {},
    })
  })

  it('the SAME bus event (same eventId) records ONCE — the bridge + the cross-tab sync both deliver it', () => {
    const st = useMessageStore.getState()
    st.addMessage({ ...dedupeMsg, eventId: 'e1' }) // the local bridge delivery
    st.addMessage({ ...dedupeMsg, eventId: 'e1' }) // the synced copy from tab B
    st.addMessage({ ...dedupeMsg, eventId: 'e1' }) // the synced copy from tab C
    expect(useMessageStore.getState().messages).toHaveLength(1)
  })

  it('a NEW event with the same content still records (the center is the record)', () => {
    const st = useMessageStore.getState()
    st.addMessage({ ...dedupeMsg, eventId: 'e1' })
    st.addMessage({ ...dedupeMsg, eventId: 'e2' }) // a genuinely new firing
    expect(useMessageStore.getState().messages).toHaveLength(2)
  })

  it('the no-eventId locals (the Bob-errors doctrine) ALWAYS land — repeats included', () => {
    const st = useMessageStore.getState()
    st.addMessage({ ...dedupeMsg }) // a local error without a bus event
    st.addMessage({ ...dedupeMsg }) // its repeat firing — must record too
    expect(useMessageStore.getState().messages).toHaveLength(2)
  })
})

describe('the cross-tab sync (2026-09-26 — the standing badge/center disagreement)', () => {
  const foreign = (title: string) => ({
    state: {
      messages: [
        { id: 'other-tab-1', kind: 'bus-notify', source: 'exa', type: 'info',
          title, message: 'written in the other tab', timestamp: 1, read: false },
      ],
      tombstones: [],
      tombstoneTimestamps: {},
    },
    version: 0,
  })

  it("adopts another tab's queue when its write announces itself", async () => {
    // the other tab's write = the value in localStorage, then the event
    const payload = JSON.stringify(foreign('from the other tab'))
    localStorage.setItem('cogitate-messages', payload)
    window.dispatchEvent(new StorageEvent('storage', { key: 'cogitate-messages', newValue: payload }))
    await new Promise((r) => setTimeout(r, 0))

    expect(useMessageStore.getState().messages.some((m) => m.title === 'from the other tab')).toBe(true)
  })

  it('ignores a write to some other key', async () => {
    const payload = JSON.stringify(foreign('should never arrive'))
    window.dispatchEvent(new StorageEvent('storage', { key: 'some-other-store', newValue: payload }))
    await new Promise((r) => setTimeout(r, 0))

    expect(useMessageStore.getState().messages.some((m) => m.title === 'should never arrive')).toBe(false)
  })
})
