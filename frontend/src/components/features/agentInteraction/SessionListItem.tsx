import { useRef, useEffect, useState } from 'react'
import { useNotificationStore } from '@/stores/notificationStore'
import type { ConversationSession } from '@/types/agentInteraction'
import { getTruncatedSessionTitle } from '@/utils/agentNameUtils'
import PortalTooltip from '@/components/ui/PortalTooltip'

interface SessionListItemProps {
  session: ConversationSession
  isActive: boolean
  isRenaming: boolean
  renameValue: string
  onSelect: () => void
  onDelete: () => void
  onRenameStart: () => void
  onRenameSave: () => void
  onRenameCancel: () => void
  onRenameChange: (value: string) => void
  onSmartRename?: () => void
  requireDeleteConfirm?: boolean
  isLoading?: boolean
  isBulkDeleteMode?: boolean
  isSelected?: boolean
  onToggleSelect?: () => void
}

export default function SessionListItem({
  session,
  isActive,
  isRenaming,
  renameValue,
  onSelect,
  onDelete,
  onRenameStart,
  onRenameSave,
  onRenameCancel,
  onRenameChange,
  onSmartRename,
  requireDeleteConfirm = true,
  isLoading = false,
  isBulkDeleteMode = false,
  isSelected = false,
  onToggleSelect = () => {}
}: SessionListItemProps) {
  const addNotification = useNotificationStore((state) => state.addNotification)
  const inputRef = useRef<HTMLInputElement>(null)
  const deleteModalRef = useRef<HTMLDialogElement>(null)
  // THE ⋮ ROW-MENU STATE (2026-08-22, user): the per-row actions
  // beyond the rename live in the three-dot dropdown — Copy + Delete
  // (and the manual Edit), mirroring the panel's Actions dropdown.
  const [showRowMenu, setShowRowMenu] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  // Focus input when renaming starts
  useEffect(() => {
    if (isRenaming && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select()
    }
  }, [isRenaming])

  // Handle delete confirmation modal
  useEffect(() => {
    if (showDeleteConfirm && deleteModalRef.current) {
      deleteModalRef.current.showModal()
    }
  }, [showDeleteConfirm])


  return (
    <div
      className={`px-3 py-2 cursor-pointer transition-colors relative ${
        isActive
          ? 'bg-primary/10 border-l-4 border-primary'
          : 'hover:bg-base-200'
      } ${isLoading ? 'opacity-50 pointer-events-none' : ''} ${
        isBulkDeleteMode ? 'pl-10' : ''
      }`}
      onClick={(e) => {
        e.stopPropagation()
        if (isLoading) return
        if (isBulkDeleteMode) {
          onToggleSelect()
        } else {
          onSelect()
        }
      }}
    >
      {/* Bulk Delete Checkbox */}
      {isBulkDeleteMode && (
        <input
          type="checkbox"
          checked={isSelected}
          onChange={(e) => {
            e.stopPropagation()
            onToggleSelect()
          }}
          onClick={(e) => e.stopPropagation()}
          className="checkbox checkbox-sm absolute left-2 top-1/2 -translate-y-1/2 z-10 checkbox-primary"
        />
      )}
      {isRenaming ? (
        // Rename Mode
        <div className="space-y-2" onClick={(e) => e.stopPropagation()}>
          <input
            ref={inputRef}
            type="text"
            value={renameValue}
            onChange={(e) => onRenameChange(e.target.value)}
            className="input input-bordered input-sm w-full rounded-[var(--form-input-radius)] px-[var(--form-input-padding)] bg-[var(--form-input-bg)] border-[var(--form-input-border)] text-[var(--form-input-text)] focus:border-[var(--form-input-focus-border)] transition-all duration-[var(--button-transition)]"
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                onRenameSave()
              } else if (e.key === 'Escape') {
                onRenameCancel()
              }
            }}
          />
          <div className="flex gap-2">
            <button
              onClick={(e) => {
                e.stopPropagation()
                onRenameSave()
              }}
              className="btn btn-primary btn-xs flex-1 rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
            >
              Save
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation()
                onRenameCancel()
              }}
              className="btn btn-neutral btn-ghost btn-xs flex-1"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        // Display Mode - Simplified with tooltip
        <div className="flex items-center justify-between gap-2 group">
          {isLoading && (
            <div className="absolute inset-0 flex items-center justify-center bg-base-100/50 z-10">
              <span className="loading loading-spinner loading-sm"></span>
            </div>
          )}
          <div className="flex-1 min-w-0">
            {/* THE STANDARD DAISYUI TOOLTIP (2026-08-22, user): a SHORT
                single-line tip — the full session title. The old custom
                hover box (title/agent/messages/updated, 4 lines) is gone:
                DaisyUI tooltips are short tips; the metadata box was not
                the standard pattern. The full title is what the truncated
                display hides. */}
            {/* THE FULL TITLE ON HOVER (2026-09-15, the user's ask: "the session
                titles are ok as they are... the work around is the tooltip that
                shows the full title on hover").

                The DISPLAY IS UNCHANGED — still getTruncatedSessionTitle(…, 28).
                Only the tip changed: this was a DaisyUI `div.tooltip` whose
                `::before` carried the correct text but was CLIPPED by the panel's
                scroll ancestors, so it never appeared. PortalTooltip renders
                outside that tree. */}
            <PortalTooltip content={session.title} side="bottom">
              <h3 className="font-medium text-sm truncate text-left cursor-default">
                {/* THE SHORTER TITLE (2026-08-22, user): 28 chars — the
                    longer titles overlapped the action buttons on hover
                    (the buttons fade in at opacity-0 group-hover). The
                    eye button's tooltip + its toast carry the full info. */}
                {getTruncatedSessionTitle(session.title, 28)}
              </h3>
            </PortalTooltip>
          </div>

          {/* Action Buttons */}
          <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
            {/* THE EYE (2026-08-22, user): a view button BEFORE the rename —
                its tooltip shows the FULL session title (the row title is a
                fixed-length truncation). A button trigger renders reliably
                (the h3 tooltip was invisible). */}
            <div className="tooltip tooltip-left" data-tip={session.title}>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  // THE EYE'S FUNCTION (2026-08-22, user): a toast with the
                  // pertinent session info — a TALLER, formatted layout
                  // (multi-line via \n + whitespace-pre-line) + a link to
                  // the Sessions page (the toaster supports actions).
                  addNotification({
                    type: 'info',
                    title: session.title,
                    message: [
                      `Agent: ${session.agentId ? session.agentId : 'Exa'}`,
                      // THE COUNT COMES FROM THE API (2026-09-15). It used to be
                      // `session.messages?.length ?? 0`, which was 0 for every
                      // session not yet opened (messages are lazy-loaded) and a
                      // STALE value for the open one — so deleting every message
                      // left the toast still reporting the old number.
                      `Messages: ${session.message_count ?? session.messages?.length ?? 0}`,
                      `Updated: ${session.updatedAt ? new Date(session.updatedAt).toLocaleString() : '—'}`,
                    ].join('\n'),
                    duration: 8000,
                    action: {
                      // EXPLICIT NAVIGATION (2026-08-22, user): the label
                      // says we're LEAVING this page (no surprise
                      // navigation), and the link carries the session id
                      // so the Sessions page opens WITH this session.
                      label: 'Go to Sessions page',
                      href: `/sessions?session=${encodeURIComponent(session.id)}`,
                    },
                  })
                }}
                className="btn btn-xs btn-circle bg-base-100 hover:bg-base-200 border border-base-300 shadow-md transition-all duration-[var(--button-transition)]"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                </svg>
              </button>
            </div>
            {/* THE SMART RENAME (2026-08-22, user): the edit button is now
                a rename button — one click generates a title from the FULL
                session conversation (the local title service). The inline
                manual editor stays for tweaks (triggered by the title). */}
            <div className="tooltip tooltip-left" data-tip="Rename">
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  if (onSmartRename) {
                    onSmartRename()
                  } else {
                    onRenameStart()
                  }
                }}
                className="btn btn-xs btn-circle bg-base-100 hover:bg-base-200 border border-base-300 shadow-md transition-all duration-[var(--button-transition)]"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
              </button>
            </div>
            {/* THE ⋮ ROW-MENU (2026-08-22, user): the per-row actions beyond
                the rename consolidate behind the three-dot dropdown —
                Copy + Delete (and the manual Edit). The sparkle (rename)
                stays OUTSIDE by design. Mirrors the panel's Actions
                dropdown (SessionManager.tsx). */}
            <div className="dropdown dropdown-bottom dropdown-end">
              <div className="tooltip tooltip-left" data-tip="More actions">
                <button
                  tabIndex={0}
                  onClick={(e) => {
                    e.stopPropagation()
                    setShowRowMenu(!showRowMenu)
                  }}
                  className="btn btn-xs btn-circle bg-base-100 hover:bg-base-200 border border-base-300 shadow-md transition-all duration-[var(--button-transition)]"
                >
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 8c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 2c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0 6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z" />
                  </svg>
                </button>
              </div>
              {showRowMenu && (
                <ul
                  tabIndex={0}
                  className="dropdown-content z-[1] menu p-2 shadow bg-base-100 rounded-box w-48"
                  onBlur={() => setShowRowMenu(false)}
                  onClick={(e) => e.stopPropagation()}
                >
                  <li>
                    <a onClick={() => { setShowRowMenu(false); onRenameStart() }}>
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                      </svg>
                      Edit name
                    </a>
                  </li>
                  <li>
                    <a onClick={() => {
                      setShowRowMenu(false)
                      const text = session.title || ''
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
                      ;(async () => {
                        let copied = false
                        try {
                          await navigator.clipboard.writeText(text)
                          copied = true
                        } catch {
                          copied = fallbackCopy()
                        }
                        if (copied) {
                          addNotification({ type: 'success', title: 'Session name copied', message: text })
                        } else {
                          addNotification({ type: 'error', title: 'Copy failed', message: 'Could not access the clipboard.' })
                        }
                      })()
                    }}>
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                      </svg>
                      Copy name
                    </a>
                  </li>
                  <li>
                    <a
                      className="text-error"
                      onClick={() => {
                        setShowRowMenu(false)
                        if (requireDeleteConfirm) {
                          setShowDeleteConfirm(true)
                        } else {
                          onDelete()
                          addNotification({ type: 'success', title: 'Deleted!', message: 'Session deleted', duration: 2000 })
                        }
                      }}
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                      Delete
                    </a>
                  </li>
                </ul>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      <dialog ref={deleteModalRef} className="modal">
        <div className="modal-box">
          <h3 className="font-bold text-lg">Delete Session?</h3>
          <p className="py-4">
            Are you sure you want to delete "<strong>{session.title}</strong>"? This action cannot be undone.
          </p>
          <div className="modal-action">
            <button
              onClick={() => {
                deleteModalRef.current?.close()
                setShowDeleteConfirm(false)
              }}
              className="btn btn-neutral btn-ghost"
            >
              Cancel
            </button>
            <button
              onClick={() => {
                deleteModalRef.current?.close()
                setShowDeleteConfirm(false)
                onDelete()
                addNotification({
                  type: 'success',
                  title: 'Deleted!',
                  message: 'Session deleted',
                  duration: 2000
                })
              }}
              className="btn btn-error rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
            >
              Delete
            </button>
          </div>
        </div>
        <form method="dialog" className="modal-backdrop">
          <button onClick={() => setShowDeleteConfirm(false)}>close</button>
        </form>
      </dialog>
    </div>
  )
}

