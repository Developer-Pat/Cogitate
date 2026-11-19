import { act, fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NotificationContainer } from '../NotificationContainer'
import { ttsConfigService } from '@/services/domain/ttsConfigService'
import { ttsService } from '@/services/ttsService'

// THE STORE MOCKS: a mutable notifications array (the container reads
// it on every render — the effect keys on the newest toast's id).
let soundMutedIds: string[] = []
let notifications: Array<{ id: string; type: string; title: string; message?: string; timestamp: number; sticky?: boolean; eventId?: string }> = []

vi.mock('@/stores/notificationStore', () => ({
  useNotificationStore: () => ({
    notifications,
    removeNotification: vi.fn(),
    soundMutedIds,
    toggleToastSound: vi.fn((id: string) => {
      // THE MUTE TOGGLE (the dig fix): the module-level set flips —
      // the rerender re-reads the mock, so the cycle-respect is
      // observable in the test.
      soundMutedIds = soundMutedIds.includes(id)
        ? soundMutedIds.filter((x) => x !== id)
        : [...soundMutedIds, id]
    }),
  }),
}))

// THE DISMISS-TOMBSTONE (2026-08-30, the Exa-diagnosed replay bug):
// the ✕ must tombstone the event key so the SSE ring-replay stays
// silent — the mock records the calls for the assertion.
const tombstoneKey = vi.fn()
vi.mock('@/stores/messageStore', () => ({
  useMessageStore: { getState: () => ({ tombstoneKey }) },
}))

let config: {
  suppressed: boolean
  audio_enabled: boolean
  sound_id: string
  volume: number
  sound_success: string
  sound_warning: string
  sound_error: string
  sound_level: 'info' | 'success' | 'warning' | 'error'
} | null = {
  suppressed: false,
  audio_enabled: true,
  sound_id: 'gentle-ping.wav',
  volume: 1,
  sound_success: 'end-of-run.wav',
  sound_warning: 'alert.wav',
  sound_error: 'emergency.wav',
  sound_level: 'success',
}

vi.mock('@/stores/notificationConfigStore', () => ({
  useNotificationConfigStore: () => ({
    config,
    load: vi.fn(),
    update: vi.fn(),
  }),
}))

// THE AUDIO MOCK: records every constructed element + its play calls.
class MockAudio {
  src: string
  volume = 1
  static instances: MockAudio[] = []
  static plays: string[] = []
  static rejectPlay = false
  constructor(src: string) {
    this.src = src
    MockAudio.instances.push(this)
  }
  play() {
    MockAudio.plays.push(this.src)
    return MockAudio.rejectPlay ? Promise.reject(new Error('NotAllowedError')) : Promise.resolve()
  }
  pause() {}
}
vi.stubGlobal('Audio', MockAudio)

vi.mock('@/services/domain/ttsConfigService', () => ({
  ttsConfigService: { getConfig: vi.fn().mockResolvedValue({ sticky_mode: 'siren', enabled: true }) },
}))
vi.mock('@/services/ttsService', () => ({
  ttsService: { speak: vi.fn() },
}))

const toast = (id: string, type = 'info') => ({ id, type, title: `T${id}`, message: 'm', timestamp: Date.now(), sticky: undefined as boolean | undefined })

describe('the toast audio ping (the wav-assets play hook)', () => {
  beforeEach(() => {
    MockAudio.instances = []
    MockAudio.plays = []
    soundMutedIds = []
    MockAudio.rejectPlay = false
    notifications = []
    config = {
      suppressed: false,
      audio_enabled: true,
      sound_id: 'gentle-ping.wav',
      volume: 1,
      sound_success: 'end-of-run.wav',
      sound_warning: 'alert.wav',
      sound_error: 'emergency.wav',
  sound_level: 'success',
    }
  })

  it('plays the configured sound for each new warning (including the first at mount)', () => {
    const { rerender } = render(<NotificationContainer />)
    expect(MockAudio.plays).toEqual([]) // no toasts -> nothing to ping

    notifications = [toast('a', 'warning')]
    rerender(<NotificationContainer />)
    expect(MockAudio.plays).toHaveLength(1)
    expect(MockAudio.plays[0]).toContain('/sounds/alert.wav')

    notifications = [...notifications, toast('b', 'error')]
    rerender(<NotificationContainer />)
    expect(MockAudio.plays).toHaveLength(2)
    expect(MockAudio.plays[1]).toContain('/sounds/emergency.wav')
  })

  it('stays silent for info — the only quiet class (success pings its own bell now)', () => {
    const { rerender } = render(<NotificationContainer />)
    notifications = [toast('a', 'info')]
    rerender(<NotificationContainer />)
    expect(MockAudio.plays).toEqual([])

    // the SUCCESS class pings the run-complete bell (the F4 design —
    // the run-complete is the success class)
    notifications = [...notifications, toast('b', 'success')]
    rerender(<NotificationContainer />)
    expect(MockAudio.plays).toHaveLength(1)
    expect(MockAudio.plays[0]).toContain('/sounds/end-of-run.wav')
  })

  it('plays the newly selected sound once the config changes', () => {
    const { rerender } = render(<NotificationContainer />)

    notifications = [toast('a', 'warning')]
    rerender(<NotificationContainer />)
    expect(MockAudio.plays[0]).toContain('/sounds/alert.wav')

    notifications = [...notifications, toast('b', 'warning')]
    config = { suppressed: false, audio_enabled: true, sound_id: 'gentle-ping.wav', volume: 1, sound_success: 'end-of-run.wav', sound_warning: 'soft-chime.wav', sound_error: 'emergency.wav', sound_level: 'success' }
    rerender(<NotificationContainer />)

    expect(MockAudio.plays).toHaveLength(2)
    expect(MockAudio.plays[1]).toContain('/sounds/soft-chime.wav')
  })

  it('applies the configured volume to the played sound', () => {
    config = { suppressed: false, audio_enabled: true, sound_id: 'gentle-ping.wav', volume: 0.35, sound_success: 'end-of-run.wav', sound_warning: 'alert.wav', sound_error: 'emergency.wav', sound_level: 'success' }
    notifications = [toast('a', 'warning')]
    const { rerender } = render(<NotificationContainer />)
    expect(MockAudio.instances[0].volume).toBe(0.35)
    rerender(<NotificationContainer />)
  })

  it('cycles the sound every 2s while a sticky toast is present (the repeat)', () => {
    vi.useFakeTimers()
    config = { suppressed: false, audio_enabled: true, sound_id: 'gentle-ping.wav', volume: 1, sound_success: 'end-of-run.wav', sound_warning: 'emergency.wav', sound_error: 'emergency.wav', sound_level: 'success' }
    notifications = [toast('a', 'warning')]
    notifications[0].sticky = true
    const { rerender } = render(<NotificationContainer />)

    expect(MockAudio.plays).toHaveLength(1) // the first play at mount
    vi.advanceTimersByTime(2000)
    expect(MockAudio.plays).toHaveLength(2)
    vi.advanceTimersByTime(4000)
    expect(MockAudio.plays).toHaveLength(4)
    expect(MockAudio.plays.every((src) => src.includes('/sounds/emergency.wav'))).toBe(true)

    // the dismissal (the toast removed) stops the cycle
    notifications = []
    rerender(<NotificationContainer />)
    const count = MockAudio.plays.length
    vi.advanceTimersByTime(6000)
    expect(MockAudio.plays).toHaveLength(count)
    vi.useRealTimers()
  })

  it('does not repeat for the non-sticky toasts (one play only)', () => {
    vi.useFakeTimers()
    notifications = [toast('a', 'warning')]
    render(<NotificationContainer />)
    expect(MockAudio.plays).toHaveLength(1)

    vi.advanceTimersByTime(6000)
    expect(MockAudio.plays).toHaveLength(1)
    vi.useRealTimers()
  })

  it('surfaces the sound-blocked banner when the play is rejected + unlocks on the click', async () => {
    MockAudio.rejectPlay = true
    notifications = [toast('a', 'warning')]
    render(<NotificationContainer />)
    await act(async () => {}) // flush the rejection microtask

    expect(screen.getByText(/browser blocked the sound/)).toBeTruthy()

    // the click = the gesture — the next play succeeds + the banner clears
    MockAudio.rejectPlay = false
    fireEvent.click(screen.getByText(/browser blocked the sound/))
    await act(async () => {})
    expect(screen.queryByText(/browser blocked the sound/)).toBeNull()
  })

  it('plays the CLASS sound — success -> the bell, warning -> the alert, error -> the siren', () => {
    // warning -> sound_warning (the alert)
    notifications = [toast('w', 'warning')]
    const { rerender } = render(<NotificationContainer />)
    expect(MockAudio.plays.slice(-1)[0]).toContain('/sounds/alert.wav')

    // success -> sound_success (the bell) — a success toast pings now
    notifications = [toast('s', 'success')]
    rerender(<NotificationContainer />)
    expect(MockAudio.plays.slice(-1)[0]).toContain('/sounds/end-of-run.wav')

    // error -> sound_error (the siren)
    notifications = [toast('e', 'error')]
    rerender(<NotificationContainer />)
    expect(MockAudio.plays.slice(-1)[0]).toContain('/sounds/emergency.wav')

    // the class fields override the plain sound_id
    expect(MockAudio.plays.every((src) => !src.includes('/sounds/gentle-ping.wav'))).toBe(true)
  })

  it('treats the empty class field as the per-class silent (the none)', () => {
    // THE PER-CLASS NONE (2026-08-31, the user's null-wav ask):
    // the configured EMPTY string means that class stays SILENT —
    // the container skips the play entirely (no fallback).
    config = {
      suppressed: false,
      audio_enabled: true,
      sound_id: 'soft-chime.wav',
      volume: 1,
      sound_success: '',
      sound_warning: '',
      sound_error: '',
      sound_level: 'success',
    }
    notifications = [toast('w2', 'warning')]
    render(<NotificationContainer />)
    expect(MockAudio.plays).toHaveLength(0)
  })

  it('stays silent when audio is disabled', () => {
    config = { suppressed: false, audio_enabled: false, sound_id: 'gentle-ping.wav', volume: 1, sound_success: 'end-of-run.wav', sound_warning: 'alert.wav', sound_error: 'emergency.wav', sound_level: 'success' }
    notifications = [toast('a', 'warning')]
    const { rerender } = render(<NotificationContainer />)

    notifications = [...notifications, toast('b', 'warning')]
    rerender(<NotificationContainer />)

    expect(MockAudio.plays).toEqual([])
  })

  it('plays once per toast id (no repeats on re-renders)', () => {
    notifications = [toast('a', 'warning'), toast('b', 'warning')]
    const { rerender } = render(<NotificationContainer />)
    rerender(<NotificationContainer />)
    rerender(<NotificationContainer />)

    expect(MockAudio.plays).toHaveLength(1)
  })

  // THE REPLAY-AFTER-DISMISS FIX (2026-08-30, the Exa-diagnosed
  // bug): the ✕ must tombstone the event key — the bridge's
  // replay-check suppresses the sticky re-toast only when the
  // tombstone exists. The toast ✕ used to leave it empty, so the
  // next SSE ring-replay resurrected the sticky + the sound loop.
  it('tombstones the event key on dismiss', () => {
    tombstoneKey.mockClear()
    notifications = [
      { id: 's1', type: 'warning', title: 'Sticky alert', message: 'The payload', timestamp: 1, sticky: true, eventId: 'evt-42' },
    ]
    render(<NotificationContainer />)

    const close = screen.getByLabelText('Dismiss notification')
    act(() => {
      fireEvent.click(close)
    })

    expect(tombstoneKey).toHaveBeenCalledWith('evt:evt-42')
  })
  it('the sticky sound-MUTE stops the 2s cycle without dismissing (the dig fix)', () => {
    vi.useFakeTimers()
    notifications = [{ ...toast('st', 'error'), sticky: true }]
    const { rerender } = render(<NotificationContainer />)
    const before = MockAudio.plays.length
    expect(before).toBeGreaterThan(0) // the sticky plays at mount

    fireEvent.click(screen.getByLabelText('Mute the toast sound'))
    rerender(<NotificationContainer />)
    const muted = MockAudio.plays.length
    vi.advanceTimersByTime(6000)
    expect(MockAudio.plays.length).toBe(muted) // the cycle stopped

    // the toast STAYS (the mute is not the dismiss)
    expect(screen.getByText(/Tst/)).toBeTruthy()
    expect(screen.queryByLabelText('Mute the toast sound')).toBeNull()
    expect(screen.getByLabelText('Unmute the toast sound')).toBeTruthy()

    // the unmute resumes the cycle
    fireEvent.click(screen.getByLabelText('Unmute the toast sound'))
    rerender(<NotificationContainer />)
    vi.advanceTimersByTime(2200)
    expect(MockAudio.plays.length).toBeGreaterThan(muted)
    vi.useRealTimers()
  })

  it("the SPOKEN mode reads the sticky's content once, no wav-loop (the TTS P3)", async () => {
    vi.useFakeTimers()
    vi.mocked(ttsConfigService.getConfig).mockResolvedValue({ provider: 'piper', voice: 'x', rate: 1, source: 'piper', sticky_mode: 'spoken', enabled: true })
    notifications = [{ ...toast('sp', 'error'), sticky: true, message: 'the aborted run' }]
    render(<NotificationContainer />)
    await act(async () => {})

    expect(ttsService.speak).toHaveBeenCalledWith(expect.stringContaining('Tsp'))
    expect(ttsService.speak).toHaveBeenCalledWith(expect.stringContaining('the aborted run'))
    // no siren-LOOP in the spoken mode: the settle (the first render
    // plays once before the mode-fetch lands), then the idle window
    // must stay silent.
    MockAudio.plays.length = 0
    vi.advanceTimersByTime(6000)
    expect(MockAudio.plays).toHaveLength(0)
    vi.useRealTimers()
  })

})
