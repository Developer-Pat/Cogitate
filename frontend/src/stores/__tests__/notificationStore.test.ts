import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useNotificationStore } from '../notificationStore'
import { useMessageStore } from '../messageStore'
import { useNotificationConfigStore } from '../notificationConfigStore'

// THE AIRPLANE-MODE GATE (2026-08-29, the notifications-upgrade):
// the suppressed config mutes the TOAST display — the message
// center + the cross-tab broadcast continue (the viewable-queue
// doctrine). The bypass flag rides the flip-announcements.

const baseConfig: import('@/services/domain/notificationConfigService').NotificationConfig = {
  suppressed: false,
  audio_enabled: true,
  sound_id: 'gentle-ping.wav',
  mute_until: null as number | null,
  volume: 1,
  sound_success: 'end-of-run.wav',
  sound_warning: 'alert.wav',
  sound_error: 'emergency.wav',
  sound_level: 'success',
}

describe('the notificationStore airplane-mode gate', () => {
  beforeEach(() => {
    useNotificationStore.setState({ notifications: [] })
    useMessageStore.setState({ messages: [], tombstones: [] })
  })

  it('records to the center while suppressed (the toast is muted)', () => {
    useNotificationConfigStore.setState({ config: { ...baseConfig, suppressed: true }, loaded: true })
    useNotificationStore.getState().addWarning('Sweep', '2 findings')

    expect(useNotificationStore.getState().notifications).toHaveLength(0)
    const center = useMessageStore.getState().messages
    expect(center.some((m) => m.title === 'Sweep')).toBe(true)
  })

  it('shows the toast when not suppressed', () => {
    useNotificationConfigStore.setState({ config: { ...baseConfig, suppressed: false }, loaded: true })
    useNotificationStore.getState().addWarning('Sweep', '2 findings')

    expect(useNotificationStore.getState().notifications).toHaveLength(1)
  })

  it('shows the bypass announcement even while suppressed (the restore toast)', () => {
    useNotificationConfigStore.setState({ config: { ...baseConfig, suppressed: true }, loaded: true })
    useNotificationStore.getState().addNotification({
      type: 'info',
      title: 'Notifications back on',
      message: 'Muted notifications are enabled again.',
      source: 'system',
      bypassSuppression: true,
    })

    const toasts = useNotificationStore.getState().notifications
    expect(toasts).toHaveLength(1)
    expect(toasts[0].title).toBe('Notifications back on')
  })
})


describe('the sticky toasts', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    useNotificationStore.setState({ notifications: [] })
    useMessageStore.setState({ messages: [], tombstones: [] })
    useNotificationConfigStore.setState({ config: { ...baseConfig, suppressed: false }, loaded: true })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('stays until dismissed — the duration does NOT auto-remove it', () => {
    useNotificationStore.getState().addNotification({
      type: 'warning',
      title: 'Workflow aborted',
      message: 'the run failed',
      sticky: true,
      duration: 5000,
    })
    expect(useNotificationStore.getState().notifications).toHaveLength(1)

    vi.advanceTimersByTime(7000)
    expect(useNotificationStore.getState().notifications).toHaveLength(1)

    useNotificationStore.getState().removeNotification(useNotificationStore.getState().notifications[0].id)
    expect(useNotificationStore.getState().notifications).toHaveLength(0)
  })

  it('the regular toast still auto-removes after its duration', () => {
    useNotificationStore.getState().addWarning('Sweep', '2 findings', 3000)
    vi.advanceTimersByTime(4000)
    expect(useNotificationStore.getState().notifications).toHaveLength(0)
  })
  it('records the REPEAT firings too (the dedupe removed — the Bob-errors dig)', () => {
    const store = useNotificationStore.getState()
    store.addNotification({ type: 'warning', title: 'Bob fell back', message: 'the primary failed' })
    store.addNotification({ type: 'warning', title: 'Bob fell back', message: 'the primary failed' })
    const all = useNotificationStore.getState().notifications
    expect(all.filter((n) => n.title === 'Bob fell back')).toHaveLength(2)
  })

})
