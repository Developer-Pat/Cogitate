// THE REPORT FOLD (2026-08-30, the user's ask): the LONG responses
// fold like the thinking/tools — the native <details> pattern; the
// short chat stays flat; the fold appears when the stream completes.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { act } from 'react'
import ResponseStream from '../ResponseStream'
import { useSettingsStore } from '@/stores/settingsStore'

vi.mock('@/stores/notificationStore', () => ({
  useNotificationStore: () => ({ addNotification: vi.fn() }),
}))

vi.mock('@/stores/settingsStore', () => ({
  useSettingsStore: vi.fn((selector: (s: unknown) => unknown) =>
    selector({ settings: { general: { showPipelineIndicators: false } } }),
  ),
}))

vi.mock('mermaid', () => ({ default: { run: vi.fn(), initialize: vi.fn() } }))

// THE PARSE SPY (the streaming-perf arc, Phase A): the mock reports every
// render so a test can COUNT how many times markdown is parsed per update.
// The rendered output is unchanged, so every pre-existing test keeps working.
const MarkdownSpy = vi.hoisted(() => vi.fn())

vi.mock('react-markdown', () => ({
  default: (props: { children: string }) => {
    MarkdownSpy(props)
    return <div data-testid="markdown">{props.children}</div>
  },
}))

const longReport =
  '# Market Report\n\n' +
  'The market showed strong momentum this week, with the technology ' +
  'sector leading gains across all major indices. Analysts point to ' +
  'continued demand for AI infrastructure as the primary driver, ' +
  'while consumer confidence surveys suggest broadening participation ' +
  'beyond the initial tech-led rally. Several sectors, including ' +
  'energy and financials, posted their best weekly performance in ' +
  'months, supported by improving earnings expectations and easing ' +
  'inflationary pressures. International markets followed suit, with ' +
  'European and Asian exchanges recording synchronized gains on ' +
  'robust trade data and a stabilizing currency environment. ' +
  'Looking ahead, strategists expect the momentum to continue ' +
  'through the next quarter, though they caution that valuations ' +
  'remain elevated relative to historical averages and recommend ' +
  'selective positioning in quality names with strong balance ' +
  'sheets and visible earnings growth. The coming weeks will be ' +
  'critical as markets digest the latest policy signals and ' +
  'corporate earnings reports.\n'

describe('the ResponseStream report fold', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  const baseMessage = (content: string, id = 'm1') => ({
    id,
    role: 'assistant' as const,
    content,
    timestamp: new Date('2026-08-30T12:00:00Z'),
  })

  it('renders the LONG responses OPEN — the auto-fold dropped (the 2026-09-01 clarity)', () => {
    render(
      <ResponseStream
        messages={[baseMessage(longReport)]}
        isStreaming={false}
      />
    )
    // the content is VISIBLE without any click (the old auto-fold
    // collapsed it — the text disappeared before the user could read)
    expect(screen.getByTestId('markdown')).toBeTruthy()
    const details = document.querySelector('details.report-fold')
    expect(details).toBeTruthy()
    expect((details as HTMLDetailsElement).open).toBe(true)
  })

  it('keeps the SHORT chat flat — no fold', () => {
    render(
      <ResponseStream
        messages={[baseMessage('Hello! How can I help?')]}
        isStreaming={false}
      />
    )
    expect(screen.queryByText(/Response \([\d,]+ chars\)/)).toBeNull()
    expect(screen.getByTestId('markdown')).toBeTruthy()
  })

  it('keeps the NORMAL text size inside the open fold (the text-xs bug fix)', () => {
    render(
      <ResponseStream
        messages={[baseMessage(longReport)]}
        isStreaming={false}
      />
    )
    const details = document.querySelector('details.report-fold')
    expect(details).toBeTruthy()
    expect(details!.className).not.toContain('text-xs')
    const summary = details!.querySelector('summary')
    expect(summary!.className).toContain('text-xs')
  })

  it('stays flat while streaming — the live text stays visible', () => {
    render(
      <ResponseStream
        messages={[baseMessage(longReport)]}
        isStreaming={true}
      />
    )
    // no fold while streaming — the live text is not collapsed
    expect(screen.queryByText(/Response \([\d,]+ chars\)/)).toBeNull()

    // THE STREAMING PATH RENDERS BLOCK-WISE. The mock gives each block its own
    // container, so asserting exactly one would test the splitter's block count
    // rather than the thing this test is about. Assert the CONTENT instead —
    // which is stronger: it fails if the split ever drops or reorders a block.
    const blocks = screen.getAllByTestId('markdown')
    expect(blocks.length).toBeGreaterThanOrEqual(1)
    const all = blocks.map((n) => n.textContent || '').join('\n')
    expect(all).toContain('# Market Report')
    expect(all).toContain('strong momentum this week')
    expect(all).toContain('corporate earnings reports')
  })
  it('GHOST MODE: the bubbles get the bubble-ghost class (the 2026-09-01 build)', () => {
    vi.mocked(useSettingsStore).mockImplementation((selector) =>
      selector({
        settings: { general: { showPipelineIndicators: false }, appearance: { chatBubbleGhost: true } },
      } as never),
    )
    render(
      <ResponseStream
        messages={[baseMessage('A normal-sized response.')]}
        isStreaming={false}
      />
    )
    const bubbles = document.querySelectorAll('.chat-bubble.bubble-ghost')
    expect(bubbles.length).toBeGreaterThan(0)
    // reset — the other tests expect the default (ghost off)
    vi.mocked(useSettingsStore).mockReset()
    vi.mocked(useSettingsStore).mockImplementation((s) =>
      s({ settings: { general: { showPipelineIndicators: false } } } as never),
    )
  })

  it('THE HOVER-EXPAND: a COLLAPSED fold expands after 1.5s, and not a tick before (the 2026-09-01 try)', () => {
    vi.useFakeTimers()
    const { container } = render(
      <ResponseStream
        messages={[baseMessage(longReport)]}
        isStreaming={false}
      />
    )
    const details = container.querySelector('details.report-fold') as HTMLDetailsElement
    expect(details).toBeTruthy()
    // the user's manual collapse
    details.open = false
    const summary = details.querySelector('summary') as HTMLElement
    fireEvent.mouseOver(summary)
    act(() => { vi.advanceTimersByTime(1499) })
    expect(details.open).toBe(false)
    act(() => { vi.advanceTimersByTime(1) })
    expect(details.open).toBe(true)
    vi.useRealTimers()
  })


describe('THE PIPELINE-INDICATOR SETTLE (the user reported "it is still running", 2026-09-02)', () => {
  // The indicator must show the spinner ONLY while a stream is live.
  // The bus pump (useTracePanel) clears isActive only on a
  // trace_complete event — which can miss on the stream tail. The
  // render site settles when isStreaming is false.
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useSettingsStore).mockImplementation((selector) =>
      selector({
        settings: { general: { showPipelineIndicators: true } },
        appearance: { chatBubbleGhost: false },
      } as never),
    )
  })

  const stuckState = {
    isActive: true,
    executorStage: 'running' as string,
    latestTrace: null,
    events: [
      { type: 'cognitive_executor_started' as const, data: { component: 'executor' as const, strategy: 'hybrid' } },
    ],
  }

  it('SHOWS the spinner while streaming — the ONE activity animation', () => {
    // (2026-09-05, the user's call: the stage badges highlight
    // statically and never pulse — a stuck-active state would pulse
    // forever. The spinner is the only animated activity cue.)
    render(
      <ResponseStream
        messages={[baseMessage('Hello! How can I help?', 'm-live')]}
        isStreaming={true}
        cognitiveState={stuckState}
      />,
    )
    expect(document.querySelector('.loading-spinner')).not.toBeNull()
    expect(document.querySelector('.animate-pulse')).toBeNull()
  })

  it('SETTLES when the stream is done — the spinner must not spin forever', () => {
    render(
      <ResponseStream
        messages={[baseMessage('Hello! How can I help?', 'm-done')]}
        isStreaming={false}
        cognitiveState={stuckState}
      />,
    )
    // THE BUG: the bus state still says isActive (trace_complete missed)
    // — but no stream is running, so the indicator must NOT spin.
    expect(document.querySelector('.loading-spinner')).toBeNull()
    expect(document.querySelector('.animate-pulse')).toBeNull()
  })

  it('REPAINTS when a settled cognitiveState arrives late (the memo comparator)', () => {
    const settledState = {
      isActive: false,
      executorStage: 'completed' as string,
      latestTrace: {
        trace: {
          context_builder: { component: 'context_builder', strategy: 'semantic', duration_ms: 10, tokens_used: 5, sources: [] },
          executor: { component: 'executor', strategy: 'hybrid', duration_ms: 20, tokens_used: 10 },
          memory_manager: { component: 'memory_manager', strategy: 'window', duration_ms: 5, tokens_used: 0 },
          response_formatter: { component: 'response_formatter', strategy: 'md', duration_ms: 5, tokens_used: 0 },
          total_duration_ms: 40,
          total_tokens: 15,
        },
        metrics: { total_duration_ms: 40, total_tokens: 15, llm_calls: 1, tool_calls: 0, cache_hits: 0 },
        memory_delta: null,
      },
      events: [
        { type: 'cognitive_executor_started' as const, data: { component: 'executor' as const, strategy: 'hybrid' } },
        { type: 'cognitive_trace_complete' as const, data: {} as never },
      ],
    }
    // THE SAME messages reference across renders — the memo comparator
    // decides: only cognitiveState changes between the two renders.
    const sameMessages = [baseMessage('Hello! How can I help?', 'm-late')]
    const { rerender } = render(
      <ResponseStream
        messages={sameMessages}
        isStreaming={false}
        cognitiveState={stuckState}
      />,
    )
    // late-arriving trace_complete: a NEW cognitiveState object must repaint.
    // The discriminator: the "15 tokens" readout renders ONLY from
    // latestTrace (which arrives with trace_complete) — without the memo
    // comparator fix the rerender is skipped and it never appears.
    rerender(
      <ResponseStream
        messages={sameMessages}
        isStreaming={false}
        cognitiveState={settledState}
      />,
    )
    expect(screen.getByText('15 tokens')).toBeTruthy()
    expect(document.querySelector('.loading-spinner')).toBeNull()
  })

  // reset for the other suites (fold tests expect the default mock)
  afterEach(() => {
    vi.mocked(useSettingsStore).mockReset()
    vi.mocked(useSettingsStore).mockImplementation((s) =>
      s({ settings: { general: { showPipelineIndicators: false } } } as never),
    )
  })
})
})

// ── THE PER-UPDATE PARSE COUNT (the streaming-perf arc, Phase A) ────────────
//
// WHAT THIS GUARDS, AND WHY IT IS THE RIGHT METRIC. During a stream the UI
// re-renders ~10x/sec (the service throttles updates to
// STREAM_UPDATE_INTERVAL_MS = 100). The cost per update is the problem, not
// the rate: `ResponseStream` calls ReactMarkdown inside its messages.map(),
// so on every update EVERY bubble re-parses and re-highlights its full text.
// Counting parses per update measures that directly.
//
// THE STORE'S CONTRACT, VERIFIED (Phase A, 2026-09-16) — this is what makes a
// memo possible. An update replaces exactly ONE message object and leaves the
// rest untouched, at all three layers:
//   agentStore.updateSessionMessage        -> map: `{...msg}` for the target,
//                                             the SAME ref for everything else
//   MessageService.updateMessageInSession  -> same targeted shallow replace
//   the session object                     -> new object, new array, same elements
// NOTE: agentStore's comment says "deep copied messages" — the code is a
// shallow targeted replace. The comment lies; the code is correct.
//
// So a memo keyed on message IDENTITY is exactly right: the streaming message
// is a new object each update and must re-render, every other message keeps its
// reference and must not. THIS TEST READS 3 TODAY AND MUST READ 1 AFTER THE
// MEMO LANDS. It fails now on purpose — the failure is the proof, and it is the
// regression guard for that change.
describe('the per-update markdown parse count (the streaming arc, Phase A)', () => {
  const msg = (content: string, id: string) => ({
    id,
    role: 'assistant' as const,
    content,
    timestamp: new Date('2026-09-16T12:00:00Z'),
  })

  beforeEach(() => {
    MarkdownSpy.mockClear()
  })

  it('re-parses ONLY the message that changed — not the whole history', () => {
    const m1 = msg('First answer.', 'm1')
    const m2 = msg('Second answer.', 'm2')
    const m3 = msg('Third answer, streaming', 'm3')

    const { rerender } = render(<ResponseStream messages={[m1, m2, m3]} isStreaming />)

    // One parse per message on mount — that part is correct and stays correct.
    const afterMount = MarkdownSpy.mock.calls.length
    expect(afterMount).toBe(3)

    // THE STREAMING UPDATE: only m3 is replaced. m1 and m2 are the SAME objects,
    // exactly as the store hands them over.
    const m3b = { ...m3, content: 'Third answer, streaming and now longer' }
    rerender(<ResponseStream messages={[m1, m2, m3b]} isStreaming />)

    const perUpdate = MarkdownSpy.mock.calls.length - afterMount
    // The contract: ONE parse, for the one message that changed.
    expect(perUpdate).toBe(1)
  })

  it('DOES re-parse the message that changed — the memo must not over-reach', () => {
    // The other half of the guard. A memo that skips too much would freeze the
    // stream on screen, which is worse than the stutter this arc is fixing.
    const m1 = msg('First answer.', 'm1')
    const m2 = msg('Second answer.', 'm2')

    const { rerender } = render(<ResponseStream messages={[m1, m2]} isStreaming />)
    const afterMount = MarkdownSpy.mock.calls.length

    const m2b = { ...m2, content: 'Second answer, now with NEW text added' }
    rerender(<ResponseStream messages={[m1, m2b]} isStreaming />)

    const perUpdate = MarkdownSpy.mock.calls.length - afterMount
    expect(perUpdate).toBeGreaterThanOrEqual(1)
    // and the new text really is on screen — the bubble is live, not frozen
    expect(screen.getByText(/NEW text added/)).toBeTruthy()
    expect(screen.getByText(/First answer/)).toBeTruthy()
  })
})
