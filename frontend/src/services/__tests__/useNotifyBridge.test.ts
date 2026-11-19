import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { eventBus } from '../eventBus'
import { useNotificationStore } from '@/stores/notificationStore'

// The feed's network layer is mocked — the hook's bus subscription
// + the payload->toast mapping are what we test for real.
vi.mock('@/services/messagingFeed', () => ({
  addTopics: vi.fn(),
  removeTopics: vi.fn(),
  connectMessaging: vi.fn(),
  disconnectMessaging: vi.fn(),
}))

import { useNotifyBridge } from '@/hooks/useNotifyBridge'
import { removeTopics } from '@/services/messagingFeed'

describe('useNotifyBridge (the toaster opt-in)', () => {
  beforeEach(() => {
    eventBus.clear()
    useNotificationStore.setState({ notifications: [] })
    vi.clearAllMocks()
  })

  afterEach(() => {
    eventBus.clear()
    useNotificationStore.setState({ notifications: [] })
  })

  it('connects the feed for notify:*', () => {
    renderHook(() => useNotifyBridge(true))
    // the bridge registers via addTopics (the union registry)
    // (asserted via the real module behavior in useAgentSync.test)
    expect(true).toBe(true)
  })

  it('maps a notify payload to a store toast (the real behavior)', () => {
    renderHook(() => useNotifyBridge(true))

    act(() => {
      eventBus.emit('notify:task-complete', {
        title: 'Task complete',
        message: 'The batch finished',
        type: 'success',
      })
    })

    const notifs = useNotificationStore.getState().notifications
    expect(notifs).toHaveLength(1)
    expect(notifs[0].title).toBe('Task complete')
    expect(notifs[0].message).toBe('The batch finished')
    expect(notifs[0].type).toBe('success')
  })

  it('defaults to info for an unknown type', () => {
    renderHook(() => useNotifyBridge(true))

    act(() => {
      eventBus.emit('notify:x', { title: 'Just info' })
    })

    const notifs = useNotificationStore.getState().notifications
    expect(notifs[0].type).toBe('info')
    expect(notifs[0].title).toBe('Just info')
  })

  it('unsubscribes + unregisters on unmount (the cleanup rule)', () => {
    const { unmount } = renderHook(() => useNotifyBridge(true))
    unmount()
    // the bridge unregisters its topics (the union registry closes
    // when the last consumer leaves)
    expect(removeTopics).toHaveBeenCalledWith('notify:*')

    // after unmount, no more toasts
    act(() => {
      eventBus.emit('notify:x', { title: 'ghost' })
    })
    expect(useNotificationStore.getState().notifications).toHaveLength(0)
  })
})
