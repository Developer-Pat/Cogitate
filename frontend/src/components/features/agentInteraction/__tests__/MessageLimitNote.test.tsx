/**
 * The soft-limit note rides the message (Phase D.2).
 *
 * A turn that crossed a soft limit is TOLD once by the toast — this is the
 * record that stays on the message, and it survives a reload because the note
 * rides the saved row's metadata (the same shape as the truncation flag). The
 * sentence is the backend's own limit reason, so the bubble adds no copy of its
 * own: it renders what the limit said, and only on the message that crossed.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import ResponseStream from '../ResponseStream'

// ResponseStream reads ttsService during render (the speak cluster), and the
// bubble's error path touches the notification store — both are inert here.
vi.mock('@/services/ttsService', () => ({
  ttsService: {
    get state() { return 'idle' },
    get activeKey() { return null },
    subscribe: () => () => {},
    speak: vi.fn(),
    pause: vi.fn(),
    resume: vi.fn(),
    cancel: vi.fn(),
  },
}))

vi.mock('@/stores/notificationStore', () => ({
  useNotificationStore: () => ({ addNotification: vi.fn() }),
}))

const NOTE =
  'This answer has been running for 5 minutes — longer than usual. ' +
  'Nothing is blocked; the turn carries on.'

const msg = (
  content: string,
  id: string,
  metadata?: Record<string, unknown>,
) => ({
  id,
  role: 'assistant' as const,
  content,
  timestamp: new Date('2026-09-16T12:00:00Z'),
  ...(metadata ? { metadata } : {}),
})

const bubbleFor = (text: string) => screen.getByText(text).closest('.chat') as HTMLElement

describe('the soft-limit note on the message', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the limit reason on the message that crossed it, and only there', () => {
    const crossed = msg('A long answer.', 'n1', {
      limit_notice: NOTE,
      limits: [
        { key: 'wall_clock_s', value: 312, threshold: 300, reason: NOTE },
      ],
    })
    const plain = msg('A plain answer.', 'n2', { tokenCount: 42 })

    render(<ResponseStream messages={[crossed, plain]} isStreaming={false} />)

    expect(within(bubbleFor('A long answer.')).getByText(/Nothing is blocked/)).toBeTruthy()
    expect(within(bubbleFor('A plain answer.')).queryByText(/Nothing is blocked/)).toBeNull()
  })

  it('shows nothing when the turn crossed no limit', () => {
    render(
      <ResponseStream
        messages={[msg('An ordinary answer.', 'n3', { tokenCount: 12, totalTimeMs: 900 })]}
        isStreaming={false}
      />,
    )

    expect(screen.queryByText(/Nothing is blocked/)).toBeNull()
  })
})
