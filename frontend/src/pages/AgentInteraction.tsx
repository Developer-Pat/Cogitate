
import { useMemo, useState, useEffect, useRef } from 'react';
import { ErrorBoundary } from '../components/ErrorBoundary'
import { usePageTitle } from '../hooks/usePageTitle'

import AgentSelector from '../components/features/agentInteraction/AgentSelector'
import { useMessageStore, selectUnreadCount } from '../stores/messageStore'
import { usePromptHistoryStore } from '../stores/promptHistoryStore'
import { frontendLoggingService } from '../services/frontendLoggingService'
import { navigateTo } from '../services/crossTab/navigationService'
import AgentListSelector from '../components/features/agentInteraction/AgentListSelector'
import ResponseStream from '../components/features/agentInteraction/ResponseStream'
import ChatInterface from '../components/features/agentInteraction/ChatInterface'
import { ExaPromptFlyout } from '../components/features/agentInteraction/ExaPromptFlyout'
import SessionManager from '../components/features/agentInteraction/SessionManager'
import CognitiveTraceDebugOverlay from '../components/features/agentInteraction/CognitiveTraceDebugOverlay'
import useAgentInteraction from '../hooks/useAgentInteraction'
import { useTracePanel } from '../hooks/useTracePanel'


import { collectionsService } from '../services/domain/CollectionsService'



const TEAM_SELECTION_STORAGE_KEY = 'team-selection-store'
const AGENT_SELECTION_STORAGE_KEY = 'agent-selection-store'

export default function Chat() {
  usePageTitle('Agent Chat', 'Interact with AI agents using streaming responses')

  const [sidebarOpen, setSidebarOpen] = useState(true)

  
  // Restore persisted team selection
  const getStoredTeamId = (): string | null => {
    try {
      const stored = sessionStorage.getItem(TEAM_SELECTION_STORAGE_KEY)
      if (stored) {
        const parsed = JSON.parse(stored)
        return parsed.teamId || null
      }
    } catch {
      // Ignore parse errors
    }
    return null
  }

  // Restore persisted agent selection
  const getStoredAgentId = (): string | null => {
    try {
      const stored = sessionStorage.getItem(AGENT_SELECTION_STORAGE_KEY)
      if (stored) {
        const parsed = JSON.parse(stored)
        return parsed.agentId || null
      }
    } catch {
      // Ignore parse errors
    }
    return null
  }

  const [selectedAgentListId, setSelectedAgentListId] = useState<string | null>(getStoredTeamId())
  const persistedAgentId = useRef(getStoredAgentId())

  // Get hook for actions
  const {
    agents,
    sessions,
    state,
    handleAgentSelect,
    handleSendMessage,
    handleSessionSelect,
    handleSessionDelete,
    handleSessionRename,
    handleSessionSmartRename,
    handleGenerateTitle,
    handleImportSession,
    createNewSession,
    handleReloadSessions,
    handleCloseSession,
    handleDeselectSession,
    handleTossSession,
    handleClearMessages,
    stopStreaming,

  } = useAgentInteraction()

  const { selectedAgent, currentSession, isStreaming, isReloadingSessions } = state

  // THE UI PUMP (Step 3): the cognitive state comes from the BUS
  // (useTracePanel — chat:* events) instead of the stream parsing.
  // The indicator re-renders only on trace events, not every token
  // chunk. The stream's own cognitive parsing goes dormant (the
  // retirement in step 4).
  const busCognitiveState = useTracePanel(currentSession?.id?.toString())


  // the overlay's getter: the LATEST bus state (the ref pattern —
  // the getter must not go stale across renders)
  const busStateRef = useRef(busCognitiveState)
  busStateRef.current = busCognitiveState
  // THE MESSAGES WIDGET (2026-08-25, the user's placement): the
  // bell + count in the TOP ROW —
  // moved out of the chat's input toolbar (the de-clutter).
  const unreadCount = useMessageStore(selectUnreadCount)

  // THE PROMPT HISTORY'S WRITE SIDE (2026-09-15). The send path below copies into it.
  const addPrompt = usePromptHistoryStore((state) => state.addPrompt)

  // THE HISTORY → COMPOSER HAND-OFF (2026-09-15, the user's ask).
  // The History tab's "copy into the message box" button needs to reach the
  // composer, but the composer's text state is local to ChatInterface and the
  // panel is its SIBLING. So the page carries it: the panel sets this, the
  // composer appends it and clears it. Never auto-sends.
  const [pendingPrompt, setPendingPrompt] = useState<string | null>(null)

  // Filter agents by selected collection
  const [collectionAgentIds, setCollectionAgentIds] = useState<Set<string>>(new Set())
  const [, setLoadingCollection] = useState(false);

  // Load collection agents when collection changes
  useEffect(() => {
    const loadCollectionAgents = async () => {
      if (!selectedAgentListId) {
        setCollectionAgentIds(new Set())
        return
      }

      try {
        setLoadingCollection(true)
        const items = await collectionsService.getCollectionItems(selectedAgentListId)
        const agentIds = new Set(
          items
            .filter(item => item.entity_type === 'agent')
            .map(item => item.entity_id)
        )
        setCollectionAgentIds(agentIds)
      } catch (error) {
        frontendLoggingService.error('AgentInteraction', 'Failed to load collection agents', error)
        setCollectionAgentIds(new Set())
      } finally {
        setLoadingCollection(false)
      }
    }

    loadCollectionAgents()
  }, [selectedAgentListId])

  // Persist team selection to localStorage
  useEffect(() => {
    if (selectedAgentListId) {
      sessionStorage.setItem(TEAM_SELECTION_STORAGE_KEY, JSON.stringify({ teamId: selectedAgentListId }))
    } else {
      sessionStorage.removeItem(TEAM_SELECTION_STORAGE_KEY)
    }
  }, [selectedAgentListId])

  // Persist agent selection to localStorage on change
  useEffect(() => {
    if (selectedAgent) {
      sessionStorage.setItem(AGENT_SELECTION_STORAGE_KEY, JSON.stringify({ agentId: selectedAgent.id }))
    } else {
      sessionStorage.removeItem(AGENT_SELECTION_STORAGE_KEY)
    }
  }, [selectedAgent])

  // Restore persisted agent selection when agents are loaded (only once on mount)
  const hasRestoredAgentRef = useRef(false)
  useEffect(() => {
    // Only run once - after initial restoration, user selections should not trigger this
    if (hasRestoredAgentRef.current) return
    if (!persistedAgentId.current || agents.length === 0) return

    hasRestoredAgentRef.current = true

    // Try to find the persisted agent in the loaded agents list
    const agentToRestore = agents.find(a => String(a.id) === String(persistedAgentId.current))
    if (agentToRestore) {
      handleAgentSelect(agentToRestore)
    } else {
      // Persisted agent no longer exists, clear it
      persistedAgentId.current = null
      sessionStorage.removeItem(AGENT_SELECTION_STORAGE_KEY)
    }
  }, [agents, handleAgentSelect])

  // Filter agents by selected collection
  const filteredAgents = useMemo(() => {
    if (!selectedAgentListId || collectionAgentIds.size === 0) return agents
    
    return agents.filter(agent => collectionAgentIds.has(agent.id))
  }, [agents, selectedAgentListId, collectionAgentIds])

  // Get messages from currentSession provided by the hook
  const messages = currentSession?.messages || []


  return (
    <ErrorBoundary>
      <div className="flex h-dvh overflow-hidden bg-base-100">
        {/* Main Content Area */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden transition-all duration-300 ease-in-out">
          {/* Header */}
          <div className="border-b border-base-300 flex-shrink-0 bg-base-100 flex items-center justify-between h-auto py-4 px-6">
            {/* Agent List Selector and Agent Selector */}
            <div className="flex items-center gap-2">
              <div className="tooltip tooltip-bottom" data-tip="Select agent team">
                <AgentListSelector
                  selectedListId={selectedAgentListId}
                  onSelectList={setSelectedAgentListId}
                  userKey="default"
                />
              </div>
              <div className="tooltip tooltip-bottom w-64" data-tip="Select an agent">
                <AgentSelector
                  agents={filteredAgents}
                  selectedAgent={selectedAgent}
                  onAgentSelect={handleAgentSelect}
                />
              </div>
            </div>

            {/* Header Buttons */}
            <div className="flex gap-2 items-center">
              {/* (the BackendStatusIndicator stood here — removed
                  2026-09-15 at the user's ask: "I want to get rid of
                  the backend online button. It is distracting." The
                  Dashboard keeps its own compact dot. The connectivity
                  notices come from apiClient + useSystemHealth, NOT
                  from this control, so removing it silences nothing.) */}

              {/* THE MESSAGES WIDGET (2026-08-25): the bell + the
                  count; navigates to the Message Center page.

                  THE TIP CARRIES THE COUNT TOO (2026-09-15, the user's ask). They
                  read the 9 as 95 — which is fair, the badge is `badge-xs` at
                  `text-[10px]` and a single digit is easy to misread at that size.
                  The count is now ALSO in the tooltip, where it is plain text and
                  available at a glance, so the number is readable and the badge stays
                  the always-visible indicator (state belongs ON the element; a
                  hover-only count could not alert anyone).

                  And the tip distinguishes the two counts in the app: THIS is the
                  message center's unread SYSTEM messages, not a session's messages. */}
              <div className="tooltip tooltip-bottom" data-tip={unreadCount > 0 ? `${unreadCount} unread — go to message center` : 'Go to message center'}>
                <button
                  type="button"
                  onClick={() => navigateTo('messages')}
                  className="rounded-full p-1.5 border border-base-300 hover:border-primary/50 relative"
                  aria-label={`Go to message center (${unreadCount} unread)`}
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                  </svg>
                  {unreadCount > 0 && (
                    <span className="absolute -top-1 -right-1 badge badge-primary badge-xs text-[10px]">
                      {unreadCount > 9 ? '9+' : unreadCount}
                    </span>
                  )}
                </button>
              </div>
              <div className="tooltip tooltip-bottom" data-tip={sidebarOpen ? 'Close' : 'Open'}>
                <button
                  type="button"
                  className="rounded-full px-2 py-1 text-xs font-medium bg-primary/20 text-primary border border-primary/30 hover:bg-primary/30 transition-all"
                  onClick={() => setSidebarOpen(!sidebarOpen)}
                >
                  {sidebarOpen ? '✕' : '☰'}
                </button>
              </div>
              {/* THE ASK-EXA WIDGET — LAST IN THE ROW (2026-09-15, the
                  user's ask: "I'd like the exa button on the right so the
                  flyout stays on the page"). The panel is right-aligned to
                  its trigger, so mid-row placement floated it over the middle
                  of the conversation; at the row's end it hugs the page's
                  right edge instead. This page carries its own copy because a
                  bar row above the chat costs vertical space — App.tsx skips
                  this route so there is exactly one widget per page.
                  Cmd/Ctrl+K works either way. */}
              <ExaPromptFlyout />
            </div>
          </div>

          {/* Main Chat Area */}
          <div className="flex-1 overflow-hidden min-h-0 h-full">
            <ResponseStream
              messages={messages}
              isStreaming={isStreaming}
              cognitiveState={busCognitiveState}
            />
          </div>

          {/* Chat Input */}
          <div className="flex-shrink-0 px-6 bg-base-100 border-t border-base-300 py-1 transition-all duration-300">
            <ChatInterface
              onSendMessage={(msg, attachments) => {
                // THE COPY-ON-SEND (2026-09-15, the user's model: "a straight copy to
                // the history table"). The composer hands the text over here, and it
                // lands in the history store. Recorded BEFORE the send so the entry
                // exists even if the request fails — it is a record of what the user
                // asked, not of what succeeded.
                addPrompt(msg, currentSession?.id ?? null)
                return handleSendMessage(msg, undefined, attachments)
              }}
              isStreaming={isStreaming}
              disabled={!selectedAgent || !currentSession}
              onStopStreaming={stopStreaming}
              onDeselectSession={handleDeselectSession}
              onTossSession={handleTossSession}
              placeholder={
                !selectedAgent
                  ? "Select an agent to start chatting..."
                  : !currentSession
                  ? "Select or create a session to start chatting..."
                  : `Message ${selectedAgent.name}...`
              }
              onToggleRightPanel={() => setSidebarOpen(!sidebarOpen)}
              agentId={selectedAgent?.id}
              pendingPrompt={pendingPrompt}
              onPendingPromptConsumed={() => setPendingPrompt(null)}
            />
          </div>
        </div>

        {/* Right Sidebar - Session Manager (Collapsible) */}
        <div
          key={`sidebar-${sidebarOpen}`}
          className={`border-l border-base-300 bg-base-100 transition-all duration-300 ease-in-out overflow-y-auto flex flex-col ${
            sidebarOpen ? 'w-80' : 'w-0'
          }`}
        >
          <div className={sidebarOpen ? 'h-full flex flex-col' : 'hidden'}>
            <div className="flex-1 overflow-y-auto">
              <SessionManager
                sessions={sessions}
                currentSession={currentSession}
                onSessionSelect={handleSessionSelect}
                onSessionDelete={handleSessionDelete}
                onSessionRename={handleSessionRename}
                onSessionSmartRename={handleSessionSmartRename}
                onGenerateTitle={handleGenerateTitle}
                onSessionImport={handleImportSession}
                onNewSession={createNewSession}
                onReloadSessions={handleReloadSessions}
                isReloadingSessions={isReloadingSessions}
                onCloseSession={handleCloseSession}
                onClearMemory={handleClearMessages}
                /* MOVED HERE 2026-09-15: the Deselect control relocated from the
                   ChatInterface input row to this panel's header. The SAME handler is
                   still passed to ChatInterface below (its button is DEPRECATED but its
                   prop remains), so nothing about the behaviour changed — only where
                   the control sits. `isStreaming` carries the guard the button had. */
                onDeselectSession={handleDeselectSession}
                isStreaming={isStreaming}
                onUsePrompt={setPendingPrompt}
              />
            </div>

          </div>
        </div>
        {/* Cognitive Trace Debug Overlay (development only, Ctrl+Shift+D) */}
        <CognitiveTraceDebugOverlay
          cognitiveState={busCognitiveState}
          getCognitiveState={() => busStateRef.current}
        />
      </div>
    </ErrorBoundary>
  )
}