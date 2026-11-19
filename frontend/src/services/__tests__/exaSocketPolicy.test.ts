/**
 * The Exa socket policy — the rule that stopped the "Exa is not active" toast
 * loop (2026-11-19): an inactive answer is terminal for the socket, and only a
 * `ready` answer may reset the backoff.
 */

import { describe, it, expect } from 'vitest'
import { backoffDelay, shouldReconnectOnClose } from '../exaSocketPolicy'

describe('shouldReconnectOnClose', () => {
  it('reconnects a socket that died while Exa was active', () => {
    expect(shouldReconnectOnClose({ disposed: false, inactive: false })).toBe(true)
  })

  it('does NOT reconnect after an inactive answer — the gate will refuse again', () => {
    expect(shouldReconnectOnClose({ disposed: false, inactive: true })).toBe(false)
  })

  it('does not reconnect a disposed surface', () => {
    expect(shouldReconnectOnClose({ disposed: true, inactive: false })).toBe(false)
    expect(shouldReconnectOnClose({ disposed: true, inactive: true })).toBe(false)
  })
})

describe('backoffDelay', () => {
  it('grows 1s, 2s, 4s…', () => {
    expect(backoffDelay(0)).toBe(1000)
    expect(backoffDelay(1)).toBe(2000)
    expect(backoffDelay(3)).toBe(8000)
  })

  it('caps at the caller’s ceiling', () => {
    expect(backoffDelay(10)).toBe(30000)
    expect(backoffDelay(10, 15000)).toBe(15000)
  })
})
