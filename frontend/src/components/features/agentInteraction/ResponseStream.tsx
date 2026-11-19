/**
 * ResponseStream — the message LIST: the scrolling container, the auto-scroll,
 * the mermaid pass, the fold-hover delegation, and the empty state.
 *
 * The per-message markup lives in MessageBubble (the streaming-perf arc,
 * Phase B extraction). This component keeps only what is genuinely list-level:
 * the scroll ref and behaviour, the TTS subscription that feeds every bubble's
 * speak controls, the settings read, the mermaid effects, and the memo
 * comparator that protects the whole tree.
 */
import { useState, useEffect, useRef, memo } from 'react'
import mermaid from 'mermaid'
import type { ResponseStreamProps } from '@/types/agentInteraction'
import type { CognitiveState } from '@/services/domain/StreamingService'
import { ttsService } from '@/services/ttsService'
import { useSettingsStore } from '@/stores/settingsStore'
import { frontendLoggingService } from '@/services/frontendLoggingService'
import MessageBubble from './MessageBubble'

mermaid.initialize({ startOnLoad: false, theme: 'dark' })

const ResponseStream = ({
  messages,
  isStreaming,
  onExaApproval,
  theaterMode = false,
  cognitiveState,
}: ResponseStreamProps & { theaterMode?: boolean; cognitiveState?: CognitiveState }) => {
  const showPipelineIndicators = useSettingsStore((s) => s.settings.general.showPipelineIndicators)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)
  // THE SPEAK STATE (2026-08-30, the _24 P1 build; 2026-09-04, the
  // chat-audio rework P3): the SERVICE owns the playback — this
  // component subscribes to the state and hands it to each bubble,
  // which renders the controls on the matching message. No private state.
  const [speakState, setSpeakState] = useState(ttsService.state)
  useEffect(() => ttsService.subscribe(setSpeakState), [])

  // The speech must stop when the page unmounts (the queue is global
  // to the page — no zombie voices).
  useEffect(() => () => ttsService.cancel(), [])

  // Auto-scroll to bottom when new messages arrive or content updates (streaming)
  useEffect(() => {
    if (autoScroll && messagesEndRef.current) {
      // Scroll the messages container, not the entire page
      const messagesContainer = messagesEndRef.current.closest('.overflow-y-auto')
      if (messagesContainer) {
        messagesContainer.scrollTop = messagesContainer.scrollHeight
      }
    }
  }, [messages, autoScroll]) // Trigger on any message changes (including content updates during streaming)

  // Render mermaid diagrams when streaming completes
  useEffect(() => {
    if (!isStreaming) {
      const renderMermaid = async () => {
        try {
          frontendLoggingService.debug('ResponseStream:mermaid', 'Rendering mermaid diagrams...')
          await mermaid.run()
          frontendLoggingService.info('ResponseStream:mermaid', 'Mermaid diagrams rendered successfully')
        } catch (error) {
          frontendLoggingService.error('ResponseStream:mermaid', 'Error rendering mermaid diagram', error)
        }
      }
      // Add a small delay to ensure DOM is fully updated
      const timer = setTimeout(renderMermaid, 100)
      return () => clearTimeout(timer)
    }
  }, [isStreaming])

  // Re-render mermaid diagrams when messages change (for new diagrams)
  useEffect(() => {
    if (!isStreaming && messages.length > 0) {
      const renderMermaid = async () => {
        try {
          // Check if there are any unrendered mermaid divs
          const mermaidDivs = document.querySelectorAll('.mermaid')
          if (mermaidDivs.length > 0) {
            frontendLoggingService.debug('ResponseStream:mermaid', `Found ${mermaidDivs.length} mermaid diagram(s), rendering...`)
            await mermaid.run()
            frontendLoggingService.info('ResponseStream:mermaid', 'Mermaid diagrams re-rendered successfully')
          }
        } catch (error) {
          frontendLoggingService.error('ResponseStream:mermaid', 'Error re-rendering mermaid diagram', error)
        }
      }
      // Add a small delay to ensure DOM is fully updated
      const timer = setTimeout(renderMermaid, 100)
      return () => clearTimeout(timer)
    }
  }, [messages, isStreaming])

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const { scrollTop, scrollHeight, clientHeight } = e.currentTarget
    const isAtBottom = scrollHeight - scrollTop <= clientHeight + 50
    setAutoScroll(isAtBottom)
  }

  // THE GHOST MODE (2026-09-01, the user's ask — the try-on-the-
  // bubbles-first): read at the TOP LEVEL — a hook inside the
  // getBubbleClass function violated the Rules of Hooks (the hook
  // order jittered with the conditional calls — React's warning).
  // It is passed DOWN to each bubble so there is one subscription,
  // not one per message.
  const ghostBubbles = useSettingsStore((s) => s.settings?.appearance?.chatBubbleGhost)

  // THE 1.5-SECOND HOVER-EXPAND (2026-09-01, the user's ask — 'if
  // you hover over a collapsed bubble for 2 seconds it expands.
  // Let's try it'): hovering a COLLAPSED fold's summary expands it
  // after a DELIBERATE pause — the accidental passes do nothing.
  // THE TIMER IS 1500 ms (the value the test pins: 1499 stays shut,
  // 1500 opens) even though the ask and the older comment said "2
  // seconds" — corrected here to match the code.
  //
  // It is DELEGATED at the container (onMouseOver on the scroll div)
  // rather than bound per bubble: one handler, one timer, no matter
  // how many folds are on screen. The timer refs live at the top
  // level (the stable hook order).
  const foldHoverTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const hoveredFoldRef = useRef<HTMLDetailsElement | null>(null)

  const handleFoldHoverStart = (e: React.MouseEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement
    const details = target.closest('details.report-fold') as HTMLDetailsElement | null
    if (!details || details.open) return
    // only the collapsed fold's VISIBLE part (its summary) arms the timer
    const summary = details.querySelector('summary')
    if (!summary || !summary.contains(target)) return
    if (hoveredFoldRef.current === details && foldHoverTimer.current) return
    clearFoldHover()
    foldHoverTimer.current = setTimeout(() => {
      details.open = true
      foldHoverTimer.current = null
      hoveredFoldRef.current = null
    }, 1500)
    hoveredFoldRef.current = details
  }

  const clearFoldHover = () => {
    if (foldHoverTimer.current) {
      clearTimeout(foldHoverTimer.current)
      foldHoverTimer.current = null
    }
    hoveredFoldRef.current = null
  }

  // the unmount cleanup — the hover timer must not fire after the
  // fold's gone
  useEffect(() => clearFoldHover, [])

  return (
    <div className="flex flex-col min-h-0 h-full bg-base-100">
      {/* Messages Container */}
      <div
        className={`flex-1 overflow-y-auto px-6 space-y-4 messages-container ${
          theaterMode ? 'py-2' : 'py-4'
        }`}
        onScroll={handleScroll}
        onMouseOver={handleFoldHoverStart}
        onMouseLeave={clearFoldHover}
      >
          {messages.length === 0 ? (
            <div className="text-center text-readout py-8">
              <div className="text-4xl mb-2">💬</div>
              <p>No messages yet. Start a conversation!</p>
            </div>
          ) : (
            messages.map((message, index) => {
              // THE LAST MESSAGE OWNS THE PIPELINE INDICATOR, and the
              // cognitiveState is passed ONLY to it — so every other bubble's
              // props stay referentially stable while a stream repaints the
              // state (the streaming-perf arc: this is what makes a memo on the
              // bubble possible).
              const isLast = index === messages.length - 1
              return (
                <MessageBubble
                  key={message.id}
                  message={message}
                  isStreaming={isStreaming}
                  isLast={isLast}
                  cognitiveState={isLast ? cognitiveState : undefined}
                  showPipelineIndicators={showPipelineIndicators}
                  ghostBubbles={ghostBubbles}
                  speakState={speakState}
                  activeKey={ttsService.activeKey}
                  onExaApproval={onExaApproval}
                />
              )
            })
          )}
          
        <div ref={messagesEndRef} />
      </div>
    </div>
  )
}

// Memoize to prevent unnecessary re-renders of the whole LIST.
// The comparator's job is narrow now that the bubbles are their own components:
// it re-renders the list when the messages array changes, when streaming starts
// or stops, when theater mode flips, or when a NEW cognitiveState arrives.
//
// THE MEMO SETTLE (2026-09-02): cognitiveState is the bus pump's output — the
// settle (and the trace events themselves) MUST repaint. Without it the component
// skipped re-renders when ONLY the cognitive state changed (a late
// trace_complete never painted). This is why the comparator compares it at all;
// the test "REPAINTS when a settled cognitiveState arrives late" pins it.
export default memo(ResponseStream, (prevProps, nextProps) => {
  const messagesSame = prevProps.messages === nextProps.messages
  const isStreamingSame = prevProps.isStreaming === nextProps.isStreaming
  const theaterModeSame = prevProps.theaterMode === nextProps.theaterMode
  const cognitiveStateSame = prevProps.cognitiveState === nextProps.cognitiveState

  return messagesSame && isStreamingSame && theaterModeSame && cognitiveStateSame
})
