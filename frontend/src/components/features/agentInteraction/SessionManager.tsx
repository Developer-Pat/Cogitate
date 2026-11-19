import { useState, useMemo } from 'react'
// DEPRECATED(2026-09-15): `useNavigate` was only for the gear button, which is gone.
// Kept as a comment so a grep for DEPRECATED finds it; delete with the gear block.
// import { useNavigate } from 'react-router-dom'
import { useNotificationStore } from '@/stores/notificationStore'
import { useCognitiveHubStore } from '@/stores/cognitiveHubStore'
import { apiClient } from '@/services/apiClient'
import type { ConversationSession } from '@/types/agentInteraction'
import SessionList from './SessionList'
import PromptHistoryList from './PromptHistoryList'
import { BadgeButton } from '@/components/ui/BadgeButton'
// New imports use the `@` locator (the house rule — one definition, every consumer);
// the older hand-computed climbs beside it are the banked codemod's business.
import PortalTooltip from '@/components/ui/PortalTooltip'
import { frontendLoggingService } from '@/services/frontendLoggingService'
import { IdService } from '@/services/domain/IdService'

export type SessionManagerVariant = 'agent' | 'exa'

interface SessionManagerProps {
  /** THE SURFACE VARIANT (2026-09-04, the Exa-panel B): 'agent'
      (default) = the agent page's full manager (agent filter +
      settings tab + the agent-guarded New). 'exa' = the same widget
      for the Exa page: no agent concept, no settings tab (Exa's
      config lives on its own page), the New button creates
      directly. Everything else (list, search, sort, rename,
      delete, bulk ops) is shared. */
  variant?: SessionManagerVariant
  sessions: ConversationSession[]
  currentSession: ConversationSession | null
  onSessionSelect: (session: ConversationSession) => Promise<void>
  onSessionDelete: (sessionId: string) => void
  onSessionRename?: (sessionId: string, newTitle: string) => void
  onSessionSmartRename?: (session: ConversationSession) => void
  onGenerateTitle?: (sessionId: string) => Promise<void>
  onSessionImport?: (session: ConversationSession) => void
  onNewSession?: () => void
  onReloadSessions?: () => void
  isReloadingSessions?: boolean
  onCloseSession?: () => void
  onClearMemory?: () => void
  /** MOVED HERE 2026-09-15 (the user's ask): the Deselect control used to live in
      ChatInterface's input widget. It now sits in the panel header, where the
      redundant gear/"Chat settings" button was. */
  onDeselectSession?: () => void
  /** The guard the moved button carried in ChatInterface (`disabled={isStreaming}`).
      SessionManager has no streaming state of its own, so it is passed in — dropping
      the guard would have been a silent behaviour change. */
  isStreaming?: boolean
  /** THE HISTORY TAB'S SECOND BUTTON (2026-09-15, the user's ask): "utilize it
      either copy to clipboard or copy to input".

      This puts the prompt INTO the composer and never sends it. It has to be a
      callback because the composer's text state is local to ChatInterface and this
      panel is its SIBLING — the page owns the hand-off (the same shape the macros
      use, just across the panel boundary instead of inside the composer). */
  onUsePrompt?: (text: string) => void
}

export default function SessionManager({
  variant = 'agent',
  sessions,
  currentSession,
  onSessionSelect,
  onSessionDelete,
  onSessionRename,
  onSessionSmartRename,
  onGenerateTitle,
  onSessionImport: _onSessionImport,
  onNewSession,
  onReloadSessions,
  isReloadingSessions = false,
  onCloseSession,
  onDeselectSession,
  isStreaming = false,
  onUsePrompt,
}: SessionManagerProps) {
  // DEPRECATED(2026-09-15): the only caller was the gear button's navigate('/settings').
  // const navigate = useNavigate()
  const addNotification = useNotificationStore((state) => state.addNotification)
  const [searchQuery, setSearchQuery] = useState('')
  const [filterAgent, setFilterAgent] = useState<string | null>(null)
  const [sortBy, setSortBy] = useState<'recent' | 'oldest' | 'alphabetical'>('recent')
  const [isExpanded, setIsExpanded] = useState(false)  // Default collapsed
  const [requireDeleteConfirm, setRequireDeleteConfirm] = useState(false)  // Default OFF
  const [selectedSessions, setSelectedSessions] = useState<Set<string>>(new Set())
  const [isBulkDeleteMode, setIsBulkDeleteMode] = useState(false)
  const [activeTab, setActiveTab] = useState<'sessions' | 'history'>('sessions')
  const [showActionsMenu, setShowActionsMenu] = useState(false)

  // Get selected agent from cognitiveHubStore (single source of truth)
  // — the EXA variant has no agent concept; the read is skipped
  // (the hub store belongs to the agent-chat surface).
  const selectedAgent = useCognitiveHubStore(
    variant === 'exa' ? () => null : (state) => state.activeAgent
  )

  // Get unique agents from sessions — the EXA variant skips this
  // entirely (its sessions have no agentId; a null-keyed group would
  // render a bogus 'undefined' filter row).
  const uniqueAgents = useMemo(() => {
    if (variant === 'exa') return []
    const agents = new Map<string, string>()
    sessions.forEach(session => {
      if (!agents.has(session.agentId)) {
        agents.set(session.agentId, session.agentId)
      }
    })
    return Array.from(agents.values())
  }, [sessions, variant])

  // Filter and sort sessions
  const filteredSessions = useMemo(() => {
    const filtered = sessions.filter(session => {
      // THE SOURCE GUARD (2026-09-04, the leak dig — issue #1): the
      // agent page's hub CACHE can hold stale exa sessions (written
      // before the source=agent fetch filter existed; the keep-cache
      // fallback preserves them). The widget is the last line of
      // defense: each variant shows ONLY its own surface's sessions
      // — agent hides source='exa', exa hides source='agent'. (The
      // ConversationSession.source is optional — legacy rows with no
      // tag are agent-side.)
      //
      // THE UNDEFINED-SOURCE FIX (2026-09-11) — REVISED, and the revision is
      // the point.
      //
      // The first attempt keyed this on `agentId`:
      //   x.source === 'exa' || (!isTemp && !x.agentId)
      // That was WRONG, and it is the same mistake it was meant to fix. A
      // guard must hide a row only on a POSITIVE signal about that row —
      // never because a field is ABSENT. Fields are absent here all the
      // time: `source` is dropped by some loader paths, and `agentId` can be
      // dropped too (a locally-created session committed mid-stream). A
      // guard that hides on absence swallows REAL agent sessions — the user
      // reports exactly that, a session vanishing from the panel.
      //
      // So: hide ONLY a row that positively declares itself Exa. An untagged
      // row is shown. The correct repair for the leak is to make the tag
      // survive the mapping (a known gap) — not to infer it from a
      // missing field.
      const isExaRow = session.source === 'exa'
      if (variant === 'agent' && isExaRow) return false
      if (variant === 'exa' && session.source !== 'exa') return false
      const matchesSearch = session.title.toLowerCase().includes(searchQuery.toLowerCase())
      const matchesAgent = !filterAgent || session.agentId === filterAgent
      return matchesSearch && matchesAgent
    })

    // Sort sessions — THE TEMP PIN + THE NAN-GUARDED COMPARATORS
    // (2026-09-05, the user's session-list report): two mechanisms.
    //
    // (1) THE TEMP PIN (the user's chosen fix): a brand-new session
    // is a LOCAL TEMP (temp id — no backend row yet; it only
    // becomes real when the first message commits it). The loader
    // appends temps at the tail of the fetched list
    // ([...mergedSessions, ...tempSessions]) and their date shape
    // differs from the backend rows' — so they wedge mid-list under
    // a pure date sort. But a temp is by definition the newest thing
    // in the room: every temp pins ABOVE the committed list, newest
    // first. The moment the first message commits it, it becomes a
    // real row and sorts naturally below with the others.
    //
    // (2) THE NAN-GUARD (the random-wedge class): the naive
    // `new Date(<unparseable>).getTime()` = NaN — a NaN comparator
    // drops the element into an arbitrary stable position.
    // sortTime() normalizes any shape (Date / ISO string / epoch
    // number) and maps unparseable to 0: the sorts are always
    // deterministic, and a dateless session sinks to the bottom
    // instead of wedging mid-list.
    const sortTime = (d: unknown): number => {
      if (d === undefined || d === null) return 0
      const t = d instanceof Date ? d.getTime() : new Date(d as string | number).getTime()
      return Number.isNaN(t) ? 0 : t
    }
    const committed = filtered.filter(session => !IdService.isTempId(session.id))
    const temps = filtered.filter(session => IdService.isTempId(session.id))
    switch (sortBy) {
      case 'oldest':
        committed.sort((a, b) => sortTime(a.createdAt) - sortTime(b.createdAt))
        break
      case 'alphabetical':
        committed.sort((a, b) => a.title.localeCompare(b.title))
        break
      case 'recent':
      default:
        committed.sort((a, b) => sortTime(b.updatedAt) - sortTime(a.updatedAt))
    }
    temps.sort((a, b) => sortTime(b.updatedAt) - sortTime(a.updatedAt))

    // THE ACTIVE PIN (2026-09-09, the user's panel spec): the
    // CURRENT session — the one being talked to — always renders
    // first, selected. The temp-pin above already covers brand-new
    // sessions; this also covers the swapped/committed active (the
    // moment the first message lands) so the conversation never
    // appears to "lose" its session mid-chat. The active is the
    // anchor; the rest sort below it.
    const hubState = useCognitiveHubStore.getState()
    // The prop is the same session the hub holds (the parents pass the active
    // session down); reading it here is what makes it a REAL dependency —
    // otherwise the memo would only recompute when the store read below
    // happened to coincide with a re-render.
    const activeId = hubState.activeSession?.id ?? currentSession?.id
    // THE TYPE-SAFE PIN (2026-09-10): the remap stores the committed id
    // as a STRING (String(parsed.session_id) in StreamingService) while
    // the loaded rows can carry NUMBERS — a raw === misses and the
    // active session silently unpins from the panel. IdService.equals
    // normalizes both sides (its whole purpose).
    const rest = [...temps, ...committed].filter(s => !IdService.equals(s.id, activeId))
    if (activeId) {
      const active = [...temps, ...committed].find(s => IdService.equals(s.id, activeId))
      if (active) {
        rest.unshift(active)
      }
    }
    return rest
  }, [sessions, searchQuery, filterAgent, sortBy, variant, currentSession?.id])

  const toggleSessionSelection = (sessionId: string) => {
    setSelectedSessions(prev => {
      const newSelected = new Set(prev)
      if (newSelected.has(sessionId)) {
        newSelected.delete(sessionId)
      } else {
        newSelected.add(sessionId)
      }
      frontendLoggingService.debug('SessionManager:selection', 'Toggle selection', { sessionId, selectedSessions: Array.from(newSelected) })
      return newSelected
    })
  }

  const selectAllSessions = () => {
    const allIds = new Set(filteredSessions.map(s => s.id))
    setSelectedSessions(allIds)
    frontendLoggingService.debug('SessionManager:selection', 'Select all', { selectedSessions: Array.from(allIds) })
  }

  const deselectAllSessions = () => {
    setSelectedSessions(new Set())
    frontendLoggingService.debug('SessionManager:selection', 'Deselect all')
  }

  const handleBulkDelete = async () => {
    if (selectedSessions.size === 0) {
      frontendLoggingService.warning('SessionManager:bulkDelete', 'No sessions selected for deletion')
      return
    }

    frontendLoggingService.info('SessionManager:bulkDelete', 'Starting bulk delete', { sessionIds: Array.from(selectedSessions) })

    try {
      const sessionIds = Array.from(selectedSessions)
        .filter(id => !IdService.isTempId(id))
        .map(id => IdService.toBackend(id))
      frontendLoggingService.debug('SessionManager:bulkDelete', 'Sending bulk delete request', { sessionIds })

      const result = await apiClient.post<{ total_deleted: number; deleted_ids: number[] }>(
        '/api/v1/sessions/bulk-delete',
        sessionIds
      )

      if (result.data) {
        frontendLoggingService.info('SessionManager:bulkDelete', `Deleted ${result.data.total_deleted} sessions`, result as unknown as Record<string, unknown>)
        setSelectedSessions(new Set())
        setIsBulkDeleteMode(false)

        // Show success notification
        addNotification({
          type: 'success',
          title: 'Deleted!',
          message: `${result.data.total_deleted} session${result.data.total_deleted !== 1 ? 's' : ''} deleted`,
          duration: 2000
        })

        // Reload sessions to reflect changes - wait for it to complete
        if (onReloadSessions) {
          frontendLoggingService.debug('SessionManager:bulkDelete', 'Reloading sessions after bulk delete...')
          await onReloadSessions()
          frontendLoggingService.info('SessionManager:bulkDelete', 'Sessions reloaded')
        }
      }
    } catch (error) {
      frontendLoggingService.error('SessionManager:bulkDelete', 'Bulk delete failed', error)

      // Show error notification
      addNotification({
        type: 'error',
        title: 'Delete Failed',
        message: 'Failed to delete sessions',
        duration: 3000
      })
    }
  }

  // Session action handlers
  const handleEditTitle = () => {
    if (!currentSession || !onSessionRename) return
    const newTitle = prompt('Enter new session title:', currentSession.title)
    if (newTitle && newTitle.trim()) {
      onSessionRename(currentSession.id, newTitle.trim())
    }
    setShowActionsMenu(false)
  }

  const handleGenerateTitle = async () => {
    if (!currentSession || !onGenerateTitle) return
    try {
      await onGenerateTitle(currentSession.id)
      frontendLoggingService.info('SessionManager', 'Session title generated', { sessionId: currentSession.id })
    } catch (error) {
      frontendLoggingService.error('SessionManager', 'Failed to generate title', error as Error)
      addNotification({
        type: 'error',
        title: 'Title Generation Failed',
        message: error instanceof Error ? error.message : 'Failed to generate session title',
        duration: 3000
      })
    }
    setShowActionsMenu(false)
  }

  const handleExport = async () => {
    if (!currentSession) return
    try {
      frontendLoggingService.info('SessionManager', `Exporting session: ${currentSession.title}`, { sessionId: currentSession.id })
      const response = await apiClient.post<{filename: string; message: string}>(`/api/v1/chat/sessions/${currentSession.id}/export`)
      if (response.data?.filename) {
        addNotification({ type: 'success', title: 'Session Exported', message: `Exported to: ${response.data.filename}`, duration: 2000 })
      }
    } catch (error) {
      frontendLoggingService.error('SessionManager', 'Export failed', error as Error)
      addNotification({ type: 'error', title: 'Export Failed', message: error instanceof Error ? error.message : 'Failed to export', duration: 3000 })
    }
    setShowActionsMenu(false)
  }

  const handleImport = () => {
    // Trigger file input via ref - handled below
    setShowActionsMenu(false)
  }

  // Check if title generation is possible
  const sessionMessages = currentSession?.messages || []
  const hasAtLeastTwoMessages = sessionMessages.length >= 2
  const hasAssistantMessages = sessionMessages.filter(msg => msg.role === 'assistant').length > 0
  const canGenerateTitle = hasAtLeastTwoMessages && hasAssistantMessages

  return (
    <div className="flex flex-col h-full bg-base-100">
      {/* Header */}
      <div className="p-4 border-b border-base-300">
        <div className="flex items-center justify-end gap-1 mb-4 flex-wrap">
          {/* Icons only - no label needed */}
          {/* New Session Button (Create - first, left side) */}
          {onNewSession && (
            <div className="tooltip tooltip-bottom" data-tip="Create new session">
              <BadgeButton
                onClick={() => {
                  // THE EXA VARIANT (2026-09-04): no agent to select —
                  // the New button creates the exa session directly.
                  if (variant === 'agent' && !selectedAgent) {
                    addNotification({
                      type: 'warning',
                      title: 'No Agent Selected',
                      message: 'Please select an agent first to create a new session',
                      duration: 3000
                    })
                    return
                  }

                  onNewSession()

                  addNotification({
                    type: 'success',
                    title: 'New Session Ready',
                    message: variant === 'exa'
                      ? 'New Exa chat started — send a message to name it'
                      : `Start chatting to save the session with ${selectedAgent?.name}`,
                    duration: 2000
                  })
                }}
              >
                New
              </BadgeButton>
            </div>
          )}


          {/* ---- THE FIVE VIEW CONTROLS, IN THE USER'S ORDER (2026-09-15) ----
              The user fixed this row's order as:

                  deselect - refresh - expand - trash can - delete confirm

              and asked for the delete-confirmation toggle at the FAR RIGHT. This row
              is `justify-end`, so the LAST element emitted is the rightmost; Delete-
              confirm is therefore emitted last.

              Everything session-level (the ⋮ actions menu) groups ahead of the five,
              next to the New button, so the five read as a contiguous run. */}

          {/* ⋮ Session actions — moved up from the row's end so the five controls
              above stay contiguous and Delete-confirm can hold the far right. */}
          {currentSession && (
            <div className="dropdown dropdown-bottom dropdown-end">
              <div className="tooltip tooltip-bottom" data-tip="Session actions">
                <button
                  tabIndex={0}
                  onClick={() => setShowActionsMenu(!showActionsMenu)}
                  className="btn btn-ghost btn-sm btn-circle hover:bg-base-200 transition-all duration-[var(--button-transition)]"
                >
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 8c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 2c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0 6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z" />
                  </svg>
                </button>
              </div>
              {showActionsMenu && (
                <ul
                  tabIndex={0}
                  className="dropdown-content z-[1] menu p-2 shadow bg-base-100 rounded-box w-52"
                  onBlur={() => setShowActionsMenu(false)}
                >
                  <li>
                    <a onClick={handleEditTitle}>
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                      </svg>
                      Edit Title
                    </a>
                  </li>
                  <li>
                    <a
                      onClick={handleGenerateTitle}
                      className={!canGenerateTitle ? 'opacity-50 cursor-not-allowed' : ''}
                      title={!canGenerateTitle ? (hasAtLeastTwoMessages ? 'No assistant messages found' : 'Need at least 2 messages') : 'Generate title from assistant response'}
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
                      </svg>
                      Rename (AI)
                    </a>
                  </li>
                  <li className="border-t border-base-300 my-1"></li>
                  <li>
                    <a onClick={handleExport}>
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                      </svg>
                      Export
                    </a>
                  </li>
                  <li>
                    <a onClick={handleImport}>
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8v1a3 3 0 003 3h10a3 3 0 003-3V8m-4 4l-4-4m0 0l-4 4m4-4v12" />
                      </svg>
                      Import
                    </a>
                  </li>
                  <li className="border-t border-base-300 my-1"></li>
                  <li>
                    <a onClick={onCloseSession}>
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                      Close Session
                    </a>
                  </li>
                </ul>
              )}
            </div>
          )}

          {/* 1. DESELECT — moved here 2026-09-15 (the user's ask).

              It used to live in ChatInterface's under-Send row as a TEXT button
              ("Deselect"). It keeps the tooltip and the aria-label it had, and the
              `disabled={isStreaming}` guard is passed in from the page — SessionManager
              has no streaming state of its own, and dropping the guard silently would
              have changed what is allowed when.

              `onDeselectSession` is optional, so the Exa variant (which never passes it)
              renders nothing here. */}
          {onDeselectSession && (
            <div className="tooltip tooltip-bottom" data-tip={!currentSession ? 'Deselect — select a session first' : 'Deselect — work with no session selected'}>
              <button
                onClick={() => onDeselectSession()}
                /* THE BUTTON TRACKS THE SELECTION (2026-09-15, the user's ask):
                   "when a session is selected it should be active and with no
                   session selected it should be disabled". Deselect with nothing
                   selected is a no-op, so offering it was a lie about state.
                   The isStreaming guard is kept — it was the button's original
                   guard and is not mine to drop. */
                disabled={!currentSession || isStreaming}
                aria-label="Deselect current session"
                className={`btn btn-ghost btn-sm btn-circle transition-all duration-[var(--button-transition)] ${
                  !currentSession || isStreaming ? 'cursor-not-allowed opacity-50' : 'hover:bg-base-200'
                }`}
              >
                {/* A CIRCLE WITH A SLASH (2026-09-15, the user's ask): the plain
                    "none" mark. The previous glyph was a pointer with a slash,
                    which read as a crossed triangle / "mute" rather than as
                    deselect — see the DEPRECATED note below for the trail. */}
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="9" />
                  <path strokeLinecap="round" d="M5.6 5.6l12.8 12.8" />
                </svg>
              </button>
            </div>
          )}
                {/* DEPRECATED(2026-09-15) — the pointer-with-slash glyph, kept for the
                    record. It replaced an unreadable diamond-and-bracket shape, but
                    read as a crossed triangle / "mute" rather than as deselect, so the
                    user chose a plain circle-with-slash instead. Do not reinstate
                    without looking at it rendered at 20px.
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 3l7.07 16.97 2.51-7.39 7.39-2.51L3 3z" />
                  <path strokeLinecap="round" strokeLinejoin="round" d="M20 4L4 20" />
                </svg>
                */}

          {/* 2. REFRESH — reload all sessions with their messages from the database */}
          {onReloadSessions && (
            <div className="tooltip tooltip-bottom" data-tip="Reload all sessions with messages from database">
              <button
                onClick={onReloadSessions}
                disabled={isReloadingSessions}
                className="btn btn-ghost btn-sm btn-circle hover:bg-base-200 transition-all duration-[var(--button-transition)]"
              >
                {isReloadingSessions ? (
                  <span className="loading loading-spinner loading-xs"></span>
                ) : (
                  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                )}
              </button>
            </div>
          )}

          {/* 3. EXPAND / COLLAPSE */}
          <div className="tooltip tooltip-bottom" data-tip={isExpanded ? 'Collapse' : 'Expand'}>
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="btn btn-ghost btn-sm btn-circle hover:bg-base-200 transition-all duration-[var(--button-transition)]"
            >
              <svg
                className={`w-5 h-5 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
              </svg>
            </button>
          </div>

          {/* 4. TRASH CAN — bulk delete mode */}
          <div className="tooltip tooltip-bottom" data-tip="Bulk delete mode">
            <button
              onClick={() => setIsBulkDeleteMode(!isBulkDeleteMode)}
              className={`btn btn-ghost btn-sm btn-circle hover:bg-base-200 ${isBulkDeleteMode ? 'btn-warning' : ''}`}
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>

          {/* 5. DELETE CONFIRMATION ON/OFF — the FAR RIGHT of the row (the user's ask).
              Warning-tinted when OFF: the toggle is then disabling a safeguard, and
              colour is what says so at a glance. */}
          <div className="tooltip tooltip-bottom" data-tip={requireDeleteConfirm ? 'Delete confirmation ON' : 'Delete confirmation OFF'}>
            <button
              onClick={() => setRequireDeleteConfirm(!requireDeleteConfirm)}
              className={`btn btn-ghost btn-sm btn-circle hover:bg-base-200 ${requireDeleteConfirm ? '' : 'btn-warning'}`}
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d={requireDeleteConfirm ? "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" : "M10 14l-2-2m0 0l-2-2m2 2l2-2m-2 2l-2 2"} />
              </svg>
            </button>
          </div>

          {/* DEPRECATED(2026-09-15) — the gear / "Chat settings" button.
              Removed at the user's ask: it was REDUNDANT. It only did
              `navigate('/settings')`, and the settings it reached were a mix of
              agent settings (covered on the Agent Profiles page) and theme settings
              (covered on the Settings page).

              Kept here, commented, so a grep for DEPRECATED finds it for later
              removal. Do not restore without re-checking that claim.

          <div className="tooltip tooltip-bottom" data-tip="Chat settings">
            <button
              onClick={() => navigate('/settings')}
              className="btn btn-ghost btn-sm btn-circle hover:bg-base-200 transition-all duration-[var(--button-transition)]"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </button>
          </div>
          */}
        </div>
      </div>

      {/* THE TWO-TAB STRIP (2026-09-15). Sessions | History.

          History takes the slot the removed Settings tab occupied — the strip was
          kept for exactly this. The prompts list follows the session-title display
          technique: a partial line in the row, a longer cut in the tooltip, and the
          copy buttons for the rest.

          Gated to the `agent` variant, mirroring how Settings was gated: the Exa page
          has its own prompt flyout, and this is not the place to change it. */}
      <div className="p-4 border-b border-base-300">
        <div className="tabs tabs-boxed w-full gap-1">
          <button
            /* THE LABEL IS PLAIN AND LOUDER (2026-09-15, the user's ask): the emoji
               is gone ("has an emoji which is bad"), and the text was SMALLER than
               the session names beneath it — `tab-sm` plus the default weight. The
               session rows are `font-medium text-sm`, so this is `text-base
               font-semibold`: a section label should not be the quietest thing in
               its own list. */
            className={`tab flex-1 text-base font-semibold ${activeTab === 'sessions' ? 'tab-active' : ''}`}
            onClick={() => setActiveTab('sessions')}
          >
            Sessions
          </button>
          {variant === 'agent' && (
            <button
              className={`tab flex-1 text-base font-semibold ${activeTab === 'history' ? 'tab-active' : ''}`}
              onClick={() => setActiveTab('history')}
            >
              History
            </button>
          )}
        </div>
      </div>

      {/* Tab Content — the EXA variant has no settings tab; the
          activeTab can never be 'settings' (the tab is hidden). */}
      {(activeTab === 'sessions' || variant === 'exa') ? (
        <>

        {/* Bulk Delete Actions.
            THE LABELS ARE DELIBERATELY TERSE (2026-09-17, the user's ask): "All"
            and "None" for "Select All" / "Deselect All", and "Delete N" for
            "Delete N Sessions". Two buttons in a bulk-delete bar can only mean
            one thing, so the words shrink to what the row already implies — and
            the tips carry the rest, because a terser label is exactly where a tip
            earns its keep.

            The "N of M selected" readout that stood between them is gone: the
            Delete button already carries the count that matters, so N-of-M was a
            third number in a row that only needed one. (`filteredSessions` is NOT
            orphaned by this — the filter count and the list still use it. The
            "N of M sessions" line in the Filters block is a DIFFERENT readout and
            was left alone.)

            `ml-auto` moved to the Delete button's wrapper: it used to live on the
            removed span, and it has to sit on the PortalTooltip wrapper because
            THAT is the flex item — putting it on the button inside would do
            nothing.

            The tips are PortalTooltip, not DaisyUI `data-tip`, because this is the
            side panel, whose scroll ancestors clip an absolutely-positioned
            `::before`; SessionListItem next door was moved for the same reason. The
            wrapper also gives the DISABLED Delete button a hover target — a
            disabled button fires no mouse events of its own. */}
        {isBulkDeleteMode && (
          <div className="flex items-center gap-2 mb-4 p-3 bg-warning/10 rounded-lg">
            <PortalTooltip content="Select every session" side="bottom">
              <button
                onClick={selectAllSessions}
                className="btn btn-xs btn-outline"
              >
                All
              </button>
            </PortalTooltip>
            <PortalTooltip content="Clear the selection" side="bottom">
              <button
                onClick={deselectAllSessions}
                className="btn btn-xs btn-outline"
              >
                None
              </button>
            </PortalTooltip>
            <div className="ml-auto">
              <PortalTooltip
                content={
                  selectedSessions.size === 1
                    ? 'Delete the selected session'
                    : `Delete the ${selectedSessions.size} selected sessions`
                }
                side="bottom"
              >
                <button
                  onClick={handleBulkDelete}
                  disabled={selectedSessions.size === 0}
                  className="btn btn-error btn-sm"
                >
                  Delete {selectedSessions.size}
                </button>
              </PortalTooltip>
            </div>
          </div>
        )}

        {/* Filters */}
        {isExpanded && (
          <div className="space-y-3 mb-4">
            {/* Search */}
            <div className="form-control">
              <input
                type="text"
                placeholder="Search sessions..."
                className="input input-bordered input-sm bg-base-100 text-base-content rounded-[var(--form-input-radius)] bg-[var(--form-input-bg)] border-[var(--form-input-border)] text-[var(--form-input-text)] focus:border-[var(--form-input-focus-border)] transition-all duration-[var(--button-transition)]"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>

            {/* Agent Filter — the EXA variant never shows it */}
            {variant === 'agent' && uniqueAgents.length > 1 && (
              <div className="form-control">
                <label className="label py-1">
                  <span className="label-text text-xs text-base-content">Filter by Agent</span>
                </label>
                <select
                  className="select select-bordered select-sm bg-base-100 text-base-content rounded-[var(--form-input-radius)] px-[var(--form-input-padding)] focus:border-[var(--form-input-focus-border)] transition-all duration-[var(--button-transition)]"
                  value={filterAgent || ''}
                  onChange={(e) => setFilterAgent(e.target.value || null)}
                >
                  <option value="">All Agents</option>
                  {uniqueAgents.map(agent => (
                    <option key={agent} value={agent}>
                      {agent}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Sort */}
            <div className="form-control">
              <label className="label py-1">
                <span className="label-text text-xs text-base-content">Sort by</span>
              </label>
              <select
                className="select select-bordered select-sm bg-base-100 text-base-content rounded-[var(--form-input-radius)] px-[var(--form-input-padding)] focus:border-[var(--form-input-focus-border)] transition-all duration-[var(--button-transition)]"
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as 'recent' | 'oldest' | 'alphabetical')}
              >
                <option value="recent">Most Recent</option>
                <option value="oldest">Oldest First</option>
                <option value="alphabetical">Alphabetical</option>
              </select>
            </div>

            {/* Session Count */}
            <div className="text-xs text-readout py-2">
              {filteredSessions.length} of {sessions.length} sessions
            </div>
          </div>
        )}

      {/* Session List */}
      <div className="flex-1 overflow-y-auto pb-4">
        {filteredSessions.length === 0 ? (
          <div className="p-4 text-center text-readout">
            <p className="text-sm">
              {sessions.length === 0 ? 'No sessions yet' : 'No sessions match your search'}
            </p>
          </div>
        ) : (
          <SessionList
            sessions={filteredSessions}
            currentSession={currentSession}
            onSessionSelect={onSessionSelect}
            onSessionDelete={onSessionDelete}
            onSessionRename={onSessionRename}
            onSessionSmartRename={onSessionSmartRename}
            requireDeleteConfirm={requireDeleteConfirm}
            isBulkDeleteMode={isBulkDeleteMode}
            selectedSessions={selectedSessions}
            onSessionToggleSelect={toggleSessionSelection}
          />
        )}
      </div>
        </>
      ) : (
        <>

          {/* THE HISTORY TAB (2026-09-15) — the user's past prompts for this session.
              The prompts come from the ACTIVE session's user messages, which are
              lazily loaded: for a session that has not been opened this is
              legitimately empty, and the list says so rather than firing a fetch per
              row. */}
          <div className="flex-1 overflow-y-auto pb-4">
            {/* No props for the data: the list reads the store directly now. The
                history is its own record, written on send — not derived from the
                active session's messages (2026-09-15 correction). */}
            <PromptHistoryList onUsePrompt={onUsePrompt} />
          </div>
        </>
      )}
    </div>
  )
}

