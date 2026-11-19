/**
 * CognitiveIndicator — the message-footer stage badges.
 *
 * THE BUG THIS FILE EXISTS FOR. The executor stage map carried an `idle` entry and
 * the lookup fell back to it, so an executor stage the map did not recognise drew
 * "⏸️ Idle" INSIDE the badge whose tooltip read "Thinking: active". The indicator
 * contradicted itself, during the only moment it is on screen — while the model is
 * generating. These tests pin both halves: the wrong word is gone, and the badge
 * that belongs there is still there.
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import CognitiveIndicator from '../CognitiveIndicator'
import type { CognitiveState } from '@/services/domain/StreamingService'

/** A state mid-stream: the executor is ACTIVE, and the stage is one we do not know. */
const state = (over: Partial<CognitiveState> = {}): CognitiveState =>
  ({
    isActive: true,
    // 'idle' is exactly what the live stream reports here — the stage that used to
    // fall through to the "Idle" label.
    executorStage: 'idle',
    events: [{ type: 'cognitive_executor_started', data: {} }],
    latestTrace: null,
    ...over,
  }) as unknown as CognitiveState

describe('CognitiveIndicator', () => {
  it('does NOT say "Idle" while the executor is active', () => {
    render(<CognitiveIndicator cognitiveState={state()} compact />)
    // the whole point: no "Idle" text anywhere in the footer
    expect(screen.queryByText(/Idle/i)).toBeNull()
    expect(screen.queryByText(/⏸️/)).toBeNull()
  })

  it('still shows the stage badge and its tooltip', () => {
    const { container } = render(<CognitiveIndicator cognitiveState={state()} compact />)
    // the badge that belongs there is NOT collateral damage — its tooltip is the one
    // the user reads, and it was correct all along
    const tipped = container.querySelector('[data-tip="Thinking: active"]')
    expect(tipped).not.toBeNull()
  })

  it('renders the real stage when the stream reports one', () => {
    render(<CognitiveIndicator cognitiveState={state({ executorStage: 'thinking' })} compact />)
    expect(screen.getByText(/Thinking/)).toBeTruthy()
    expect(screen.queryByText(/Idle/i)).toBeNull()
  })

  it('renders every known stage without an Idle fallback', () => {
    for (const stage of ['thinking', 'streaming', 'executing', 'completed']) {
      const { unmount } = render(<CognitiveIndicator cognitiveState={state({ executorStage: stage })} compact />)
      expect(screen.queryByText(/Idle/i)).toBeNull()
      unmount()
    }
  })

  it('does not say "Idle" in the full variant either', () => {
    // the same fallback fed the stacked variant, so the same stage must not label
    render(<CognitiveIndicator cognitiveState={state()} />)
    expect(screen.queryByText(/Idle/i)).toBeNull()
  })

  it('renders nothing at all when it is inactive with no events', () => {
    const { container } = render(
      <CognitiveIndicator cognitiveState={state({ isActive: false, events: [] })} compact />,
    )
    expect(container.textContent).toBe('')
  })
})
