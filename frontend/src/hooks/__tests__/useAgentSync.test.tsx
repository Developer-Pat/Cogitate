import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { eventBus } from '@/services/eventBus'
import { useAgentSync, SYNC_TOPICS } from '../useAgentSync'

// The feed's network layer is mocked — the union registry + the
// invalidation behavior are tested for real.
const feedMocks = vi.hoisted(() => ({
  connect: vi.fn(),
  disconnect: vi.fn(),
}))
vi.mock('@/services/messagingFeed', () => ({
  addTopics: (t: string) => feedMocks.connect(t),
  removeTopics: (t: string) => feedMocks.disconnect(t),
  disconnectMessaging: vi.fn(),
  connectMessaging: vi.fn(),
}))

function makeWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
  return { wrapper, invalidateSpy }
}

describe('useAgentSync (the cross-window sync)', () => {
  beforeEach(() => {
    eventBus.clear()
    vi.clearAllMocks()
  })

  afterEach(() => {
    eventBus.clear()
  })

  it('registers the agent topics (the union registry)', () => {
    renderHook(() => useAgentSync(true), { wrapper: makeWrapper().wrapper })
    expect(SYNC_TOPICS).toBe('agent:*')
    expect(feedMocks.connect).toHaveBeenCalledWith('agent:*')
  })

  it('invalidates the agent queries on the updated event — the CROSS-WINDOW refresh', () => {
    const { wrapper, invalidateSpy } = makeWrapper()
    renderHook(() => useAgentSync(true), { wrapper })

    act(() => {
      eventBus.emit('agent:5:updated', { agent_id: 5 })
    })

    // the three keys every open page uses must be invalidated
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['agents'] })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['agent', 5] })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['agent-metrics', 5] })
  })

  it('ignores the events without an agent_id', () => {
    const { wrapper, invalidateSpy } = makeWrapper()
    renderHook(() => useAgentSync(true), { wrapper })

    act(() => {
      eventBus.emit('agent:x:updated', {})
    })

    expect(invalidateSpy).not.toHaveBeenCalled()
  })

  it('cleans up on unmount (the MVVM rule)', () => {
    const { wrapper } = makeWrapper()
    const { unmount } = renderHook(() => useAgentSync(true), { wrapper })
    unmount()
    expect(feedMocks.disconnect).toHaveBeenCalledWith('agent:*')
  })
})
