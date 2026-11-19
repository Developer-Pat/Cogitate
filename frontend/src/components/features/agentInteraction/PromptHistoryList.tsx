import { useState } from 'react'
import { useNotificationStore } from '@/stores/notificationStore'
import { usePromptHistoryStore, MAX_DISPLAYED } from '@/stores/promptHistoryStore'
import PortalTooltip from '@/components/ui/PortalTooltip'

/**
 * PromptHistoryList — the "History" tab's body. The user's own prompts.
 *
 * WHERE THE DATA COMES FROM (2026-09-15, corrected). The first pass DERIVED this list
 * from `currentSession.messages`. That was wrong, and the user's model was simpler:
 *
 *   "I thought you were getting them from the input user window.
 *    A straight copy to the history table."
 *
 * So the store is written on SEND and read here. Nothing derives, nothing filters by
 * session, and deleting is a real delete — there is no dismissed-set shadow state,
 * because there is finally something to delete FROM.
 *
 * THE DISPLAY IS THREE TIERS, because a prompt has no natural length:
 *
 *   ROW       ~60 chars  — enough to recognise which prompt it is
 *   TOOLTIP   ~500 chars — a few lines of the real text
 *   BEYOND    the buttons. Copy is the escape hatch for the rest.
 *
 * The third tier is the point: a tooltip holding a 4,000-character prompt is not
 * readable and cannot be kept in the viewport, so the tip stops at a sane length and
 * SAYS how much it is holding back.
 *
 * The tooltip is PortalTooltip, not a DaisyUI `data-tip`: this list lives inside the
 * same scroll containers that were clipping the session-name tips.
 */

/** Enough to recognise the prompt at a glance. */
const ROW_CHARS = 60
/** A few lines — past this the tip stops being readable. */
const TIP_CHARS = 500

interface PromptHistoryListProps {
  /** Put the prompt INTO the composer — never sends it. Optional: with no handler
      the button is hidden rather than rendered dead. */
  onUsePrompt?: (text: string) => void
}

/** Collapse a prompt to a single line so the row list stays scannable. */
function oneLine(s: string): string {
  return s.replace(/\s+/g, ' ').trim()
}

export default function PromptHistoryList({ onUsePrompt }: PromptHistoryListProps) {
  const addNotification = useNotificationStore((state) => state.addNotification)
  const allPrompts = usePromptHistoryStore((state) => state.prompts)
  const removePrompt = usePromptHistoryStore((state) => state.removePrompt)
  const clearAll = usePromptHistoryStore((state) => state.clearAll)

  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [confirmClearOpen, setConfirmClearOpen] = useState(false)

  // The store keeps the list ALPHABETICAL and deduped; we only bound how many are
  // DRAWN. Entries past the cut stay recorded, so a long history costs nothing until
  // it is scrolled — the cut takes the first hundred alphabetically.
  const shown = allPrompts.slice(0, MAX_DISPLAYED)

  const copy = async (text: string, id: string) => {
    // The fallback is the same one the session row-menu uses: the clipboard API needs
    // a secure context and a user gesture, and we are not always given both.
    const fallbackCopy = () => {
      const ta = document.createElement('textarea')
      ta.value = text
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      let ok = false
      try { ok = document.execCommand('copy') } catch { ok = false }
      document.body.removeChild(ta)
      return ok
    }
    let copied = false
    try {
      await navigator.clipboard.writeText(text)
      copied = true
    } catch {
      copied = fallbackCopy()
    }
    if (copied) {
      setCopiedId(id)
      window.setTimeout(() => setCopiedId((c) => (c === id ? null : c)), 1200)
      addNotification({ type: 'success', title: 'Prompt copied', message: `${text.length} characters on the clipboard`, duration: 1800 })
    } else {
      addNotification({ type: 'error', title: 'Copy failed', message: 'Could not access the clipboard.', duration: 3000 })
    }
  }

  const handleDelete = (id: string) => {
    removePrompt(id)
    addNotification({
      type: 'success',
      title: 'Prompt removed from history',
      message: 'The conversation is unchanged — only this list was tidied.',
      duration: 2400,
    })
  }

  const handleClearAll = () => {
    setConfirmClearOpen(false)
    clearAll()
    addNotification({
      type: 'success',
      title: 'History cleared',
      message: 'The conversation is unchanged — only this list was tidied.',
      duration: 2400,
    })
  }

  if (shown.length === 0) {
    return (
      <div className="p-6 text-center">
        <p className="text-sm text-base-content/60">No prompts in the history yet.</p>
        {/* Said plainly, because the list is now written ON SEND and does not reach
            back into sessions: a user looking for last week's prompts should learn
            here that the history starts when the feature did, not wonder if it broke. */}
        <p className="mt-1 text-xs text-base-content/40">
          Prompts are recorded as you send them.
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col">
      <ul className="divide-y divide-base-300">
        {shown.map((entry) => {
          const clean = oneLine(entry.text)
          const rowText = clean.length > ROW_CHARS ? clean.slice(0, ROW_CHARS - 1) + '…' : clean
          const tipText =
            clean.length > TIP_CHARS
              ? clean.slice(0, TIP_CHARS) + `\n\n… ${clean.length - TIP_CHARS} more characters — use Copy for the whole prompt.`
              : clean
          const isCopied = copiedId === entry.id

          return (
            <li key={entry.id} className="group px-3 py-2 hover:bg-base-200">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  {/* Partial display; the full prompt is one hover away. */}
                  <PortalTooltip content={tipText} side="bottom" maxWidth={460}>
                    <p className="cursor-default truncate text-sm text-left text-base-content/90">{rowText}</p>
                  </PortalTooltip>
                  <p className="mt-0.5 text-[11px] text-base-content/40">{entry.text.length} chars</p>
                </div>

                <div className="flex shrink-0 gap-1">
                  <div className="tooltip tooltip-left" data-tip={isCopied ? 'Copied' : 'Copy to clipboard'}>
                    <button
                      type="button"
                      onClick={() => copy(entry.text, entry.id)}
                      aria-label="Copy prompt to clipboard"
                      className="btn btn-xs btn-circle bg-base-100 hover:bg-base-200 border border-base-300"
                    >
                      {isCopied ? (
                        <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                        </svg>
                      ) : (
                        <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                        </svg>
                      )}
                    </button>
                  </div>

                  {/* CONDITIONAL: with no handler there is nothing to put the prompt
                      into, so the button is absent rather than present-and-dead. */}
                  {onUsePrompt && (
                    <div className="tooltip tooltip-left" data-tip="Copy to user input">
                      <button
                        type="button"
                        onClick={() => onUsePrompt(entry.text)}
                        aria-label="Copy prompt to user input"
                        className="btn btn-xs btn-circle bg-base-100 hover:bg-base-200 border border-base-300"
                      >
                        <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1" />
                        </svg>
                      </button>
                    </div>
                  )}

                  {/* THE TRASH, DIRECTLY (2026-09-17, the user's ask). This was a ⋮
                      dropdown holding exactly one item, on the reasoning that "a
                      destructive action should not sit one mis-click from Copy". The
                      user's call is the other way, and it is the better one here: the
                      menu charged a click for the row's ONLY hidden action, and the
                      delete is not actually dangerous — it removes the entry from this
                      list, the conversation is untouched, and the toast says so. So
                      nothing irreversible was one mis-click away either way, and the
                      cost was a hidden control. */}
                  <div className="tooltip tooltip-left" data-tip="Remove from history">
                    <button
                      type="button"
                      onClick={() => handleDelete(entry.id)}
                      aria-label="Remove this prompt from the history"
                      className="btn btn-xs btn-circle bg-base-100 hover:bg-base-200 border border-base-300 text-error"
                    >
                      <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
            </li>
          )
        })}
      </ul>

      {/* THE FOOTER. It acts on the whole list, so it does not belong in a row. */}
      <div className="mt-1 flex items-center justify-between border-t border-base-300 px-3 py-2">
        <span className="text-[11px] text-base-content/50">
          {allPrompts.length} prompt{allPrompts.length === 1 ? '' : 's'}
          {allPrompts.length > MAX_DISPLAYED ? ` (showing ${MAX_DISPLAYED})` : ''}
        </span>
        <div className="tooltip tooltip-left" data-tip="Remove every prompt from this history">
          <button
            type="button"
            onClick={() => setConfirmClearOpen(true)}
            className="btn btn-ghost btn-xs text-error"
          >
            {/* "Clear all" SAID TOO MUCH (2026-09-15). The message center has a
                button with that exact label, and it clears something entirely
                different — the user pressed one expecting the other, then wondered
                why the bell's badge had not moved. Naming this for what it clears
                costs nothing and removes the collision. */}
            Clear history
          </button>
        </div>
      </div>

      {/* CONFIRMATION — DaisyUI v5 requires the <dialog className="modal"> wrapper
          (the project's convention), and a destructive action gets a confirm. */}
      <dialog className="modal" open={confirmClearOpen}>
        <div className="modal-box">
          <h3 className="font-bold text-lg">Clear this history?</h3>
          <p className="py-4">
            All {allPrompts.length} prompt{allPrompts.length === 1 ? '' : 's'} will be
            cleared from this history. The conversation is not changed — only this list is.
          </p>
          <div className="modal-action">
            <button className="btn btn-ghost" onClick={() => setConfirmClearOpen(false)}>
              Cancel
            </button>
            <button className="btn btn-error" onClick={handleClearAll}>
              Clear history
            </button>
          </div>
        </div>
        <form method="dialog" className="modal-backdrop">
          <button onClick={() => setConfirmClearOpen(false)}>close</button>
        </form>
      </dialog>
    </div>
  )
}

export { ROW_CHARS, TIP_CHARS }
