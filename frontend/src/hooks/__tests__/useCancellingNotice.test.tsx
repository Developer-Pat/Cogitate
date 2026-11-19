import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { eventBus } from '@/services/eventBus'
import { useNotificationStore } from '@/stores/notificationStore'
import { useCancellingNotice, CANCELLING_TOPICS } from '../useCancellingNotice'

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

describe('useCancellingNotice (the orderly-shutdown notice)', () => {
  beforeEach(() => {
    eventBus.clear()
    useNotificationStore.setState({ notifications: [] })
    vi.clearAllMocks()
  })

  afterEach(() => {
    eventBus.clear()
    useNotificationStore.setState({ notifications: [] })
  })

  it('registers the workflow topics', () => {
    renderHook(() => useCancellingNotice(true))
    expect(CANCELLING_TOPICS).toBe('workflow:*')
    expect(feedMocks.add).toHaveBeenCalledWith('workflow:*')
  })

  it('shows the graceful-shutdown toast on a cancelling event', () => {
    renderHook(() => useCancellingNotice(true))

    act(() => {
      eventBus.emit('workflow:wf-1:cancelling', { workflow_id: 'wf-1', reason: 'user', kind: 'cancelling' })
    })

    const notifs = useNotificationStore.getState().notifications
    expect(notifs).toHaveLength(1)
    expect(notifs[0].title).toBe('Shutting down gracefully…')
    expect(notifs[0].message).toContain('wf-1')
  })

  it('ignores the non-cancelling workflow events (started/completed)', () => {
    renderHook(() => useCancellingNotice(true))

    act(() => {
      eventBus.emit('workflow:wf-1:started', { workflow_id: 'wf-1' })
    })
    expect(useNotificationStore.getState().notifications).toHaveLength(0)
  })

  it('unregisters on unmount (the cleanup rule)', () => {
    const { unmount } = renderHook(() => useCancellingNotice(true))
    unmount()
    expect(feedMocks.remove).toHaveBeenCalledWith('workflow:*')
  })
})
