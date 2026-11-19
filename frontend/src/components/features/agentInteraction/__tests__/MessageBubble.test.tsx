/**
 * MessageBubble — the speak cluster's OWNERSHIP rule.
 *
 * The bug this pins (the D1 settlement, Phase C of the streaming-perf arc):
 * ttsService.activeKey is not React state, so a memo cannot see it change.
 * Switching the voice to another bubble WHILE one is playing changes activeKey
 * but leaves speakState at 'playing' — so without activeKey in the comparator,
 * the previous bubble's memo skips the re-render and it keeps offering
 * Pause/Stop for audio it no longer owns.
 *
 * This test drives exactly that sequence and is the reason the roadmap's "check
 * it by hand" step is now covered by the suite instead.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, act, within } from '@testing-library/react'
import ResponseStream from '../ResponseStream'

// A controllable ttsService. The getters matter: ResponseStream reads
// ttsService.activeKey during render, so the mock must report the CURRENT value.
const tts = vi.hoisted(() => ({
  state: 'idle' as string,
  activeKey: null as string | null,
  subscriber: null as ((s: string) => void) | null,
  speak: vi.fn(),
  pause: vi.fn(),
  resume: vi.fn(),
  cancel: vi.fn(),
}))

vi.mock('@/services/ttsService', () => ({
  ttsService: {
    get state() { return tts.state },
    get activeKey() { return tts.activeKey },
    subscribe: (cb: (s: string) => void) => {
      tts.subscriber = cb
      return () => { tts.subscriber = null }
    },
    speak: tts.speak,
    pause: tts.pause,
    resume: tts.resume,
    cancel: tts.cancel,
  },
}))

vi.mock('@/stores/notificationStore', () => ({
  useNotificationStore: () => ({ addNotification: vi.fn() }),
}))

const msg = (content: string, id: string) => ({
  id,
  role: 'assistant' as const,
  content,
  timestamp: new Date('2026-09-16T12:00:00Z'),
})

const bubbleFor = (text: string) => screen.getByText(text).closest('.chat') as HTMLElement

describe('the speak cluster follows the bubble that owns the audio', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    tts.state = 'idle'
    tts.activeKey = null
    tts.subscriber = null
  })

  afterEach(() => {
    tts.state = 'idle'
    tts.activeKey = null
  })

  it('moves the controls to the new bubble when the voice SWITCHES mid-playback', () => {
    const m1 = msg('First answer.', 'm1')
    const m2 = msg('Second answer.', 'm2')

    // m2 is the one being read, and audio is playing.
    tts.state = 'playing'
    tts.activeKey = 'm2'

    const { rerender } = render(<ResponseStream messages={[m1, m2]} isStreaming={false} />)
    // the subscribe callback is how ResponseStream learns the speak state
    act(() => { tts.subscriber?.(tts.state) })

    // Baseline: m2 owns the audio, so it offers Pause + Stop; m1 offers the
    // SWITCH label — while something is playing a non-owning bubble says
    // "Switch reading to this response", not "Read this response aloud"
    // (the latter is the idle label).
    expect(within(bubbleFor('Second answer.')).getByLabelText('Pause reading')).toBeTruthy()
    expect(within(bubbleFor('Second answer.')).getByLabelText('Stop reading')).toBeTruthy()
    expect(within(bubbleFor('First answer.')).getByLabelText('Switch reading to this response')).toBeTruthy()

    // THE SWITCH — the user clicks Play on m1 while m2 is still playing.
    // activeKey changes; speakState stays 'playing'. This is the D1 hole.
    tts.activeKey = 'm1'
    rerender(<ResponseStream messages={[m1, m2]} isStreaming={false} />)

    // m1 now owns the audio...
    expect(within(bubbleFor('First answer.')).getByLabelText('Pause reading')).toBeTruthy()
    // ...and m2 has RELINQUISHED it. Without activeKey in the comparator this
    // assertion fails: m2's memo skips the re-render and it keeps the controls.
    expect(within(bubbleFor('Second answer.')).getByLabelText('Switch reading to this response')).toBeTruthy()
    expect(within(bubbleFor('Second answer.')).queryByLabelText('Pause reading')).toBeNull()
  })

  it('shows Play on every bubble when nothing is speaking', () => {
    render(<ResponseStream messages={[msg('Alpha.', 'a'), msg('Beta.', 'b')]} isStreaming={false} />)
    expect(within(bubbleFor('Alpha.')).getByLabelText('Read this response aloud')).toBeTruthy()
    expect(within(bubbleFor('Beta.')).getByLabelText('Read this response aloud')).toBeTruthy()
  })
})
