import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { eventBus } from '@/services/eventBus'
import { useTracePanel, TRACE_TOPICS } from '../useTracePanel'

const feedMocks = vi.hoisted(() => ({
  add: vi.fn(),
  remove: vi.fn(),
}))
vi.mock('@/services/messagingFeed', () => ({
  addTopics: (t: string) => feedMocks.add(t),
  removeTopics: (t: string) => feedMocks.remove(t),
  connectMessaging: vi.fn(),
  disconnectMessaging: vi.fn(),
}))

describe('useTracePanel (the UI pump for the cognitive trace)', () => {
  beforeEach(() => {
    eventBus.clear()
    vi.clearAllMocks()
  })

  afterEach(() => {
    eventBus.clear()
  })

  it('registers the chat topics with the feed', () => {
    renderHook(() => useTracePanel('sess-1'))
    expect(feedMocks.add).toHaveBeenCalledWith(TRACE_TOPICS)
    expect(TRACE_TOPICS).toBe('chat:*')
  })

  it('maps the trace events to the cognitive state', () => {
    const { result } = renderHook(() => useTracePanel('sess-1'))

    act(() => {
      eventBus.emit('chat:sess-1:executor_started', {
        kind: 'executor_started', component: 'executor', strategy: 'hybrid',
      })
    })
    expect(result.current.isActive).toBe(true)
    expect(result.current.executorStage).toBe('running')
    expect(result.current.events).toHaveLength(1)
    expect(result.current.events[0].type).toBe('cognitive_executor_started')

    act(() => {
      eventBus.emit('chat:sess-1:trace_complete', {
        kind: 'trace_complete', component: 'executor',
        trace: {
          executor: { strategy: 'hybrid' },
          total_duration_ms: 1234,
          total_tokens: 56,
        },
        metrics: { total_duration_ms: 1234 },
        memory_delta: null,
      })
    })
    expect(result.current.isActive).toBe(false)
    expect(result.current.executorStage).toBe('completed')
    // THE LIVE-TEST FIX (the TypeError catch): latestTrace is the
    // WHOLE payload — the indicator reads
    // latestTrace.trace.total_duration_ms. Storing the inner dict
    // made latestTrace.trace undefined.
    expect(result.current.latestTrace).not.toBeNull()
    expect((result.current.latestTrace as { trace: { total_duration_ms: number } }).trace.total_duration_ms).toBe(1234)
  })

  it('ignores events without the kind discriminator', () => {
    const { result } = renderHook(() => useTracePanel('sess-1'))
    act(() => {
      eventBus.emit('chat:sess-1:executor_started', { component: 'executor' })
    })
    expect(result.current.events).toHaveLength(0)
  })

  it('unregisters on unmount', () => {
    const { unmount } = renderHook(() => useTracePanel('sess-1'))
    unmount()
    expect(feedMocks.remove).toHaveBeenCalledWith(TRACE_TOPICS)
  })

  it('RESETS the pump when the session changes (no carry-over of the busy state)', () => {
    const { result, rerender } = renderHook(({ sid }) => useTracePanel(sid), {
      initialProps: { sid: 'sess-1' },
    })

    act(() => {
      eventBus.emit('chat:sess-1:executor_started', {
        kind: 'executor_started', component: 'executor', strategy: 'hybrid',
      })
    })
    expect(result.current.isActive).toBe(true)
    expect(result.current.events).toHaveLength(1)

    // THE BUG (2026-09-02, the user's "it is still running"): switching
    // sessions carried the old session's busy state into the new view.
    rerender({ sid: 'sess-2' })
    expect(result.current.isActive).toBe(false)
    expect(result.current.executorStage).toBe('idle')
    expect(result.current.events).toHaveLength(0)
    expect(result.current.latestTrace).toBeNull()
  })
})
