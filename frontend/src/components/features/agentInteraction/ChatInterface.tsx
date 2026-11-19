import { useState, useRef, useEffect, memo } from 'react'
import { useUIStore } from '@/stores/uiStore'
import MacroKeyboard from './MacroKeyboard'
import LoadingIndicator from './LoadingIndicator'
import AttachmentPreview from './AttachmentPreview'
import { BadgeButton } from '@/components/ui/BadgeButton'
import { Paperclip, PanelLeft, PanelRight, PanelsLeftRight, ChevronsDownUp, ChevronsUpDown } from 'lucide-react'
import { attachmentService } from '@/services/domain/AttachmentService'
import { useSystemMacrosStore } from '@/stores/macroSetsStore'
import { useNotificationStore } from '@/stores/notificationStore'
import { frontendLoggingService } from '@/services/frontendLoggingService'

interface ChatInterfaceProps {
  onSendMessage: (message: string, attachments?: File[]) => void
  isStreaming: boolean
  disabled?: boolean
  placeholder?: string
  onStopStreaming?: () => void
  onToggleRightPanel?: () => void
  // THE DESELECT + TOSS CONTROLS (2026-09-11, the user's ask): the
  // agent-chat passes both; the Exa chat passes neither, so the pair
  // stays hidden there.
  // DEPRECATED(2026-09-15): the Deselect button moved to SessionManager's header.
  // Kept in the interface so the page's existing pass-through still type-checks, and
  // commented here per the deprecate-don't-delete instruction. Remove with the block.
  onDeselectSession?: () => void
  onTossSession?: () => void
  agentId?: string
  sessionId?: string
  // THE EXA-ONLY (2026-08-28, the user's ask): the ACP-actions +
  // the prompt-history live in the INPUT toolbar (just left of the
  // right-panel toggle!) — the agent-chat doesn't pass them → the
  // block's hidden!
  exaConnected?: boolean
  onExaAction?: (prompt: string) => void
  exaPromptHistory?: string[]
  /** THE HISTORY TAB FEEDS THE COMPOSER (2026-09-15, the user's ask). The panel's
      "copy into the message box" sets this through the page; the effect below
      appends it to the input. NOT a send — the user still presses Send. */
  pendingPrompt?: string | null
  /** Called once the pending prompt has been taken, so the page can clear it —
      without this the same prompt would re-append on every re-render. */
  onPendingPromptConsumed?: () => void
}

function ChatInterface({
  onSendMessage,
  isStreaming,
  disabled = false,
  placeholder = "Type your message...",
  onStopStreaming,
  onToggleRightPanel,
  // DEPRECATED(2026-09-15): not destructured — the Deselect button moved to
  // SessionManager's header. It stays in the interface above so the page's existing
  // pass-through remains legal, and to keep the removal greppable.
  // onDeselectSession,
  onTossSession,
  sessionId,
  agentId,
  exaConnected,
  onExaAction,
  exaPromptHistory,
  pendingPrompt,
  onPendingPromptConsumed,
}: ChatInterfaceProps) {
  const toggleSidebar = useUIStore(state => state.toggleSidebar)
  const [inputValue, setInputValue] = useState('')
  // THE COLLAPSE-ALL TOGGLE STATE (2026-09-01, the user's
  // 'the toggle does not change directions'): the one-shot became
  // a real toggle — the collapse flips the chevron, the second
  // click expands all back.
  const [responsesCollapsed, setResponsesCollapsed] = useState(false)

  const { metaTopics, selectedMetaTopicId, selectMetaTopic, macroSets: macros, aKeysMetaTopicId, setSurface, loadMetaTopics, isLoadingMetaTopics, loadAllMacros } = useSystemMacrosStore()

  // THE SURFACE (2026-09-03, the akeys Phase 5a): this ChatInterface
  // renders for BOTH the agent chat and the Exa page. Which surface
  // the F/A state belongs to is derived from the agentId — the store
  // re-resolves its selection from that surface's keys.
  const surface = agentId === 'exa' ? 'exa' : 'agent'
  useEffect(() => {
    setSurface(surface)
  }, [surface, setSurface])

  // Auto-select first agent topic on mount and load macros
  useEffect(() => {
    if (metaTopics.length === 0 && !isLoadingMetaTopics) {
      loadMetaTopics()
    }
    loadAllMacros()
    if (metaTopics.length > 0 && selectedMetaTopicId === null) {
      const firstAgent = metaTopics.find(mt => mt.namespace === 'agent')
      if (firstAgent) selectMetaTopic(firstAgent.id)
    }
  }, [metaTopics, selectedMetaTopicId, loadMetaTopics, isLoadingMetaTopics, selectMetaTopic, loadAllMacros])
  const [attachedFiles, setAttachedFiles] = useState<File[]>([])
  const [uploadProgress, setUploadProgress] = useState<number[]>([])
  const [justSent, setJustSent] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`
    }
  }, [inputValue])

  // THE HISTORY → COMPOSER APPEND (2026-09-15, the user's ask).
  // The panel hands a prompt over through the page; we APPEND it (matching how
  // the macros insert) and then tell the page it has been taken, so the same
  // prompt cannot re-append on the next render. It never sends — the user does.
  useEffect(() => {
    if (!pendingPrompt) return
    setInputValue((prev) => (prev ? `${prev}\n\n${pendingPrompt}` : pendingPrompt))
    onPendingPromptConsumed?.()
    // Focus so the user can edit or send straight away; the cursor work is done
    // after paint, once the textarea has its new value.
    window.setTimeout(() => {
      const el = textareaRef.current
      if (el && !disabled) {
        el.focus()
        el.setSelectionRange(el.value.length, el.value.length)
      }
    }, 0)
  }, [pendingPrompt, onPendingPromptConsumed, disabled])

  // Restore focus after send clears the input
  useEffect(() => {
    if (justSent) {
      const timer = setTimeout(() => {
        if (textareaRef.current) {
          textareaRef.current.focus()
        }
        setJustSent(false)
      }, 0)
      return () => clearTimeout(timer)
    }
  }, [justSent])

  // Restore focus when streaming completes
  useEffect(() => {
    if (!isStreaming) {
      const timer = setTimeout(() => {
        if (textareaRef.current && !disabled) {
          textareaRef.current.focus()
        }
      }, 100)
      return () => clearTimeout(timer)
    }
  }, [isStreaming, disabled])

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return

    // Validate files
    const validFiles: File[] = []
    const errors: string[] = []

    Array.from(files).forEach(file => {
      const validation = attachmentService.validateFile(file)
      if (validation.valid) {
        validFiles.push(file)
      } else {
        errors.push(`${file.name}: ${validation.error}`)
      }
    })

    if (errors.length > 0) {
      console.error('File validation errors:', errors)
      // Could show a toast notification here
      alert(errors.join('\n'))
    }

    if (validFiles.length > 0) {
      setAttachedFiles(prev => [...prev, ...validFiles])
      setUploadProgress(prev => [...prev, ...new Array(validFiles.length).fill(0)])
    }

    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const handleRemoveAttachment = (index: number) => {
    setAttachedFiles(prev => prev.filter((_, i) => i !== index))
    setUploadProgress(prev => prev.filter((_, i) => i !== index))
  }

  const handleSummarizeAttachment = (index: number) => {
    const file = attachedFiles[index]
    if (!file) return
    setInputValue(prev => {
      const prefix = prev ? `${prev}\n\n` : ''
      return `${prefix}Please summarize the attached file "${file.name}" in detail.`
    })
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    const trimmedValue = inputValue.trim()
    if ((trimmedValue || attachedFiles.length > 0) && !disabled && !isStreaming) {
      onSendMessage(trimmedValue, attachedFiles.length > 0 ? attachedFiles : undefined)
      setInputValue('')
      setAttachedFiles([])
      setUploadProgress([])
      setJustSent(true)

      // Reset textarea height
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto'
      }
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      e.stopPropagation()  // Stop event from bubbling up
      handleSubmit(e)  // Call handleSubmit directly
    }
  }

  const handleMacroSelect = (macroText: string) => {
    setInputValue(prev => prev + (prev ? ' ' : '') + macroText)
  }

  const handleClearInput = () => {
    setInputValue('')
    setAttachedFiles([])
    setUploadProgress([])
    // Restore focus after clearing
    setTimeout(() => {
      if (textareaRef.current && !disabled) {
        textareaRef.current.focus()
      }
    }, 0)
  }

  const canSend = (inputValue.trim() || attachedFiles.length > 0) && !disabled && !isStreaming

  // THE EXA ACP TOOLBAR (2026-09-03, the user's ask): the three ACP
  // controls (commands doc + ACP + history) render AFTER the A-Key
  // selector on the keyboard row (the MacroKeyboard afterAKeys slot)
  // — moved here from the lower toolbar row so the Exa page's input
  // controls group with the keys, spaced by the slot.
  const exaToolbar = (
                      <>
                        {/* THE COMMANDS DOC (2026-08-30, the user's
                            ask): the info button opens the wiki
                            dev-note in a NEW TAB — the quick
                            reference (the top commands + the
                            Exa-vs-Hermes + the resets). */}
                        <div className="tooltip tooltip-top" data-tip="Exa commands — quick reference (opens in a new tab)">
                          <button
                            type="button"
                            className="rounded-full p-1 text-xs font-medium text-readout hover:text-primary hover:bg-primary/10 transition-all"
                            aria-label="Exa commands reference"
                            onClick={() => window.open('/wiki/dev-notes/exa-commands', '_blank', 'noopener')}
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                          </button>
                        </div>
                        <div
                          className="tooltip tooltip-top"
                          data-tip={exaConnected ? 'ACP actions' : 'ACP actions — Exa is offline (reconnecting)'}
                        >
                          <div className="dropdown dropdown-end dropdown-top">
                            <div
                              tabIndex={0}
                              role="button"
                              className={`pill-button pill-button--normal cursor-pointer ${
                                exaConnected
                                  ? 'bg-primary/20 text-primary border border-primary/30 hover:bg-primary/30'
                                  : 'bg-base-200 text-disabled border border-base-300 opacity-60'
                              }`}
                            >
                              ⚡ ACP
                            </div>
                            <ul tabIndex={0} className="dropdown-content menu bg-base-100 border border-base-300 rounded-box shadow-lg z-50 w-60 p-1 max-h-80 overflow-y-auto">
                              {[
                                // THE CURATED SET (2026-08-30, the
                                // user's 6-commands question): the
                                // hermes registry has dozens — this
                                // is the useful window; the /new
                                // (the session reset) + the /memory
                                // subcommands are now here too.
                                { label: '/help', prompt: '/help' },
                                { label: '/new', prompt: '/new' },
                                { label: '/undo', prompt: '/undo' },
                                { label: '/status', prompt: '/status' },
                                { label: '/memory', prompt: '/memory' },
                                { label: '/memory pending', prompt: '/memory pending' },
                                { label: '/memory approval off', prompt: '/memory approval off' },
                                { label: '/skills', prompt: '/skills' },
                                { label: '/model', prompt: '/model' },
                                { label: '/voice', prompt: '/voice' },
                                { label: '/compress', prompt: '/compress' },
                                { label: '/usage', prompt: '/usage' },
                                { label: '/sessions', prompt: '/sessions' },
                                { label: '/config', prompt: '/config' },
                              ].map((a) => (
                                <li key={a.label}>
                                  <button
                                    type="button"
                                    className="text-xs py-1.5 font-mono"
                                    disabled={!exaConnected || isStreaming}
                                    onClick={() => onExaAction?.(a.prompt)}
                                  >
                                    {a.label}
                                  </button>
                                </li>
                              ))}
                            </ul>
                          </div>
                        </div>

                        <div className="tooltip tooltip-top" data-tip="Prompt history">
                          <div className="dropdown dropdown-end dropdown-top">
                            <div
                              tabIndex={0}
                              role="button"
                              className="rounded-full px-3 py-1 text-xs font-medium bg-primary/20 text-primary border border-primary/30 hover:bg-primary/30 transition-all cursor-pointer"
                            >
                              History
                            </div>
                            <ul tabIndex={0} className="dropdown-content menu bg-base-100 border border-base-300 rounded-box shadow-lg z-50 w-72 p-1 max-h-64 overflow-y-auto">
                              {!exaPromptHistory || exaPromptHistory.length === 0 ? (
                                <li>
                                  <span className="text-xs py-1.5 text-readout">No prompts yet</span>
                                </li>
                              ) : (
                                exaPromptHistory.map((p, i) => (
                                  <li key={`${i}-${p.slice(0, 12)}`}>
                                    <button
                                      type="button"
                                      className="text-xs py-1.5 truncate"
                                      disabled={!exaConnected}
                                      onClick={() => onExaAction?.(p)}
                                    >
                                      {p}
                                    </button>
                                  </li>
                                ))
                              )}
                            </ul>
                          </div>
                        </div>
                      </>
  )

  // THE INPUT WIDGET WRAPPER (2026-09-03, the user's ask — the
  // black box): the wrapper previously wore the SYSTEM-BUBBLE color
  // (a message token = near-black in dark) as a full-width band
  // behind the input. It is a PAGE-LEVEL surface, not a bubble —
  // the band is gone (transparent), only the top hairline + padding
  // remain; the input widget's own rounded box carries the surface.
  // Both the chat + the Exa pages share this.
  return (
    <div className="border-t border-base-300/30 p-2">
      <div className="max-w-[80%] mx-auto">
        {/* Attachment Preview (if files are attached) */}
            {attachedFiles.length > 0 && (
              <AttachmentPreview
                files={attachedFiles}
                onRemove={handleRemoveAttachment}
                onSummarize={handleSummarizeAttachment}
                uploadProgress={uploadProgress}
              />
            )}

            {/* Input Container with buttons inside */}
            <div className="border border-[var(--chat-input-border)] rounded-2xl px-3 py-2 bg-[var(--chat-input-bg)]">
              {/* Message Input */}
              <div className="form-control mb-1">
                <textarea
                  ref={textareaRef}
                  className="textarea w-full resize-none min-h-[50px] max-h-[200px] rounded-xl border-0 focus:outline-none focus:ring-0 p-0 text-[var(--chat-input-text)] bg-transparent"
                  placeholder={placeholder}
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyDown={handleKeyDown}
                  disabled={disabled || isStreaming}
                  rows={2}
                />
              </div>

              {/* Controls inside the input box */}
              <div className="flex flex-col gap-1">
                {/* Row 1: Macro Keyboard left, Send/Clear right */}
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1">
                    <MacroKeyboard
                      onMacroSelect={handleMacroSelect}
                      disabled={disabled || isStreaming}
                      compact={true}
                      metaTopics={metaTopics}
                      selectedMetaTopicId={selectedMetaTopicId}
                      selectMetaTopic={selectMetaTopic}
                      macros={macros}
                      aKeysMetaTopicId={aKeysMetaTopicId}
                      afterAKeys={agentId === 'exa' && onExaAction ? exaToolbar : null}
                    />
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <div className="flex items-center gap-1">
                    {/* Character Count */}
                    {inputValue.length > 0 && (
                      <span className="text-xs text-readout mr-1">
                        {inputValue.length}
                      </span>
                    )}
                    {/* Clear Input Button */}
                    {(inputValue || attachedFiles.length > 0) && (
                      <div className="tooltip tooltip-top" data-tip="Clear input and attachments">
                        <BadgeButton
                          size="sm"
                          onClick={handleClearInput}
                          aria-label="Clear input and attachments"
                          className="text-error"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </BadgeButton>
                      </div>
                    )}
                    {/* Send Button (when not streaming) */}
                    {!isStreaming && (
                      <div className="tooltip tooltip-top" data-tip="Press Enter to send, Shift + Enter for new line">
                        <button
                          type="button"
                          onClick={handleSubmit}
                          disabled={!canSend}
                          className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
                            canSend
                              ? 'bg-primary text-primary-content hover:bg-primary-focus'
                              : 'bg-base-300 text-disabled cursor-not-allowed'
                          }`}
                        >
                          Send
                        </button>
                      </div>
                    )}
                    {/* Stop Button (when streaming) */}
                    {isStreaming && onStopStreaming && (
                      <div className="tooltip tooltip-top" data-tip="Stop generating response">
                        <button
                          type="button"
                          className="btn btn-outline btn-error btn-sm"
                          onClick={onStopStreaming}
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                          Stop
                        </button>
                      </div>
                    )}
                    {/* Loading Indicator (when streaming) */}
                    {isStreaming && (
                      <div className="flex items-center gap-2 text-sm text-readout">
                        <LoadingIndicator size="sm" color="oklch(var(--p))" />
                        <span>Generating...</span>
                      </div>
                    )}
                  </div>
                  {/* THE UNDER-SEND CONTROLS (2026-09-03, the user's
                      ask): the fold + layout buttons right-justified
                      under the Send button. */}
                  <div className="flex items-center gap-1">
                    {/* DEPRECATED(2026-09-15) — THE DESELECT BUTTON, MOVED OUT.

                        It lived here as a text button in the under-Send row (the user's
                        original ask, 2026-09-11: "sometimes I want to select nothing.
                        That is a gap I have noticed"). On 2026-09-15 the user asked for
                        it to MOVE to the panel header — the slot the redundant gear
                        button occupied — and to become an ICON.

                        It now lives in SessionManager (grep `onDeselectSession`), which
                        owns the header row. The page passes the same handler to both, so
                        nothing was re-implemented, only relocated.

                        Kept commented per the user's "deprecate code for later removal;
                        mark any new unused code as deprecated so we can find it with a
                        grep" instruction.

                    {onDeselectSession && (
                      <div className="tooltip tooltip-top" data-tip="Deselect — work with no session selected">
                        <button
                          type="button"
                          onClick={() => onDeselectSession()}
                          disabled={isStreaming}
                          aria-label="Deselect current session"
                          className={`px-2 py-1 text-xs font-semibold rounded-lg transition-colors ${
                            isStreaming
                              ? 'bg-base-300 text-disabled cursor-not-allowed'
                              : 'bg-base-200 text-base-content hover:bg-base-300'
                          }`}
                        >
                          Deselect
                        </button>
                      </div>
                    )}
                    */}
                    {/* THE TOSS BUTTON (2026-09-11, the user's ask — "throw
                        chats away quickly and start a new chat with one button
                        push"). RENAMED Kill -> Toss (2026-09-15): "We toss away
                        a trivial chat session" — same behavior, softer word.
                        Deletes this session and opens a fresh one with the SAME
                        agent. No confirm and no toast: the new blank session is
                        its own confirmation, and the hook logs what was tossed.
                        Disabled mid-stream — tossing a live turn would race the
                        in-flight write. */}
                    {onTossSession && (
                      <div className="tooltip tooltip-top" data-tip="Toss — delete this session and start a new one with the same agent">
                        <button
                          type="button"
                          onClick={() => onTossSession()}
                          disabled={isStreaming}
                          aria-label="Delete this session and start a new one with the same agent"
                          className="px-2 py-1 text-xs font-semibold rounded-lg transition-colors bg-base-200 text-error hover:bg-base-300"
                        >
                          Toss
                        </button>
                      </div>
                    )}
                    {/* THE COLLAPSE-RESPONSES BUTTON (2026-09-01, the user's
                        user's ask — the input widget, LEFT of the
                        right-panel toggle): collapses every response
                        fold EXCEPT the last one. DOM-driven — the
                        agent-chat + the Exa pages both render the
                        .report-fold elements. */}
                    <div className="tooltip tooltip-top" data-tip={responsesCollapsed ? 'Expand long responses' : 'Collapse long responses.'}>
                      <BadgeButton
                        size="sm"
                        className="text-sm"
                        aria-label={responsesCollapsed ? 'Expand long responses' : 'Collapse long responses'}
                        onClick={() => {
                          const folds = Array.from(
                            document.querySelectorAll<HTMLDetailsElement>('.report-fold'),
                          )
                          // THE DOM-DERIVED DIRECTION (2026-09-01,
                          // the user's 'it doesn't ever un-collapse'):
                          // the component state RESET on re-render, so
                          // the second click re-ran the collapse
                          // branch ('All responses already collapsed').
                          // The folds' ACTUAL open-state decides now —
                          // any collapsed fold = the expand direction.
                          const anyCollapsed = folds.some((f) => !f.open)
                          if (anyCollapsed) {
                            // THE EXPAND SIDE: all the folds open.
                            folds.forEach((f) => {
                              f.open = true
                            })
                            setResponsesCollapsed(false)
                            useNotificationStore.getState().addInfo(
                              `Expanded ${folds.length} response${folds.length === 1 ? '' : 's'}`,
                              '',
                            )
                            frontendLoggingService.info('ChatInterface:expand-all', 'Expand-all clicked', { total: folds.length })
                            return
                          }
                          const opened = folds.filter((f) => f.open)
                          const collapsed = opened.slice(0, -1).filter((f) => {
                            f.open = false
                            return true
                          }).length
                          // THE FEEDBACK (2026-09-01, the user's
                          // 'clicking does nothing — no message'): the
                          // silent-DOM-mutation broke the no-silent-
                          // failures rule — the result toasts + the
                          // frontend log trails it.
                          if (collapsed > 0) {
                            setResponsesCollapsed(true)
                            useNotificationStore.getState().addInfo(
                              `Collapsed ${collapsed} response${collapsed === 1 ? '' : 's'} — the latest kept`,
                              '',
                            )
                            frontendLoggingService.info('ChatInterface:collapse-all', 'Collapse-all clicked', { collapsed, total: folds.length })
                          } else {
                            useNotificationStore.getState().addInfo(
                              folds.length === 0
                                ? 'No long responses to collapse'
                                : 'All responses already collapsed',
                              '',
                            )
                            frontendLoggingService.info('ChatInterface:collapse-all', 'Collapse-all clicked (none open)', { collapsed: 0, total: folds.length })
                          }
                        }}
                      >
                        {/* THE ICON (2026-09-01, the user's ask — 'a
                            nice icon and a better tool tip'): the
                            action-affordance — the collapsed state
                            shows the EXPAND glyph, the open state the
                            COLLAPSE glyph (the text label's gone). */}
                        {responsesCollapsed ? (
                          <ChevronsUpDown className="w-4 h-4" aria-hidden="true" />
                        ) : (
                          <ChevronsDownUp className="w-4 h-4" aria-hidden="true" />
                        )}
                      </BadgeButton>
                    </div>

                    {/* THE LAYOUT FLYOUT (2026-09-01, the user's
                        ask): ONE glyph replaces the old right-panel
                        toggle — the three layout actions (the right
                        panel, the left navigation, the theater mode)
                        in one flyout. The house's flyouts OPEN UP +
                        the end-aligned (the input widget's bottom
                        edge). The items disable when the host page
                        lacks the handler (the Exa's sessions panel). */}
                    <div className="dropdown dropdown-end dropdown-top">
                      <div tabIndex={0} role="button" aria-label="Layout controls" className="tooltip tooltip-top" data-tip="Layout">
                        <BadgeButton size="sm" className="text-sm">
                          <PanelsLeftRight className="w-4 h-4" />
                        </BadgeButton>
                      </div>
                      <ul tabIndex={0} className="dropdown-content menu bg-[var(--flyout-panel-bg)] border border-[var(--flyout-panel-border)] text-[var(--flyout-panel-text)] rounded-box shadow-lg w-56 z-50 p-2">
                        <li>
                          <button
                            type="button"
                            disabled={!onToggleRightPanel}
                            className="flex items-center gap-2 text-sm disabled:opacity-40"
                            onClick={(e) => { e.stopPropagation(); onToggleRightPanel?.() }}
                          >
                            <PanelRight className="w-4 h-4" />
                            Toggle sessions panel
                          </button>
                        </li>
                        <li>
                          <button
                            type="button"
                            className="flex items-center gap-2 text-sm"
                            onClick={(e) => { e.stopPropagation(); toggleSidebar() }}
                          >
                            <PanelLeft className="w-4 h-4" />
                            Toggle navigation
                          </button>
                        </li>
                      </ul>
                    </div>
                  </div>
                </div>
                </div>
                </div>

                {/* Row 2: Action buttons — THE STANDALONE TOPIC
                    SELECTOR IS GONE (2026-09-03, the akeys Phase 5b):
                    its job moved onto the macro keyboard row — the
                    bank-attached icon selectors (F after M5, A beside
                    the A keys) select directly + persist. */}
                <div className="flex items-center justify-between gap-2">
                  {/* Right group: attachment, sessions toggle */}
                  <div className="flex items-center gap-1">
                    {/* Attachment Button */}
                    {!!sessionId && (
                      <div className="tooltip tooltip-top" data-tip="Attach file">
                        <BadgeButton 
                          size="sm" 
                          onClick={() => fileInputRef.current?.click()} 
                          aria-label="Attach file"
                          className={attachedFiles.length > 0 ? 'text-primary' : ''}
                        >
                          <Paperclip className="w-4 h-4" />
                          {attachedFiles.length > 0 && (
                            <span className="text-[10px] ml-0.5">{attachedFiles.length}</span>
                          )}
                        </BadgeButton>
                      </div>
                    )}

                    {/* Hidden file input */}
                    <input
                      ref={fileInputRef}
                      type="file"
                      multiple
                      accept=".md,.txt,.py,.json,.csv,.yaml,.yml,.pdf,.docx,.xlsx,.png,.jpg,.jpeg,.gif,.svg"
                      onChange={handleFileSelect}
                      style={{ display: 'none' }}
                      tabIndex={-1}
                    />



                  </div>
                </div>      </div>
    </div>
    </div>
  )
}

// Memoize to prevent re-renders when parent (AgentInteraction) re-renders
// due to message updates during streaming. ChatInterface uses local useState
// for inputValue, so it should only re-render when its own state or props change.
export default memo(ChatInterface, (prevProps, nextProps) => {
  const isStreamingSame = prevProps.isStreaming === nextProps.isStreaming
  const disabledSame = prevProps.disabled === nextProps.disabled
  const placeholderSame = prevProps.placeholder === nextProps.placeholder
  const agentIdSame = prevProps.agentId === nextProps.agentId
  const sessionIdSame = prevProps.sessionId === nextProps.sessionId
  const onSendMessageSame = prevProps.onSendMessage === nextProps.onSendMessage
  const onStopStreamingSame = prevProps.onStopStreaming === nextProps.onStopStreaming
  const onToggleRightPanelSame = prevProps.onToggleRightPanel === nextProps.onToggleRightPanel

  return (
    isStreamingSame &&
    disabledSame &&
    placeholderSame &&
    agentIdSame &&
    sessionIdSame &&
    onSendMessageSame &&
    onStopStreamingSame &&
    onToggleRightPanelSame
  )
})