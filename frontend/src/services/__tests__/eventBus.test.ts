import { describe, it, expect, vi, beforeEach } from 'vitest'
import { eventBus } from '../eventBus'

describe('eventBus (the frontend EventAggregator)', () => {
  beforeEach(() => {
    eventBus.clear()
  })

  it('delivers exact-channel events', () => {
    const handler = vi.fn()
    eventBus.subscribe('workflow:1:started', handler)
    eventBus.emit('workflow:1:started', { id: 1 })
    expect(handler).toHaveBeenCalledWith({ id: 1 })
  })

  it('matches wildcard channels', () => {
    const handler = vi.fn()
    eventBus.subscribe('batch:*', handler)
    eventBus.emit('batch:1:done', { rows: 12 })
    eventBus.emit('batch:2:done', { rows: 11 })
    expect(handler).toHaveBeenCalledTimes(2)
  })

  it('does not deliver non-matching topics', () => {
    const handler = vi.fn()
    eventBus.subscribe('workflow:*', handler)
    eventBus.emit('notify:test', {})
    expect(handler).not.toHaveBeenCalled()
  })

  it('unsubscribe stops delivery', () => {
    const handler = vi.fn()
    const unsub = eventBus.subscribe('notify:*', handler)
    eventBus.emit('notify:x', {})
    unsub()
    eventBus.emit('notify:x', {})
    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('isolates a throwing handler (the bus rule)', () => {
    const bad = vi.fn(() => {
      throw new Error('boom')
    })
    const good = vi.fn()
    eventBus.subscribe('system:*', bad)
    eventBus.subscribe('system:*', good)
    expect(() => eventBus.emit('system:ready', {})).not.toThrow()
    expect(good).toHaveBeenCalled()
  })

  it('clear removes everything', () => {
    const handler = vi.fn()
    eventBus.subscribe('workflow:*', handler)
    eventBus.clear()
    eventBus.emit('workflow:1:started', {})
    expect(handler).not.toHaveBeenCalled()
  })
})
