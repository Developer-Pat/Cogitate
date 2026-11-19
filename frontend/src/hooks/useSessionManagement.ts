/**
 * Hook for managing conversation session CRUD operations
 * Handles loading, creating, updating, and deleting chat sessions
 * 
 * MIGRATED TO COGNITIVE HUB: Reads/writes from cognitiveHubStore
 */

import { useState, useCallback, useRef, useEffect } from 'react'
import { sessionSyncService, SessionSource } from '../services/sessionSyncService'
import { apiClient } from '../services/apiClient'
import { useNotificationStore } from '../stores/notificationStore'
import { frontendLoggingService } from '../services/frontendLoggingService'
import { useCognitiveHubStore } from '../stores/cognitiveHubStore'


import type { ConversationSession, ConversationMessage } from '../types/agentInteraction'
import { IdService } from '../services/domain/IdService'

interface UseSessionManagementReturn {
  sessions: ConversationSession[]
  currentSession: ConversationSession | null
  isLoadingSessions: boolean
  isReloadingSessions: boolean
  error: string | null
  createSession: (title: string, agentId: string, model: string) => Promise<ConversationSession>
  deleteSession: (sessionId: string) => void
  switchSession: (session: ConversationSession) => Promise<void>
  reloadSessions: () => Promise<void>
  renameSession: (sessionId: string, newTitle: string) => void
  replaceSession: (oldId: string, newSession: ConversationSession) => void
  clearCurrentSession: () => void
  clearCurrentSessionMessages: () => void
  closeSession: () => void
  addLocalSession: (session: ConversationSession) => void
  addMessage: (sessionId: string, message: ConversationMessage) => void
  updateMessage: (sessionId: string, messageId: string, content: string, metadata?: Record<string, unknown>) => void
  smartRenameSession: (session: { id: string }) => Promise<void>
}

export function useSessionManagement(): UseSessionManagementReturn {
  // Use Cognitive Hub store for sessions and currentSession with proper subscription
  const hubStore = useCognitiveHubStore()

  // Subscribe to store slices properly for reactivity
  const sessions = useCognitiveHubStore(state => state.sessions)
  const currentSession = useCognitiveHubStore(state => state.activeSession)
  
  // Local state for UI flags only
  const [isLoadingSessions, setIsLoadingSessions] = useState(false)
  const [isReloadingSessions, setIsReloadingSessions] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Track sessions being created to prevent duplicates
  const creatingSessionRef = useRef<Set<string>>(new Set())
  /** The reload, reachable from callbacks declared ABOVE it (the failed-
   *  delete path reloads the list to put a row back). */
  const reloadRef = useRef<(() => Promise<void>) | null>(null)

  /**
   * Load sessions from backend
   */
  const loadSessions = useCallback(async () => {
    try {
      setIsLoadingSessions(true)
      setError(null)

      // Get current sessions from store (may be restored from localStorage)
      const hubState = useCognitiveHubStore.getState()
      const cachedSessions = hubState.sessions

      // Load titles only from backend (lazy loading) - messages loaded on demand
      // THE SOURCE FILTER (2026-09-04, the exa-leak dig): this hook
      // feeds the AGENT page — request ONLY the agent surface's
      // sessions, never Exa's (source='exa'). ExaChat manages its
      // own sessions directly; if this hook is ever shared, the
      // source becomes a parameter.
      const backendSessions = await sessionSyncService.getSessions(SessionSource.AGENT)

      if (backendSessions && backendSessions.length > 0) {
        const convertedSessions = backendSessions.map(session =>
          sessionSyncService.convertToFrontendSession(session)
        )

        // Preserve temp sessions that were created while loading
        const tempSessions = cachedSessions.filter(s => IdService.isTempId(s.id))

        // CRITICAL: Preserve messages from cached sessions (localStorage)
        // Backend returns sessions without messages (include_messages=false)
        // We need to merge cached messages with backend session data
        const mergedSessions = convertedSessions.map(backendSession => {
          // Find matching cached session
          const cachedSession = cachedSessions.find(s => s.id === backendSession.id)
          
          if (cachedSession && cachedSession.messages && cachedSession.messages.length > 0) {
            // Use cached messages from localStorage
            return {
              ...backendSession,
              messages: cachedSession.messages
            }
          }
          
          // No cached messages, use backend (empty)
          return backendSession
        })

        // Merge with temp sessions
        const allSessions = [...mergedSessions, ...tempSessions]

        // traceService.trace('SessionLifecycleDebug', 'loadSessions:mergedWithCache', {
          // backendCount: convertedSessions.length,
          // cachedCount: cachedSessions.length,
          // tempCount: tempSessions.length,
          // totalCount: allSessions.length,
          // sessionsWithMessages: allSessions.filter(s => s.messages && s.messages.length > 0).length,
          // tempSessionIds: tempSessions.map(s => s.id)
        // }, ['sync', 'state-change'])

        // Write directly to Zustand (single source of truth)
        hubStore.setSessions(allSessions)
      } else {
        // Backend returned empty - preserve existing cached/temp sessions instead of clearing
        const sessionsToKeep = cachedSessions.filter(s =>
          IdService.isTempId(s.id) || (s.messages && s.messages.length > 0)
        )

        if (sessionsToKeep.length > 0) {
          // traceService.trace('SessionLifecycleDebug', 'loadSessions:backendEmptyKeepingCached', {
            // cachedCount: sessionsToKeep.length,
            // sessionIds: sessionsToKeep.map(s => s.id)
          // }, ['sync', 'state-change'])
          hubStore.setSessions(sessionsToKeep)
        }
        // If no cached/temp sessions either, just keep existing state (don't clear)
      }

      setError(null)
    } catch (sessionErr) {
      // On error, don't clear sessions - keep existing state
      frontendLoggingService.warning('SessionManagement', 'Failed to load sessions, keeping existing state', { error: sessionErr instanceof Error ? sessionErr.message : String(sessionErr) })
      // traceService.trace('SessionLifecycleDebug', 'loadSessions:error', {
        // error: sessionErr instanceof Error ? sessionErr.message : String(sessionErr)
      // }, ['error'])
      setError('Failed to load sessions')
    } finally {
      setIsLoadingSessions(false)
    }
  }, [hubStore])

  /**
   * Create a new session
   */
  const handleCreateSession = useCallback(async (
    title: string,
    agentIdToUse: string,
    model: string
  ): Promise<ConversationSession> => {
    const tempSessionId = IdService.generateTempId()

    // Prevent duplicate session creation
    if (creatingSessionRef.current.has(tempSessionId)) {
      throw new Error('Session creation already in progress')
    }

    creatingSessionRef.current.add(tempSessionId)

    try {
      // Create session on backend first
      const backendSession = await sessionSyncService.createSession(
        tempSessionId,
        title,
        agentIdToUse,
        model
      )

      // Convert to frontend session
      const newSession: ConversationSession = {
        // THE CANONICAL ID TYPE (2026-09-10): every session id in the
        // store is a STRING (IdService.toFrontend). Storing the raw
        // backend number here made the store mixed-type, and raw ===
        // comparisons (the panel's active pin, the send guard) then
        // missed — the active session unpinned and the flow re-created
        // duplicates.
        id: IdService.toFrontend(backendSession.id),
        title: backendSession.title,
        agentId: IdService.toFrontend(backendSession.agent_id),
        messages: [],
        createdAt: new Date(backendSession.created ?? Date.now()),
        updatedAt: new Date(backendSession.updated ?? Date.now()),
        isActive: true
      }

      // [TRACE] Log new session creation
      frontendLoggingService.debug('SessionManagement', `New session created: ${newSession.id}`, {
        sessionId: newSession.id,
        title: newSession.title,
        agentId: newSession.agentId
      })

      // Add to sessions list via hub store
      hubStore.upsertSession(newSession)
      hubStore.setActiveSession(newSession)
      setError(null)

      return newSession
    } finally {
      creatingSessionRef.current.delete(tempSessionId)
    }
  }, [hubStore])

  /**
   * Delete a session
   */
  const handleDeleteSession = useCallback((sessionId: string) => {
    hubStore.removeSession(sessionId)

    if (hubStore.activeSession?.id === sessionId) {
      hubStore.setActiveSession(null)
    }

    // Only sync to backend if this is a real session (has integer ID)
    // Temp sessions (string IDs like "session-123") don't exist on backend yet
    const isTempSession = IdService.isTempId(sessionId)
    if (!isTempSession) {
      sessionSyncService.deleteSession(sessionId).catch((err) => {
        // A DELETE THAT DID NOT HAPPEN MUST SAY SO (2026-09-19, the
        // no-silent-failures rule). The row left the store ABOVE, before
        // this call, so a failure here would leave the UI claiming a
        // deletion the backend never made — and the row would still be
        // there on the next load. Put the list back from the backend (the
        // row returns) and tell the user.
        frontendLoggingService.error(
          'SessionManagement',
          `Session delete failed — reloading the list (session ${sessionId} is still there)`,
          err
        )
        void reloadRef.current?.()
        useNotificationStore.getState().addError(
          'Delete failed',
          'The session is still there — the list has been refreshed.'
        )
      })
    }
  }, [hubStore])

  /**
   * Switch to a different session
   * Loads full session from backend if messages are not cached
   * Note: Does NOT change the currently selected agent - user's explicit
   * agent selection is preserved even when viewing sessions created with other agents
   */
  const handleSwitchSession = useCallback(async (session: ConversationSession) => {
    // [TRACE] Log session selection
    frontendLoggingService.debug('SessionManagement', `Session selected: ${session.title}`, {
      sessionId: session.id,
      sessionTitle: session.title,
      agentId: session.agentId,
      messageCount: session.messages?.length || 0
    })

    // NOTE: We intentionally do NOT restore the agent associated with this session.
    // The user's explicit agent selection (from the dropdown) should be preserved.
    // This allows users to view any session while keeping their chosen active agent.
    const hubState = useCognitiveHubStore.getState()
    const currentAgent = hubState.activeAgent

    if (currentAgent) {
      frontendLoggingService.info('SessionManagement', 'Session switched, keeping current agent', {
        sessionId: session.id,
        activeAgentId: currentAgent.id,
        sessionOriginalAgentId: session.agentId
      })
    }

    // CRITICAL: Get cached session to preserve local changes (title, etc.)
    const cachedSession = hubState.sessions.find(s => s.id === session.id)
    const cachedTitle = cachedSession?.title
    // FIX: Check for both exact match AND timestamp-prefixed "New Session" titles
    // Temp sessions use "New Session {timestamp}" format to prevent collisions
    const isDefaultTitle = cachedTitle === 'New Session' || cachedTitle?.startsWith('New Session ')
    const hasLocalTitleChange = cachedTitle && !isDefaultTitle

    frontendLoggingService.debug('SessionManagement', 'Session switch preparing to load from backend', {
      sessionId: session.id,
      cachedTitle,
      hasLocalTitleChange,
      currentTitle: session.title,
      isDefaultTitle
    })

    // Always reload session from backend to ensure we have the latest messages
    // This fixes issues with temp sessions being replaced by backend sessions
    try {
      const loadStartTime = performance.now()
      frontendLoggingService.debug('SessionManagement', `Loading session from backend`, {
        sessionId: session.id
      })
      const backendSession = await sessionSyncService.getSession(session.id)
      const sessionWithMessages = sessionSyncService.convertToFrontendSession(backendSession)

      // CRITICAL: Preserve local title changes from localStorage
      // Backend doesn't have updated titles (not synced), so we keep the cached title
      // BUT: Default "New Session" titles should be replaced with backend title (if available)
      if (hasLocalTitleChange) {
        sessionWithMessages.title = cachedTitle
        frontendLoggingService.info('SessionManagement', 'Preserved local title change', {
          sessionId: session.id,
          cachedTitle,
          backendTitle: session.title
        })
      } else if (backendSession.title && isDefaultTitle) {
        // Use backend title when cached title is default "New Session"
        sessionWithMessages.title = backendSession.title
        frontendLoggingService.info('SessionManagement', 'Using backend title (replacing default)', {
          sessionId: session.id,
          backendTitle: backendSession.title,
          cachedTitle
        })
      }

      const loadDuration = performance.now() - loadStartTime

      // [TRACE] Log session messages loaded
      frontendLoggingService.debug('SessionManagement', `Session messages loaded from backend`, {
        sessionId: session.id,
        messageCount: sessionWithMessages.messages?.length || 0,
        loadDuration: loadDuration.toFixed(2)
      })

      // Update the session in the hub store
      // FIX: If this was a temp session, replace it with the backend session
      const isTempSession = IdService.isTempId(session.id)
      const backendSessionId = sessionWithMessages.id

      if (isTempSession && session.id !== backendSessionId) {
        // Temp session was replaced by backend session - use replaceSessionById
        frontendLoggingService.info('SessionManagement', 'Replacing temp session with backend session', {
          tempSessionId: session.id,
          backendSessionId,
          title: sessionWithMessages.title
        })
        hubStore.replaceSessionById(session.id, sessionWithMessages)
      } else {
        // Regular session update or temp session with same ID
        hubStore.upsertSession(sessionWithMessages)
      }

      hubStore.setActiveSession(sessionWithMessages)
      hubStore.updateSessionStatus(backendSessionId, 'active')

      frontendLoggingService.debug('SessionManagement', `Session activated`, {
        sessionId: backendSessionId,
        activeSessionId: useCognitiveHubStore.getState().activeSession?.id,
        wasTempSession: isTempSession
      })
    } catch (err) {
      // [TRACE] Log session loading error with proper error details
      const errorDetails = err instanceof Error ? {
        message: err.message,
        stack: err.stack
      } : { error: err }
      frontendLoggingService.warning('SessionManagement', `Failed to load session messages: ${session.id}`, errorDetails)
      // Fallback: use the session we have locally if backend loading fails
      hubStore.setActiveSession(session)
      hubStore.updateSessionStatus(session.id, 'active')
    }
  }, [hubStore])

  /**
   * Rename a session
   * Uses renameSessionById which reads fresh store state atomically,
   * preventing stale-closure overwrites that would erase messages.
   */
  const handleRenameSession = useCallback((sessionId: string, newTitle: string) => {
    hubStore.renameSessionById(sessionId, newTitle)

    // THE TEMP GUARD (2026-09-09, B1): a rename on a temp session
    // used to PUT /sessions/session-<ts>-<rand> -> 404 noise ("the
    // rename did NOT persist") — the temp's title is carried into
    // the real row by the commit flow instead.
    if (IdService.isTempId(sessionId)) {
      return
    }

    // THE RENAME PERSISTENCE (2026-08-25, the medium win — the
    // master.md's gap: 'the frontend renames at the store level
    // only; no server endpoint'): the PUT EXISTS but the frontend
    // never called it — the renames evaporated on the reload (the
    // SessionsService: 'not synced to backend'). The store updates
    // first (the optimistic); the PUT syncs; the failure logs loud
    // (the no-silent-failures rule).
    apiClient
      .put(`/api/v1/sessions/${sessionId}`, { title: newTitle })
      .catch((err) => {
        frontendLoggingService.error(
          'SessionRename',
          `The rename did NOT persist: ${String(err instanceof Error ? err.message : err)}`,
          { sessionId, newTitle },
        )
      })

    // Verify the rename worked
    setTimeout(() => {
      // traceService.trace('useSessionManagement', 'handleRenameSession: verification', {
        // sessionId,
        // newTitle,
        // sessionFound: !!renamedSession,
        // actualTitle: renamedSession?.title,
        // titleMatches: renamedSession?.title === newTitle
      // })
    }, 100)

    // Sync rename to backend
    sessionSyncService.updateSessionTitle(sessionId, newTitle).catch((_err) => {
      // traceService.trace('useSessionManagement', 'handleRenameSession: backend sync failed', {
        // sessionId,
        // error: err instanceof Error ? err.message : String(err)
      // })
    })
  }, [hubStore])

  /**
   * THE SMART RENAME (2026-08-22, user): generate a title from the
   * session's FULL conversation (the local title service — the DB
   * default provider was shadowing it with a reasoning model + a
   * 20-token budget, producing empty titles; fixed via
   * TITLE_LLM_USE_DATABASE_DEFAULT=false + MAX_TOKENS=64).
   */
  const handleSessionSmartRename = useCallback(async (session: { id: string }) => {
    try {
      const res = await fetch(`/api/v1/sessions/${session.id}/title`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error((body as { detail?: string }).detail || 'Title generation failed')
      }
      const data = await res.json() as { title: string }
      if (data.title) {
        hubStore.renameSessionById(session.id, data.title)
        sessionSyncService.updateSessionTitle(session.id, data.title).catch((err) => {
          // THE SAME RULE AS THE DELETE PATH (2026-09-19): the store above
          // already shows the new title, so a failed save would leave this
          // window naming a session the backend still calls something else —
          // and no other tab would ever hear about it. Reload (the old title
          // comes back) and say so.
          frontendLoggingService.error(
            'SessionManagement',
            `Session rename did not save (session ${session.id})`,
            err
          )
          void reloadRef.current?.()
          useNotificationStore.getState().addError(
            'Rename not saved',
            'The title did not stick — the list has been refreshed.'
          )
        })
        // THE RENAME TOAST (2026-08-22, user): confirm the change —
        // the rename has a delay (the local model thinks); the toast
        // affirms the new title landed.
        useNotificationStore.getState().addSuccess(
          'Session renamed',
          `New title: ${data.title}`
        )
      }
    } catch (err) {
      useNotificationStore.getState().addError(
        'Rename failed',
        err instanceof Error ? err.message : 'Could not generate a title'
      )
    }
  }, [hubStore])

  /**
   * Reload all sessions
   */
  const handleReloadSessions = useCallback(async () => {
    try {
      setIsReloadingSessions(true)
      setError(null)

      const backendSessions = await sessionSyncService.reloadSessionsWithMessages(SessionSource.AGENT)
      if (backendSessions && backendSessions.length > 0) {
        const convertedSessions = backendSessions.map(session =>
          sessionSyncService.convertToFrontendSession(session)
        )

        // Write directly to Zustand (single source of truth)
        hubStore.setSessions(convertedSessions)

        // Update current session if it exists in the reloaded sessions
        if (hubStore.activeSession) {
          const updatedCurrentSession = convertedSessions.find(s => s.id === hubStore.activeSession?.id)
          if (updatedCurrentSession) {
            hubStore.setActiveSession(updatedCurrentSession)
          } else {
            // Current session no longer exists in backend (was deleted), clear it
            hubStore.setActiveSession(null)
          }
        }
      } else {
        // No sessions in backend, clear current session and sessions list
        hubStore.setSessions([])
        hubStore.setActiveSession(null)
      }
    } catch (err) {
      setError('Failed to reload sessions: ' + (err instanceof Error ? err.message : 'Unknown error'))
    } finally {
      setIsReloadingSessions(false)
    }
  }, [hubStore])

  // Let the callbacks declared above reach the reload (the failed-delete
  // restore path). Assigned in an effect: the const exists by then.
  useEffect(() => {
    reloadRef.current = handleReloadSessions
  }, [handleReloadSessions])

  /**
   * Clear current session
   */
  const clearCurrentSession = useCallback(() => {
    hubStore.setActiveSession(null)
  }, [hubStore])

  /**
   * Clear messages in current session
   */
  const clearCurrentSessionMessages = useCallback(() => {
    if (hubStore.activeSession) {
      hubStore.setActiveSession({
        ...hubStore.activeSession,
        messages: [],
        updatedAt: new Date()
      })
    }
  }, [hubStore])

  /**
   * Close active session (mark as inactive)
   */
  const closeSession = useCallback(() => {
    hubStore.closeActiveSession()
  }, [hubStore])

  /**
   * Add a local session to the sessions list
   * Used for creating sessions that will be synced to backend asynchronously
   * If a session with the same temp ID pattern exists, it will be updated instead of duplicated
   */
  const addLocalSession = useCallback((session: ConversationSession) => {
    // Get fresh state from store, not from closure
    const state = useCognitiveHubStore.getState()

    // FIX: Only check for exact ID match to prevent false positives
    // The previous logic compared createdAt, title, and agentId which caused
    // sessions created in the same millisecond to be treated as duplicates
    const existingSession = state.sessions.find(s => s.id === session.id)

    if (existingSession) {
      // Session already exists - update it (preserves messages)
      replaceSession(existingSession.id, session)
    } else {
      // Add new session
      hubStore.upsertSession(session)
    }

    // Get fresh state again after upsert
    // traceService.trace('SessionLifecycleDebug', 'addLocalSession:DIAGNOSTIC_AFTER', {
      // sessionId: session.id,
      // sessionIdsAfter: stateAfter.sessions.map(s => s.id),
      
      // // CRITICAL: Where did the session end up?
      // sessionInList: !!sessionInList,
      // sessionInActive: sessionInActive?.id === session.id,
      
      // // Message counts
      // listMessages: sessionInList?.messages?.length || 0,
      // activeMessages: sessionInActive?.messages?.length || 0,
      
      // // Full state
      // activeSessionId: stateAfter.activeSession?.id,
      // allSessionIds: stateAfter.sessions.map(s => s.id)
    // }, ['state-change', 'validation'])

    hubStore.setActiveSession(session)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hubStore])

  /**
   * Add a message to a session
   */
  const addMessageToSession = useCallback((sessionId: string, message: ConversationMessage) => {
    frontendLoggingService.debug('SessionManagement', 'addMessageToSession called', {
      sessionId,
      messageId: message.id,
      role: message.role,
      contentLength: message.content.length
    })
    hubStore.addSessionMessage(sessionId, message)
    frontendLoggingService.debug('SessionManagement', 'addMessageToSession completed', {
      sessionId,
      messageId: message.id
    })
  }, [hubStore])

  /**
   * Update a message content in a session
   */
  const updateMessageInSession = useCallback((sessionId: string, messageId: string, content: string, metadata?: Record<string, unknown>) => {
    hubStore.updateSessionMessage(sessionId, messageId, content, metadata)
  }, [hubStore])

  /**
   * Replace a session (used for updating temp session with real backend ID)
   * This prevents duplicate sessions when backend returns with different ID.
   * replaceSessionById already sets activeSession to the merged session (preserving messages);
   * do NOT call setActiveSession(newSession) here — newSession may carry an empty messages array
   * and would overwrite any messages added to the temp session before the backend responded.
   */
  const replaceSession = useCallback((oldId: string, newSession: ConversationSession) => {
    hubStore.replaceSessionById(oldId, newSession)
  }, [hubStore])

  // Load sessions on mount (inside useEffect to avoid render-time side effects)
  useEffect(() => {
    loadSessions()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])  // Empty deps - only run on mount

  return {
    sessions,
    currentSession,
    isLoadingSessions,
    isReloadingSessions,
    error,
    createSession: handleCreateSession,
    deleteSession: handleDeleteSession,
    switchSession: handleSwitchSession,
    reloadSessions: handleReloadSessions,
    renameSession: handleRenameSession,
    smartRenameSession: handleSessionSmartRename,
    replaceSession,
    clearCurrentSession,
    clearCurrentSessionMessages,
    closeSession,
    addLocalSession,
    addMessage: addMessageToSession,
    updateMessage: updateMessageInSession
  }
}

export default useSessionManagement
