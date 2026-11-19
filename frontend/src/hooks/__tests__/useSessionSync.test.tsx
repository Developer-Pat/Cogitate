import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { eventBus } from '@/services/eventBus'
import { useSessionSync, SESSION_SYNC_TOPICS } from '../useSessionSync'
import { useCognitiveHubStore } from '@/stores/cognitiveHubStore'

// The feed's network layer is mocked — the union registry is tested for real.
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

const loadMock = vi.hoisted(() => vi.fn().mockResolvedValue(undefined))

vi.mock('@/services/domain/SessionsService', () => ({
  sessionsService: { loadFromBackend: loadMock },
}))

describe('useSessionSync (the cross-window session sync)', () => {
  beforeEach(() => {
    eventBus.clear()
    vi.clearAllMocks()
  })

  afterEach(() => {
    eventBus.clear()
  })

  it('registers the session topics (the union registry)', () => {
    renderHook(() => useSessionSync(true))
    expect(SESSION_SYNC_TOPICS).toBe('session:*')
    expect(feedMocks.connect).toHaveBeenCalledWith('session:*')
  })

  it('removes the session on the deleted event', () => {
    renderHook(() => useSessionSync(true))
    const remove = vi.spyOn(useCognitiveHubStore.getState(), 'removeSession')

    act(() => {
      eventBus.emit('session:99:deleted', { session_id: 99, event: 'deleted' })
    })

    expect(remove).toHaveBeenCalledWith('99')
  })

  it('applies the renamed title on the updated event', () => {
    renderHook(() => useSessionSync(true))
    const rename = vi.spyOn(useCognitiveHubStore.getState(), 'renameSessionById')

    act(() => {
      eventBus.emit('session:99:updated', { session_id: 99, title: 'Renamed elsewhere', event: 'updated' })
    })

    expect(rename).toHaveBeenCalledWith('99', 'Renamed elsewhere')
  })

  it('reloads the list on the BULK wipe event — which carries no session id', () => {
    renderHook(() => useSessionSync(true))

    act(() => {
      // the payload a Clear All in another window publishes: no session_id
      eventBus.emit('session:all:cleared', { event: 'cleared', scope: 'all', count: 7 })
    })

    // The id guard must not swallow it: the whole list changed.
    expect(loadMock).toHaveBeenCalledWith(false)
  })

  it('reloads the list on the bulk delete-all event too', () => {
    renderHook(() => useSessionSync(true))

    act(() => {
      eventBus.emit('session:all:deleted_all', { event: 'deleted_all', scope: 'all', count: 3 })
    })

    expect(loadMock).toHaveBeenCalledWith(false)
  })

  it('ignores an event with neither an id nor a bulk scope', () => {
    renderHook(() => useSessionSync(true))

    act(() => {
      eventBus.emit('session:x:updated', { event: 'updated' })
    })

    expect(loadMock).not.toHaveBeenCalled()
  })

  it('cleans up on unmount (the MVVM rule)', () => {
    const { unmount } = renderHook(() => useSessionSync(true))
    unmount()
    expect(feedMocks.disconnect).toHaveBeenCalledWith('session:*')
  })
})
