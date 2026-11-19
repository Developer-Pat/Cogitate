import { beforeEach, describe, expect, it } from 'vitest'
import { outageGate } from '../outageGate'

// THE OUTAGE EPISODE GATE (2026-09-04, the dedupe refinement): one
// announcement per direction per episode, whichever notifier
// detects first — the apiClient gate, the BackendStatusIndicator,
// and the useSystemHealth hook all consult it.
describe('the outageGate episode semantics', () => {
  beforeEach(() => outageGate.reset())

  it('the FIRST down-detector announces; the second stays silent', () => {
    expect(outageGate.markDown()).toBe(true) // e.g. the indicator
    expect(outageGate.markDown()).toBe(false) // e.g. the apiClient gate
    expect(outageGate.markDown()).toBe(false) // e.g. the health hook
  })

  it('the first recovery-detector announces + closes the episode', () => {
    outageGate.markDown()
    expect(outageGate.markUp()).toBe(true)
    expect(outageGate.markUp()).toBe(false) // the second recovery stays silent
  })

  it('a NEW outage after a recovery announces again', () => {
    outageGate.markDown()
    outageGate.markUp()
    expect(outageGate.markDown()).toBe(true) // episode 2
    expect(outageGate.markDown()).toBe(false)
  })

  it('a recovery with NO down announcement stays silent (a stale notifier)', () => {
    expect(outageGate.markUp()).toBe(false)
    expect(outageGate.markUp()).toBe(false)
  })

  it('rapid down/up flaps stay one announcement each (no storms)', () => {
    expect(outageGate.markDown()).toBe(true)
    expect(outageGate.markUp()).toBe(true)
    expect(outageGate.markDown()).toBe(true)
    expect(outageGate.markUp()).toBe(true)
  })
})
