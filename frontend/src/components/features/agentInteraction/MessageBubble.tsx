/**
 * MessageBubble — ONE message in the chat stream: the header, the bubble
 * (markdown, tool result, or approval card), and the assistant footer (the
 * speak cluster, the metrics, the action buttons, the pipeline indicator).
 *
 * EXTRACTED FROM ResponseStream (the streaming-perf arc, Phase B). The markup
 * and the helpers move here VERBATIM — this extraction changes no behaviour and
 * adds no optimisation. It exists so the bubble can be memoized on the
 * message's identity in Phase C.
 *
 * WHY IDENTITY IS THE RIGHT KEY (verified Phase A, 2026-09-16): when a stream
 * updates, the store replaces EXACTLY ONE message object and leaves every other
 * message's reference untouched (agentStore.updateSessionMessage -> a targeted
 * map; MessageService.updateMessageInSession; same at the session level). So a
 * finished bubble's props are referentially stable while the streaming bubble's
 * are not — which is precisely what a memo needs.
 *
 * NOT YET MEMOIZED: Phase C adds that. Until then this renders exactly as it
 * did inline.
 */
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import 'highlight.js/styles/atom-one-dark.css'
import { memo } from 'react'
import type { ReactNode } from 'react'
import type { ConversationMessage, ResponseStreamProps } from '@/types/agentInteraction'
import type { CognitiveState } from '@/services/domain/StreamingService'
import { ttsService } from '@/services/ttsService'
import { useNotificationStore } from '@/stores/notificationStore'
import { frontendLoggingService } from '@/services/frontendLoggingService'
import { splitStreamingMarkdown } from '@/utils/text/streamingMarkdown'
import CognitiveIndicator from './CognitiveIndicator'

// THE RESPONSE FOLD (2026-08-30, the user's ask; renamed from 'Report'
// 2026-09-01 — 'Response is probably good'): the LONG responses fold like the
// thinking/tools — the native <details> pattern (the app-level fold; markdown
// has no fold syntax — the content stays markdown INSIDE the fold). The SHORT
// chat stays flat; the fold appears when the stream completes. The text-xs
// lives on the SUMMARY ONLY (2026-09-01: the fold-wide class shrank the
// restored content — the user's text-size report).
const REPORT_FOLD_THRESHOLD = 600

// THE STREAMING RENDER (the UI chat optimization follow-on). While a reply
// streams, the accumulated text grows and this component re-renders. Rendering
// the whole document each time means re-parsing and re-creating the entire
// element tree — measured at ~45 ms per update for a ~6 KB answer, which is
// essentially all of the blocked main-thread time during a stream.
//
// Markdown is *almost* compositional, so a finished block is a stable string
// and can be memoized. `splitStreamingMarkdown` decides where splitting is
// provably output-preserving and DECLINES elsewhere; see that module for the
// failure modes it guards (loose lists, reference definitions).
const STREAMING_REMARK_PLUGINS = [remarkGfm]
const STREAMING_REHYPE_PLUGINS = [rehypeHighlight]

/**
 * One markdown block, memoized on its own TEXT.
 *
 * This is where the saving comes from: once a block is finished its text never
 * changes again, so this never re-renders for the rest of the stream — only the
 * trailing partial block does.
 *
 * (`components={{ code: CodeBlock }}` is written inline rather than hoisted:
 * CodeBlock is declared further down this module, and hoisting it here would
 * reference it before initialization. The memo skips on text equality, so the
 * inline object costs nothing when the block does not change.)
 */
const MarkdownBlock = memo(
  ({ text }: { text: string }) => (
    <ReactMarkdown
      remarkPlugins={STREAMING_REMARK_PLUGINS}
      rehypePlugins={STREAMING_REHYPE_PLUGINS}
      components={{ code: CodeBlock }}
    >
      {text}
    </ReactMarkdown>
  ),
  (prev, next) => prev.text === next.text,
)

/**
 * Render streaming markdown block-wise so finished blocks are stable.
 *
 * Falls through to a single block when the splitter declines (one block is the
 * safe answer there, not a failure). Keys are positional, which is correct here:
 * a block's text never changes once the next block exists, and the memo compares
 * text — so even if a boundary shifted, the worst case is a re-render, never a
 * wrong render.
 */
const StreamingMarkdown = memo(({ text }: { text: string }) => {
  const blocks = splitStreamingMarkdown(text)
  if (blocks.length === 1) return <MarkdownBlock text={text} />
  return <>{blocks.map((b: string, i: number) => <MarkdownBlock key={i} text={b} />)}</>
})

// THE SPEAKABLE TEXT (2026-08-30, the _24 P1 build): the response's raw
// markdown is fine to READ — strip the markdown punctuation the voices would
// otherwise spell out (the bold/italic/code fences).
const speakableText = (content: string): string =>
  content
    .replace(/```[\s\S]*?```/g, ' ') // the code fences -> a pause
    .replace(/[*_~`#>|]/g, ' ')
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1') // the links -> their label
    .replace(/\s+/g, ' ')
    .trim()

// Custom code renderer for mermaid diagrams + the hydration-safe
// inline/block split.
//
// REACT-MARKDOWN v10 (2026-08-24, the live-test catch): there is NO `inline`
// prop — v9 removed it (passNode is the mechanism). The language-* class is the
// reliable discriminator: BLOCK (fenced) code carries `language-xxx`; INLINE
// code has none. Rendering a <pre> for inline code puts a <pre> inside a <p> —
// INVALID HTML (the 'cannot be a descendant of p' hydration error). Inline code
// renders as a bare <code>; block code keeps the <pre>.
export const CodeBlock = ({ node: _node, className, children, ...props }: { node?: unknown; className?: string; children?: ReactNode }): ReactNode => {
  const match = /language-(\w+)/.exec(className || '')
  const language = match ? match[1] : ''

  if (language === 'mermaid') {
    const code = String(children).replace(/\n$/, '')
    return (
      <div
        className="mermaid rounded-lg my-2 p-3 bg-base-200 overflow-x-auto"
        dangerouslySetInnerHTML={{ __html: code }}
      />
    )
  }

  // INLINE code (no language class): a bare <code> — never a <pre> (the
  // hydration rule).
  if (!language) {
    return (
      <code className={`${className || ''} bg-base-300 rounded px-1.5 py-0.5 text-sm`} {...props}>
        {children}
      </code>
    )
  }

  // BLOCK code (fenced, language-*): the <pre> wrapper.
  return (
    <pre className="bg-base-300 rounded-lg p-3 overflow-x-auto my-2" {...props}>
      <code className={className}>
        {children}
      </code>
    </pre>
  )
}

// THE MODEL MARKDOWN NORMALIZER (2026-08-24, the user's report): gpt-oss:20b
// emits <br> as its line breaks + '•' for the bullets INSIDE the answer text —
// the ReactMarkdown escapes the raw <br> (no rehypeRaw) so the user sees the
// literal tags. The light pre-pass: <br> -> the paragraph break, • -> the
// markdown bullet. No other rewriting; the markdown passes through untouched.
function normalizeModelMarkdown(text: string): string {
  return text
    .replace(/<br\s*\/?>/gi, '\n\n')
    .replace(/•\s*/g, '- ')
}

// THE THINKING FOLD FORMATTING (2026-08-24): the reasoning chunks stream
// NEWLINE-LESS (0 \n in 280 live chunks — the model's stream shape through the
// ollama_chat handler) — the sentences run together ('help.Hey'). The light
// display fix: space after the sentence endings so the fold reads naturally.
// No other rewriting.
function formatReasoning(text: string): string {
  // 'help.Hey' -> 'help. Hey' (the newline-less stream shape);
  // decimals ('2.5x') and existing spaces are untouched
  return text.replace(/([.!?])([A-Z])/g, '$1 $2')
}

// CHAT AUTHORIZATION (2026-08-21): the Approve/Deny card for a pending
// permission request. The diff + the options live in the request payload; the
// buttons resolve via onExaApproval (the hook sends the decision over the live
// Exa WebSocket).
function ApprovalCard({ message, onApprove }: {
  message: { metadata?: { request_id?: string; request?: unknown; resolved?: boolean; resolved_at?: string } },
  onApprove?: (requestId: string, optionId: string) => void,
}) {
  const req = (message.metadata?.request || {}) as Record<string, unknown>
  const requestId = message.metadata?.request_id || ''
  const title = String(req.title || 'a file')
  const content = (req.content || []) as Array<Record<string, unknown>>
  const diff = content.map(c => String(c.text || c.content || '')).join('\n')
  const optionIds = ((req.options || []) as Array<Record<string, unknown>>)
    .map(o => String(o.option_id || ''))
  const allowId = optionIds.find(id => id !== 'deny') || 'allow_once'
  const resolved = message.metadata?.resolved

  // THE RESOLVED STATE (2026-08-21): one compact line — granted
  // (green ✓) or denied (red ✕) — instead of the big card sitting
  // there after the decision. The buttons are gone; the audit
  // trail (what was approved) stays in the thread.
  if (resolved !== undefined) {
    const granted = resolved === true
    return (
      <div className={`flex items-center gap-2 rounded-lg px-3 py-1.5 mt-1 text-xs font-medium ${
        granted ? 'bg-success/10 text-success border border-success/30'
                : 'bg-error/10 text-error border border-error/30'
      }`}>
        <span aria-hidden>{granted ? '✓' : '✕'}</span>
        <span>
          Permission {granted ? 'granted' : 'denied'}
          {title !== 'a file' && <span className="opacity-70"> — {title}</span>}
        </span>
      </div>
    )
  }

  return (
    <div className="border border-warning/40 bg-warning/5 rounded-lg p-3 mt-1">
      <div className="flex items-center gap-2 mb-2">
        <span className="badge badge-sm badge-warning badge-outline">Permission</span>
        <span className="text-xs font-medium truncate">{title}</span>
      </div>
      {diff && (
        <pre className="text-xs bg-base-300 p-2 rounded overflow-x-auto max-h-40 mb-2 whitespace-pre-wrap">
          {diff}
        </pre>
      )}
      <div className="flex items-center gap-2">
        <button
          type="button"
          className="btn btn-xs btn-success"
          onClick={() => onApprove?.(requestId, allowId)}
        >
          Allow edit
        </button>
        <button
          type="button"
          className="btn btn-xs btn-outline"
          onClick={() => onApprove?.(requestId, 'deny')}
        >
          Deny
        </button>
      </div>
    </div>
  )
}

export interface MessageBubbleProps {
  message: ConversationMessage
  isStreaming: boolean
  /** The LAST message carries the pipeline indicator — and only it. */
  isLast: boolean
  /** Passed only for the last message, so a memo on the others stays stable. */
  cognitiveState?: CognitiveState
  showPipelineIndicators: boolean
  /** The ghost-bubble setting, read once by the parent (one subscription). */
  ghostBubbles: boolean
  /** The global TTS state; the ACTIVE bubble decides its own controls from it. */
  speakState: typeof ttsService.state
  /**
   * The key of the message currently being spoken, passed IN rather than read
   * off the service inside this component (the D1 settlement, Phase C).
   *
   * WHY IT MUST BE A PROP: ttsService.activeKey is NOT React state, so a memo
   * cannot see it change. The failure it prevents is concrete — switching the
   * voice to another bubble while one is already playing changes activeKey but
   * leaves speakState at 'playing', so the PREVIOUS bubble would never repaint
   * back to its Play button (it would sit there offering Pause/Stop for audio it
   * no longer owns).
   */
  activeKey: typeof ttsService.activeKey
  onExaApproval?: ResponseStreamProps['onExaApproval']
}

/**
 * One message bubble. Moved verbatim from ResponseStream's messages.map().
 */
function MessageBubble({
  message,
  isStreaming,
  isLast,
  cognitiveState,
  showPipelineIndicators,
  ghostBubbles,
  speakState,
  activeKey,
  onExaApproval,
}: MessageBubbleProps) {
  const addNotification = useNotificationStore((state) => state.addNotification)

  const formatTimestamp = (timestamp: Date) => {
    return new Date(timestamp).toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  }

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)

      // Show success notification
      addNotification({
        type: 'success',
        title: 'Copied!',
        message: 'Message copied to clipboard',
        duration: 2000
      })

      frontendLoggingService.info('ResponseStream:clipboard', 'Copied to clipboard', { textLength: text.length })
    } catch (err) {
      frontendLoggingService.error('ResponseStream:clipboard', 'Failed to copy to clipboard', err)
      // Fallback for older browsers
      const textArea = document.createElement('textarea')
      textArea.value = text
      document.body.appendChild(textArea)
      textArea.select()
      document.execCommand('copy')
      document.body.removeChild(textArea)

      // Show success notification for fallback too
      addNotification({
        type: 'success',
        title: 'Copied!',
        message: 'Message copied to clipboard',
        duration: 2000
      })

      frontendLoggingService.info('ResponseStream:clipboard', 'Copied to clipboard (fallback)')
    }
  }

  const getMessageClass = (role: string) => {
    switch (role) {
      case 'user':
        return 'chat chat-end'
      case 'assistant':
        // Use chat-start but center the bubble with flex
        return 'chat chat-start [&_.chat-bubble]:mx-auto'
      case 'system':
        return 'chat chat-center'
      case 'tool':
        return 'chat chat-start [&_.chat-bubble]:mx-auto'
      default:
        return 'chat'
    }
  }

  const getBubbleClass = (role: string) => {
    if (ghostBubbles) {
      switch (role) {
        case 'user':
          return 'chat-bubble bubble-ghost max-w-[90%] text-[var(--chat-bubble-assistant-text)]'
        case 'assistant':
          return 'chat-bubble bubble-ghost w-[90%] text-[var(--chat-bubble-assistant-text)]'
        default:
          break
      }
    }
    switch (role) {
      case 'user':
        // Use same styling as assistant for less distracting environment
        // THE USER'S WIDTH (2026-09-01, the UI queue #1): the constant-width
        // fix's w-[90%] belongs to the ASSISTANT's streaming bubble (the
        // eye-strain fix) — the blanket replace hit the user's too, making it
        // the same size as the assistant's. The user's stays CONTENT-sized (the
        // max-w — it grows to fit the text, never beyond; the user's messages
        // are static, no streaming growth to stabilize).
        return 'chat-bubble max-w-[90%] bg-[var(--chat-bubble-assistant-bg)] text-[var(--chat-bubble-assistant-text)]'
      case 'assistant':
        return 'chat-bubble w-[90%] bg-[var(--chat-bubble-assistant-bg)] text-[var(--chat-bubble-assistant-text)]'
      case 'system':
        return 'chat-bubble chat-bubble-accent max-w-[90%]'
      case 'tool':
        return 'chat-bubble w-[90%] bg-info/10 text-info border border-info/20'
      default:
        return 'chat-bubble'
    }
  }

  // THE CLUSTER (P3): a bubble that is NOT the active speaker starts the speech
  // (the queue policy cancels whatever plays — one voice); the ACTIVE bubble
  // shows the pause/stop (or resume/stop) instead of a play — the user's "no
  // play while playing" rule.
  const handleSpeak = (msg: ConversationMessage) => {
    const text = speakableText(String(msg.content || ''))
    if (!text.trim()) return
    ttsService.speak(text, { key: msg.id })
  }

  return (
    <div className={getMessageClass(message.role)}>
      {/* Header - for user, assistant, and tool messages */}
      <div className={`chat-header opacity-70 text-xs mb-1 ${
        message.role === 'assistant' || message.role === 'tool' ? 'text-center w-full' : ''
      }`}>
        {message.role === 'user' ? 'You' :
         message.role === 'assistant' ? 'Assistant' :
         message.role === 'tool' ? `Tool: ${message.tool_name || 'Unknown'}` :
         'System'}
        <time className="text-xs opacity-50 ml-2">
          {formatTimestamp(message.timestamp)}
        </time>
      </div>
      <div className={getBubbleClass(message.role)}>
        <div className="relative">
          <div className="markdown-content">
            {message.role === 'tool' && message.tool_name === 'approval' ? (
              <ApprovalCard message={message} onApprove={onExaApproval} />
            ) : message.role === 'tool' ? (
              <div className="tool-result">
                <div className="flex items-center gap-2 mb-2">
                  <div className="badge badge-sm badge-info badge-outline">
                    {message.tool_name || 'Tool'}
                  </div>
                  {message.metadata?.tool_execution_time && (
                    <div className="text-xs opacity-70">
                      {message.metadata.tool_execution_time}ms
                    </div>
                  )}
                  {message.metadata?.tool_success !== undefined && (
                    <div className={`badge badge-sm ${message.metadata.tool_success ? 'badge-success badge-outline' : 'badge-error badge-outline'}`}>
                      {message.metadata.tool_success ? 'Success' : 'Failed'}
                    </div>
                  )}
                </div>
                <div className="tool-result-content">
                  {typeof message.tool_result === 'object' ? (
                    <pre className="text-xs bg-base-200 p-2 rounded overflow-x-auto">
                      {JSON.stringify(message.tool_result, null, 2)}
                    </pre>
                  ) : (
                    <ReactMarkdown
                      rehypePlugins={[rehypeHighlight]}
                      components={{ code: CodeBlock }}
                    >
                      {String(message.content || message.tool_result || 'Tool executed')}
                    </ReactMarkdown>
                  )}
                </div>
                {message.metadata?.tool_error && (
                  <div className="mt-2 p-2 bg-error/10 text-error text-xs rounded">
                    <strong>Error:</strong> {message.metadata.tool_error}
                  </div>
                )}
              </div>
            ) : (
              <>
                {/* THE THINKING FOLD (2026-08-24, the user's ask): the
                    chain-of-thought renders behind a collapsible fold —
                    COLLAPSED by default, the click toggles. The bubble carries
                    only the clean answer. */}
                {message.metadata?.reasoning ? (
                  <details className="thinking-fold mb-2 text-xs">
                    <summary className="cursor-pointer select-none opacity-60 hover:opacity-100 transition-opacity">
                      Thinking
                    </summary>
                    <div className="mt-1.5 p-2 rounded bg-base-200/60 border border-base-300/40 whitespace-pre-wrap leading-relaxed text-readout max-h-64 overflow-y-auto">
                      {formatReasoning(message.metadata.reasoning)}
                    </div>
                  </details>
                ) : null}
                {/* THE ACTIVITY FOLD (2026-08-29, the panel-port): the Exa
                    page's tool-call titles render behind the SAME collapsible
                    pattern — the answer is never pushed off-screen by the
                    thinking. The summary reads 'Thinking' while live, 'N steps'
                    once the turn ends. */}
                {message.activity && message.activity.length > 0 && (
                  <details className="thinking-fold mb-2 text-xs">
                    <summary className="cursor-pointer select-none opacity-60 hover:opacity-100 transition-opacity">
                      Tools ({message.activity.length})
                    </summary>
                    <div className="mt-1.5 p-2 rounded bg-base-200/60 border border-base-300/40 flex flex-col gap-0.5 max-h-64 overflow-y-auto">
                      {message.activity.map((a, i) => (
                        <div key={i} className="text-[11px] opacity-70 flex items-center gap-1 font-mono">
                          {message.activityDone && <span className="opacity-60">▸</span>}
                          {a}
                        </div>
                      ))}
                    </div>
                  </details>
                )}
                {!isStreaming && message.content.length > REPORT_FOLD_THRESHOLD ? (
                  // THE AUTO-FOLD DROPPED (2026-09-01, the user's clarity —
                  // 'drop the auto fold'): the long responses now render OPEN —
                  // the content is always visible. The old collapsed-default
                  // SNAPPED the fold in at stream-complete and hid the text the
                  // user was still reading ('folds in the middle of the stream
                  // causing it to disappear'). The fold UNIT stays (the
                  // fold/expand button's manual history-taming); only the
                  // auto-collapse is gone.
                  <details className="report-fold mb-2" open>
                    <summary className="cursor-pointer select-none opacity-60 hover:opacity-100 transition-opacity text-xs">
                      Response ({message.content.length.toLocaleString()} chars) — click to collapse
                    </summary>
                    <div className="mt-1.5">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        rehypePlugins={[rehypeHighlight]}
                        components={{ code: CodeBlock }}
                      >
                        {normalizeModelMarkdown(message.content || '')}
                      </ReactMarkdown>
                    </div>
                  </details>
                ) : (
                  // THE STREAMING BRANCH — block-wise, so finished blocks are
                  // memoized and only the trailing partial block re-parses.
                  // The FOLD branch above (non-streaming, long) still renders
                  // whole: its output is what the user keeps, so it stays
                  // exactly as it was.
                  <StreamingMarkdown text={normalizeModelMarkdown(message.content || '')} />
                )}
              </>
            )}
          </div>
        </div>
      </div>
      {/* THE LIMIT NOTE (D.2, moved out of the footer 2026-09-23): a turn that
          crossed a limit says so ON the message — the toast is the moment, this
          is the record, and it survives a reload because the note rides the saved
          row's metadata. Inside the footer's flex row it was SQUEEZED (measured
          live: 65px wide × 418px tall, one word per line) because `chat-footer`
          is `flex items-center justify-center gap-2` and a long flex child
          shrinks without a basis. As its own child of the chat container it gets
          the full row; `col-span-2` because that container is the DaisyUI chat
          GRID — without it the note would land in a single column. */}
      {message.role === 'assistant' && message.metadata?.limit_notice && (
        <div className="col-span-2 mt-1.5 p-2 bg-warning/10 text-warning text-xs rounded border border-warning/20">
          {String(message.metadata.limit_notice)}
        </div>
      )}
      {/* Footer - only for assistant messages */}
      {message.role === 'assistant' && (
        <div className="chat-footer mt-1 flex items-center justify-center gap-2 text-xs">
          {/* THE SPEAK CLUSTER (2026-08-30, the _24 P1 build; 2026-09-04, the
              chat-audio rework P3 — the play/pause/resume/stop state machine):
              the service OWNS the state; the ACTIVE bubble shows Pause⇄Resume +
              Stop (never a play — the user's rule), the other bubbles show Play
              (the click switches — the queue policy cancels the current voice).
              The click IS the autoplay gesture (the manual path always works).
              THE AUTO-READ rides the SAME key — an auto-read bubble shows these
              controls too (never unstoppable). */}
          {(() => {
            // activeKey arrives as a PROP (the D1 settlement) — reading
            // ttsService.activeKey here would make this bubble blind to a
            // voice SWITCH, which changes the key without changing speakState.
            const isThis = activeKey === message.id && speakState !== 'idle'
            const thisPlaying = isThis && speakState === 'playing'
            const thisPaused = isThis && speakState === 'paused'
            return (
              <div className="flex items-center gap-0.5">
                {thisPlaying ? (
                  <span className="tooltip tooltip-top" data-tip="Pause reading">
                  <button
                    className="btn btn-ghost btn-xs text-primary"
                    onClick={() => ttsService.pause()}
                    aria-label="Pause reading"
                  >
                    <svg className="h-3.5 w-3.5" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M6 5h4v14H6zM14 5h4v14h-4z" />
                    </svg>
                  </button>
                  </span>
                ) : thisPaused ? (
                  <span className="tooltip tooltip-top" data-tip="Resume reading">
                  <button
                    className="btn btn-ghost btn-xs text-primary"
                    onClick={() => ttsService.resume()}
                    aria-label="Resume reading"
                  >
                    <svg className="h-3.5 w-3.5" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M8 5v14l11-7z" />
                    </svg>
                  </button>
                  </span>
                ) : (
                  <span className="tooltip tooltip-top" data-tip={speakState !== 'idle' ? 'Switch reading to this response' : 'Read this response aloud'}>
                  <button
                    className={`btn btn-ghost btn-xs ${speakState !== 'idle' ? 'opacity-50' : ''}`}
                    onClick={() => handleSpeak(message)}
                    aria-label={speakState !== 'idle' ? 'Switch reading to this response' : 'Read this response aloud'}
                  >
                    <svg className="h-3.5 w-3.5" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M8 5v14l11-7z" />
                    </svg>
                  </button>
                  </span>
                )}
                {isThis && (
                  <span className="tooltip tooltip-top" data-tip="Stop reading">
                  <button
                    className="btn btn-ghost btn-xs text-error/80"
                    onClick={() => ttsService.cancel()}
                    aria-label="Stop reading"
                  >
                    <svg className="h-3.5 w-3.5" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M6 6h12v12H6z" />
                    </svg>
                  </button>
                  </span>
                )}
                {isThis && (
                  <span className="text-[10px] opacity-60 animate-pulse">
                    {thisPaused ? 'paused…' : 'speaking…'}
                  </span>
                )}
              </div>
            )
          })()}
          {/* Metrics - shown when metadata exists */}
          {message.metadata ? (
            <div className="flex items-center gap-2 opacity-70">
              {message.metadata.totalTimeMs && (
                <div className="tooltip tooltip-top" data-tip="Generation time">
                  <span className="flex items-center gap-1">
                    <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    {Math.round(message.metadata.totalTimeMs)}ms
                    <svg className="h-3 w-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </span>
                </div>
              )}
              {message.metadata.tokenCount && (
                <div className="tooltip tooltip-top" data-tip="Token count">
                  <span className="flex items-center gap-1">
                    <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    {message.metadata.tokenCount} tokens
                    <svg className="h-3 w-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </span>
                </div>
              )}
              {message.metadata.exa_meta && (
                <div className="flex items-center gap-2">
                  {/* the MODEL badge is NOT rendered here — the footer's
                      metadata.model badge (below) shows it once; this block adds
                      only the Exa turn time + context usage (2026-08-22: the
                      user caught the double badge) */}
                  {message.metadata.exa_working && (
                    <span className="badge badge-sm badge-info animate-pulse">
                      working… {String(message.metadata.exa_tool || '')}
                    </span>
                  )}
                  {typeof message.metadata.elapsed_ms === 'number' && (
                    <div className="tooltip tooltip-top" data-tip="Turn time">
                      <span className="flex items-center gap-1">
                        <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        {(Number(message.metadata.elapsed_ms) / 1000).toFixed(1)}s
                      </span>
                    </div>
                  )}
                  {message.metadata.ctx && (
                    <div className="tooltip tooltip-top" data-tip="Context usage">
                      <span className="flex items-center gap-1">
                        <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        {Math.round(Number(message.metadata.ctx.used) / 1000)}k/
                        {Math.round(Number(message.metadata.ctx.size) / 1000)}k
                      </span>
                    </div>
                  )}
                </div>
              )}
              {message.metadata.tokensPerSecond && (
                <div className="tooltip tooltip-top" data-tip="Tokens per second">
                  <span className="flex items-center gap-1">
                    <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                    {message.metadata.tokensPerSecond.toFixed(1)} tok/s
                    <svg className="h-3 w-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </span>
                </div>
              )}
              {message.metadata.model && (
                <div className="tooltip tooltip-top" data-tip={`Model: ${message.metadata.model}`}>
                  <span className="badge badge-sm badge-outline">
                    {message.metadata.model}
                  </span>
                </div>
              )}
            </div>
          ) : (
            // Empty footer spacer for messages without metadata
            <span className="text-xs opacity-30">•</span>
          )}
          {/* Action buttons - visible on footer hover */}
          <div className="flex items-center gap-1 border-l border-base-300 pl-2 ml-2">
            <div className="tooltip tooltip-top" data-tip="Copy message">
              <button
                className="btn btn-ghost btn-xs btn-circle opacity-50 hover:opacity-100"
                onClick={() => copyToClipboard(message.content)}
              >
                <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              </button>
            </div>
            {/* Copy message meta info */}
            <div className="tooltip tooltip-top" data-tip="Copy message info to clipboard">
              <button
                className="btn btn-ghost btn-xs btn-circle opacity-50 hover:opacity-100"
                onClick={() => {
                  const parts = []
                  if (message.metadata?.model) parts.push('Model: ' + message.metadata.model)
                  if (message.metadata?.totalTimeMs) parts.push('Time: ' + Math.round(message.metadata.totalTimeMs) + 'ms')
                  if (message.metadata?.tokenCount) parts.push('Tokens: ' + message.metadata.tokenCount)
                  if (message.metadata?.tokensPerSecond) parts.push('Speed: ' + message.metadata.tokensPerSecond.toFixed(1) + ' tok/s')
                  if (cognitiveState?.latestTrace) {
                    const tr = cognitiveState.latestTrace.trace
                    if (tr) {
                      parts.push('')
                      parts.push('Pipeline Trace:')
                      if (tr.context_builder) parts.push('  Context: ' + tr.context_builder.strategy + ' (' + tr.context_builder.duration_ms + 'ms)')
                      if (tr.executor) parts.push('  Executor: ' + tr.executor.strategy + ' (' + tr.executor.duration_ms + 'ms)')
                      if (tr.memory_manager) parts.push('  Memory: ' + tr.memory_manager.strategy + ' (' + tr.memory_manager.duration_ms + 'ms)')
                      if (tr.response_formatter) parts.push('  Format: ' + tr.response_formatter.strategy + ' (' + tr.response_formatter.duration_ms + 'ms)')
                      parts.push('  Total: ' + (tr.total_duration_ms || 0) + 'ms')
                    }
                  }
                  copyToClipboard(parts.join('\n'))
                }}
              >
                <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                </svg>
              </button>
            </div>

          </div>
          {/* Cognitive pipeline indicator — only on last message */}
          {isLast && cognitiveState && showPipelineIndicators && (
            <div className="ml-2">
              {/* THE RENDER-SITE SETTLE (2026-09-02, the user's "it is still
                  running"): the bus pump (useTracePanel) clears isActive ONLY on
                  a trace_complete event — which can miss on the stream tail. The
                  2026-08-24 settle guarantee lives in the service's own state,
                  which the UI no longer reads. When no stream is running the
                  pipeline cannot be active — force the settle so the spinner
                  can't spin forever. */}
              <CognitiveIndicator
                cognitiveState={
                  // the NATURAL settle passes through untouched (trace_complete
                  // arrived — completed stage + latestTrace); only the STUCK
                  // state (bus still active with no stream) forces the settle.
                  isStreaming || !cognitiveState.isActive
                    ? cognitiveState
                    : { ...cognitiveState, isActive: false, executorStage: 'idle' }
                }
                compact
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/**
 * THE MEMO (the streaming-perf arc, Phase C).
 *
 * WHAT IT FIXES. During a stream the store replaces ONE message object and
 * leaves every other message's reference untouched (verified in Phase A —
 * agentStore.updateSessionMessage is a targeted replace). Without a memo the
 * whole list re-renders on every update, so every bubble re-parses and
 * re-highlights its full markdown — measured at 3 parses per update for a
 * 3-message list, and 256 main-thread blocks across a 39 s stream. With the
 * memo only the streaming bubble re-renders: 1 parse per update.
 *
 * WHY AN EXPLICIT COMPARATOR RATHER THAN THE DEFAULT SHALLOW ONE. The props a
 * bubble consults are not all message-shaped, and two of them are the kind of
 * thing a default comparison gets subtly wrong:
 *
 *   message                 - the identity key. Stable for a finished message,
 *                             new on every update for the streaming one.
 *   isStreaming             - selects the fold variant, so it must repaint ALL
 *                             bubbles when it flips (twice per turn).
 *   isLast                  - the pipeline indicator lives on the last message.
 *                             When a new message arrives the PREVIOUS last must
 *                             repaint to drop its indicator; without this it
 *                             would keep a spinner forever.
 *   cognitiveState          - passed ONLY to the last bubble (ResponseStream
 *                             does this deliberately: it changes on every trace
 *                             event, so giving it to all bubbles would defeat
 *                             the memo). Without it the "still running" settle
 *                             never repaints — the bug pinned by the test named
 *                             "REPAINTS when a settled cognitiveState arrives
 *                             late" in ResponseStream.test.tsx. It is named
 *                             rather than line-numbered on purpose: a line
 *                             number is a hand-computed reference to a file's
 *                             layout and drifts silently, and a comment pointing
 *                             at the wrong test is worse than one pointing at
 *                             none.
 *   showPipelineIndicators  - a setting; rarely changes, but it gates the
 *   ghostBubbles              indicator and the bubble classes, so they belong.
 *   speakState              - the play/pause/resume/stop state of the voice.
 *   activeKey               - SEE D1 ABOVE. Not React state in its own right,
 *                             so it MUST be compared or a voice switch leaves
 *                             the previous bubble showing controls for audio it
 *                             no longer owns.
 *   onExaApproval           - passed through to ApprovalCard.
 */
export default memo(MessageBubble, (prev, next) =>
  prev.message === next.message &&
  prev.isStreaming === next.isStreaming &&
  prev.isLast === next.isLast &&
  prev.cognitiveState === next.cognitiveState &&
  prev.showPipelineIndicators === next.showPipelineIndicators &&
  prev.ghostBubbles === next.ghostBubbles &&
  prev.speakState === next.speakState &&
  prev.activeKey === next.activeKey &&
  prev.onExaApproval === next.onExaApproval
)
