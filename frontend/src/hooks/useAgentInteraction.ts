/**
 * useAgentInteraction - Orchestrator Hook
 *
 * Coordinates agent selection, session management, chat streaming, and persistence.
 * This is the main hook for chat interaction functionality.
 */

import { useCallback, useEffect, useRef } from 'react'
import { useAgentSelection } from './useAgentSelection'
import { useSessionManagement } from './useSessionManagement'
import { useChatStreaming } from './useChatStreaming'
import { useChatPersistence } from './useChatPersistence'
import { sessionSyncService } from '../services/sessionSyncService'
import { titleService } from '../services/domain/TitleService'
import { sessionsService } from '../services/domain/SessionsService'
import { currentSessionService } from '../services/domain/CurrentSessionService'
import { frontendLoggingService } from '../services/frontendLoggingService'

import { useNotificationStore } from '../stores/notificationStore'
import { useCognitiveHubStore } from '../stores/cognitiveHubStore'
import { useSettingsStore } from '../stores/settingsStore'
import { resolveTitleModel } from '../utils/titleModelResolver'
import { attachmentService } from '../services/domain/AttachmentService'

import type { Agent, ConversationSession, ConversationMessage, AgentInteractionState } from '../types/agentInteraction'
import type { CognitiveState } from '../services/domain/StreamingService'
import { IdService } from '../services/domain/IdService'

interface UseAgentInteractionReturn {
  // State
  agents: Agent[]
  sessions: ConversationSession[]
  state: AgentInteractionState

  // Agent actions
  handleAgentSelect: (agent: Agent) => void

  // Session actions
  handleSessionSelect: (session: ConversationSession) => Promise<void>
  handleSessionDelete: (sessionId: string) => void
  handleSessionRename: (sessionId: string, newTitle: string) => void
  handleSessionSmartRename: (session: { id: string }) => Promise<void>
  handleGenerateTitle: (sessionId: string) => Promise<void>
  addMessage: (sessionId: string, message: ConversationMessage) => void
  updateMessage: (sessionId: string, messageId: string, content: string, metadata?: Record<string, unknown>) => void
  handleReloadSessions: () => Promise<void>
  handleCloseSession: () => void
  /** Clear the active session without deleting it — the page-start state. */
  handleDeselectSession: () => void
  /** Delete the active session and open a fresh one with the same agent. */
  handleTossSession: () => void

  // Chat actions
  handleSendMessage: (content: string, overrideModel?: string, attachments?: File[]) => Promise<void>
  handleClearMessages: () => void
  handleDeleteMessage: (messageId: string) => Promise<void>
  handleExportConversation: () => Promise<void>
  handleImportSession: (importedSession: ConversationSession) => void
  handleSaveSession: () => Promise<void>
  createNewSession: (agent?: Agent) => ConversationSession | null
  stopStreaming: () => void

  // Selected agent (for backward compatibility)
  selectedAgent: Agent | null

  // Cognitive pipeline state
  cognitiveState: CognitiveState
  getCognitiveState: () => CognitiveState
}

export function useAgentInteraction(): UseAgentInteractionReturn {
  // Use extracted hooks
  const {
    agents,
    isLoadingAgents,
    selectedAgent,
    error: agentError,
    selectAgent
  } = useAgentSelection()

  const {
    sessions,
    currentSession,
    isReloadingSessions,
    error: sessionError,
    deleteSession,
    switchSession,
    reloadSessions,
    renameSession,
    replaceSession,
    clearCurrentSession,
    clearCurrentSessionMessages,
    closeSession,
    addLocalSession,
    addMessage,
    updateMessage,
    smartRenameSession,
  } = useSessionManagement()

  // Commit pending session to backend AFTER streaming completes
  // This ensures messages are preserved during the replacement
  const commitPendingSession = useCallback(async (tempSessionId: string): Promise<string> => {
    const hubState = useCognitiveHubStore.getState()
    const agent = hubState.activeAgent

    // Get session from both sources - prefer activeSession as it has the latest messages
    const sessionInList = hubState.sessions.find(s => s.id === tempSessionId)
    const sessionInActive = hubState.activeSession

    // CRITICAL DIAGNOSTIC: Check where messages actually are
    const listMessages = sessionInList?.messages || []
    const activeMessages = sessionInActive?.messages || []

    // Merge session data, preferring activeSession for messages (most up-to-date)
    const session = sessionInList || sessionInActive
    const messages = activeMessages.length > 0
      ? activeMessages
      : listMessages

    // FIX: Check if session already has a backend ID (not a temp ID)
    // If backend created session during streaming, skip commit to prevent duplicates
    const isStillTempSession = IdService.isTempId(tempSessionId)
    
    if (!isStillTempSession && session) {
      // Session was already updated with backend ID during streaming
      // No need to create a new session - backend already did it
      frontendLoggingService.info('SessionLifecycle', 'commitPendingSession:SKIPPED', {
        reason: 'Backend already created session during streaming',
        sessionId: session.id,
        sessionTitle: session.title,
        messagesCount: messages.length
      })
      
      // Just ensure pendingSession flag is cleared
      hubState.setPendingSession(false)
      return session.id
    }

    // traceService.trace('SessionLifecycleDebug', 'commitPendingSession:DIAGNOSTIC', {
      // tempSessionId,
      // // Where is the session?
      // sessionInList: !!sessionInList,
      // sessionInActive: !!sessionInActive,
      // sessionInListId: sessionInList?.id,
      // sessionInActiveId: sessionInActive?.id,
      
      // // CRITICAL: Message counts from each source
      // messagesInList: listMessages.length,
      // messagesInActive: activeMessages.length,
      // messagesUsed: messages.length,
      
      // // Message details for verification
      // listMessageIds: listMessages.map(m => m.id),
      // activeMessageIds: activeMessages.map(m => m.id),
      
      // // Session details
      // sessionTitle: session?.title,
      // totalSessions: hubState.sessions.length,
      // messagesFromActiveSession: activeMessages.length > 0,
      
      // // Full session IDs in list
      // allSessionIdsInList: hubState.sessions.map(s => s.id)
    // }, ['lifecycle', 'api-call'])

    if (!session || !agent) {
      // traceService.trace('SessionLifecycleDebug', 'commitPendingSession:ERROR', {
        // tempSessionId,
        // hasSession: !!session,
        // hasAgent: !!agent
      // }, ['error'])
      throw new Error('No session or agent available')
    }

    // FIX: Use the actual session title, not a fallback
    // The session title should already be unique (e.g., "New Session {timestamp}")
    const sessionTitle = session.title || `New Session ${Date.now()}`
    
    const backendSession = await sessionSyncService.createSession(
      session.id,
      sessionTitle,
      agent.id,
      agent.model
    )

    // traceService.trace('SessionLifecycleDebug', 'backendSessionCreated', {
      // tempSessionId,
      // backendSessionId: backendSession.id,
      // backendTitle: backendSession.title,
      // messagesBeingCommitted: messages.length,
      // titleUsedForCreate: session.title ?? 'New Session'
    // }, ['api-call'])

    // Replace session, preserving messages from activeSession (most up-to-date)
    // FIX: Use backend session title if available, otherwise keep temp title
    // This prevents "New Session {timestamp}" titles from persisting after commit
    const finalTitle = backendSession.title || session.title

    // traceService.trace('SessionLifecycleDebug', 'replaceSession:BEFORE', {
      // tempSessionId,
      // backendSessionId: backendSession.id,
      // oldTitle: session.title,
      // newTitle: finalTitle,
      // sessionsBefore: hubState.sessions.length,
      // sessionIdsBefore: hubState.sessions.map(s => s.id)
    // }, ['state-change'])

    replaceSession(tempSessionId, {
      ...session,
      id: backendSession.id,
      title: finalTitle,
      messages: messages,  // Use merged messages
      createdAt: new Date(backendSession.created ?? Date.now()),
      updatedAt: new Date(backendSession.updated ?? Date.now())
    })

    // CRITICAL DIAGNOSTIC: Verify the replace worked
    // traceService.trace('SessionLifecycleDebug', 'replaceSessionById:POST_DIAGNOSTIC', {
      // tempSessionId,
      // backendSessionId: backendSession.id,

      // // Did temp session get removed?
      // tempSessionStillInList: !!postReplaceState.sessions.find(s => s.id === tempSessionId),

      // // Is backend session in the list?
      // backendSessionInList: !!replacedSessionInList,
      // backendSessionInActive: replacedSessionInActive?.id === backendSession.id,

      // // CRITICAL: What are the titles?
      // backendSessionTitle: replacedSessionInList?.title,
      // activeSessionTitle: replacedSessionInActive?.title,

      // // Message counts after replace
      // listSessionMessages: replacedSessionInList?.messages?.length || 0,
      // activeSessionMessages: replacedSessionInActive?.messages?.length || 0,

      // // Session count
      // totalSessionsAfter: postReplaceState.sessions.length,
      // allSessionIdsAfter: postReplaceState.sessions.map(s => s.id),
      // allSessionTitlesAfter: postReplaceState.sessions.map(s => s.title),

      // // Check for duplicates
      // hasDuplicateSessions: postReplaceState.sessions.filter(s =>
        // s.title === 'New Session'
      // ).length
    // }, ['state-change', 'validation'])

    // traceService.trace('SessionLifecycleDebug', 'replaceSessionByIdComplete', {
      // tempSessionId,
      // backendSessionId: backendSession.id,
      // sessionsCount: postReplaceState.sessions.length,
      // sessionIds: postReplaceState.sessions.map(s => s.id),
      // activeSessionId: postReplaceState.activeSession?.id,
      // messagesPreserved: messages.length
    // }, ['state-change'])

    hubState.setPendingSession(false)
    return backendSession.id
  }, [replaceSession])

  // Stream callbacks

  // THE TEMP-SWAP RESOLVER (2026-09-09, B1 — the vanished bubble):
  // the streaming callbacks capture the session id at the stream
  // START (often a temp), but the backend's session_id event swaps
  // the temp for the real row mid-stream. Message writes to the old
  // temp id then hit "session not found" and were silently dropped —
  // the assistant bubble never appeared. Resolve the write target to
  // the live session (the swap sets the real row active).
  const resolveLiveSessionId = useCallback((sessionId: string): string | null => {
    if (!sessionId) return null
    const hub = useCognitiveHubStore.getState()
    if (hub.sessions.some(s => s.id === sessionId) || hub.activeSession?.id === sessionId) {
      return sessionId
    }
    // The requested session is gone (a temp that got swapped) —
    // the active session is the swap's landing row.
    const active = hub.activeSession
    if (active && !IdService.isTempId(active.id)) {
      frontendLoggingService.info('AgentInteraction', 'resolveLiveSessionId: temp swapped, redirecting to the live session', {
        requested: sessionId,
        live: active.id,
      })
      return active.id
    }
    return null
  }, [])

  const handleStreamComplete = useCallback((message: ConversationMessage) => {
    // traceService.trace('ChatFlow', 'handleStreamComplete', {
      // messageId: message.id,
      // messageRole: message.role,
      // contentLength: message.content.length
    // })

    // CRITICAL: Get fresh session from store instead of using stale closure
    const hubState = useCognitiveHubStore.getState()
    const currentSession = hubState.activeSession

    if (currentSession) {
      // traceService.trace('ChatFlow', 'updateMessage', {
        // sessionId: currentSession.id,
        // messageId: message.id
      // })
      updateMessage(currentSession.id, message.id, message.content, message.metadata as unknown as Record<string, unknown> | undefined)

      // TITLE SERVICE DEBUG: Log before async block
      // traceService.trace('TitleService', 'handleStreamComplete: BEFORE async block', {
        // sessionId: currentSession.id,
        // messageId: message.id,
        // messageRole: message.role
      // })

      // CRITICAL: Wait for Zustand update to complete before committing
      // useLayoutEffect runs after DOM mutations but before paint, ensuring store is updated
      // We use a microtask to ensure the update is processed
      Promise.resolve().then(() => {
        // Commit temp session to backend AFTER streaming completes and messages are added
        const freshState = useCognitiveHubStore.getState()
        const freshSession = freshState.activeSession

        if (freshSession) {
          const isTempSession = IdService.isTempId(freshSession.id)
          if (isTempSession) {
            // traceService.trace('ChatFlow', 'commitPendingSession (in handleStreamComplete)', {
              // sessionId: freshSession.id,
              // messagesCount: freshSession.messages?.length
            // })
            commitPendingSession(freshSession.id).catch(_err => {
              // traceService.trace('ChatFlow', 'commitPendingSession failed', { error: String(_err) })
            })
          }

          // TITLE SERVICE: Generate title after first assistant message
          const messagesCount = freshSession.messages?.length || 0
          // Trigger if: no title, OR title starts with "New Session" (covers both "New Session" and "New Session {timestamp}")
          const needsTitle = !freshSession.title?.trim() || freshSession.title.startsWith('New Session')

          frontendLoggingService.debug('TitleService', 'checking title generation conditions', {
            sessionId: freshSession.id,
            messagesCount,
            currentTitle: freshSession.title,
            needsTitle,
            isTempSession,
            hasAgent: !!freshState.activeAgent,
            sessionAgentId: freshSession.agentId
          })
          
          if (messagesCount >= 2 && needsTitle) {
            // Get first user message
            const firstMessage = freshSession.messages?.find(m => m.role === 'user')?.content || ''

            // Get agent from hub state OR from session's agentId
            let agent = freshState.activeAgent
            if (!agent && freshSession.agentId) {
              // Fallback: get agent from cognitive hub store by ID
              const hubStoreState = useCognitiveHubStore.getState()
              const foundAgent = hubStoreState.agents.find(a => IdService.equals(a.id, freshSession.agentId))
              if (foundAgent) {
                agent = foundAgent
              }
              frontendLoggingService.debug('TitleService', 'got agent from cognitiveHubStore fallback', {
                agentId: freshSession.agentId,
                foundAgent: !!foundAgent,
                agentName: foundAgent?.name
              })
            }

            if (firstMessage && agent) {
              const general = useSettingsStore.getState().settings.general
              const autoTitleEnabled = general?.enableAutoTitle ?? true
              const titleModelPref = general?.titleModelPreference ?? 'agent'
              // The ONE shared resolver (2026-09-03): agent / custom /
              // backend_default — same source as the rename paths.
              const modelString = resolveTitleModel(agent, general)

              frontendLoggingService.info('TitleService', 'triggering auto title generation', {
                sessionId: freshSession.id,
                messagesCount,
                autoTitleEnabled,
                titleModelPref,
                model: modelString ?? 'backend_default',
                currentTitle: freshSession.title,
                firstMessagePreview: firstMessage.substring(0, 50)
              })

              try {
                titleService.generateTitleInBackground(
                  freshSession.id,
                  firstMessage,
                  modelString,
                  autoTitleEnabled
                )
                frontendLoggingService.info('TitleService', 'title generation job queued', {
                  sessionId: freshSession.id,
                  modelString
                })
              } catch (err) {
                frontendLoggingService.error('TitleService', 'auto title generation failed', err, {
                  sessionId: freshSession.id,
                  error: String(err)
                })
              }
            } else {
              frontendLoggingService.warning('TitleService', 'missing firstMessage or agent', {
                sessionId: freshSession.id,
                hasFirstMessage: !!firstMessage,
                hasAgent: !!agent,
                sessionAgentId: freshSession.agentId,
                activeAgentId: freshState.activeAgent?.id
              })
            }
          } else {
            frontendLoggingService.debug('TitleService', 'NOT triggering - conditions not met', {
              sessionId: freshSession.id,
              messagesCount,
              needsTitle,
              messagesCheck: messagesCount >= 2
            })
          }
        }
      })
    } else {
      // traceService.trace('ChatFlow', 'handleStreamComplete: NO CURRENT SESSION', {
        // messageId: message.id,
        // activeSessionId: hubState.activeSession?.id,
        // sessionsCount: hubState.sessions.length
      // })
    }
  }, [updateMessage, commitPendingSession])

  const handleStreamStart = useCallback(() => {
    frontendLoggingService.debug('AgentInteraction', 'Stream started')
  }, [])

  const handleStreamError = useCallback((err: Error) => {
    frontendLoggingService.error('AgentInteraction', 'Stream error', err)

    // A hard LIMIT STOP is not a failure (D.3): the turn was stopped on purpose,
    // the partial answer is kept, and the streaming service already said so in the
    // right tone. "Agent failed" would claim a fault that did not happen.
    if ((err as Error & { errorType?: string }).errorType === 'limit_stop') return

    // Agent-aware toast — the user should know WHICH agent failed and why.
    // (The StreamingService fires a generic provider/model toast; this adds
    // the agent context on the primary chat surface.)
    const agentName = selectedAgent?.name || 'Agent'
    const agentProvider = selectedAgent?.provider
    const agentModel = selectedAgent?.model
    const detail = agentProvider && agentModel
      ? `${agentProvider}/${agentModel}`
      : 'unknown provider/model'
    useNotificationStore.getState().addError(
      `Agent "${agentName}" failed`,
      `${err.message} (${detail})`,
      8000
    )
  }, [selectedAgent])

  const {
    isStreaming,
    error: streamingError,
    startStream,
    stopStream,
    cognitiveState,
    getCognitiveState
  } = useChatStreaming({
    agent: selectedAgent,
    session: currentSession,
    onMessageComplete: handleStreamComplete,
    onStreamStart: handleStreamStart,
    onStreamError: handleStreamError,
    onAddMessage: (message, sessionId) => {
      frontendLoggingService.debug('AgentInteraction', 'onAddMessage callback', {
        messageId: message.id,
        role: message.role,
        sessionId: sessionId,
        hasSession: !!sessionId,
        messageContentPreview: message.content.substring(0, 50)
      })
      const liveId = resolveLiveSessionId(sessionId)
      if (liveId) {
        frontendLoggingService.debug('AgentInteraction', 'Calling addMessage', {
          sessionId: liveId,
          messageId: message.id
        })
        addMessage(liveId, message)
      } else {
        frontendLoggingService.debug('AgentInteraction', 'No session ID provided, skipping addMessage', {
          messageId: message.id
        })
      }
    },
    onUpdateMessage: (messageId, content, metadata, sessionId) => {
      frontendLoggingService.debug('AgentInteraction', 'onUpdateMessage callback', {
        messageId,
        contentLength: content.length,
        sessionId: sessionId,
        hasSession: !!sessionId
      })
      const liveId = resolveLiveSessionId(sessionId ?? '')
      if (liveId) {
        frontendLoggingService.debug('AgentInteraction', 'Calling updateMessage', {
          sessionId: liveId,
          messageId
        })
        updateMessage(liveId, messageId, content, metadata as unknown as Record<string, unknown> | undefined)
      } else {
        frontendLoggingService.debug('AgentInteraction', 'No session ID provided, skipping updateMessage', {
          messageId
        })
      }
    }
  })

  const { restoredState } = useChatPersistence({
    selectedAgentId: selectedAgent?.id || null,
    currentSessionId: currentSession?.id || null
  })

  // Restore session from persistence on mount
  const hasRestoredRef = useRef(false)
  useEffect(() => {
    if (hasRestoredRef.current) return
    if (!restoredState?.currentSessionId) return

    const hasBackendSessions = sessions.some(s => !IdService.isTempId(s.id))
    if (!hasBackendSessions) return

    hasRestoredRef.current = true

    const { activeSession } = useCognitiveHubStore.getState()
    if ((activeSession?.messages?.length ?? 0) > 0) return

    const sessionToRestore = sessions.find(s => IdService.equals(s.id, restoredState.currentSessionId))
    if (sessionToRestore) {
      frontendLoggingService.info('AgentInteraction', 'Restoring session from persistence', {
        sessionId: sessionToRestore.id,
        sessionTitle: sessionToRestore.title
      })
      switchSession(sessionToRestore)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [restoredState?.currentSessionId, sessions.length, switchSession])

  // Sessions are loaded by useSessionManagement hook
  // No need to load here - would cause duplicate loading

  // Subscribe to session changes from SessionsService (which reads from Zustand)
  useEffect(() => {
    const unsubscribe = sessionsService.subscribe((_sessions) => {
      // Sessions are already in Zustand, no merge needed
      // This subscription is for backward compatibility only
      // traceService.trace('AgentInteraction', 'SessionsService subscription callback', {
        // sessionCount: sessions.length
      // })
    })

    return () => {
      unsubscribe()
    }
  }, [])

  // Update CurrentSessionService when session/agent changes
  useEffect(() => {
    currentSessionService.setContext(currentSession, selectedAgent)
  }, [currentSession, selectedAgent])

  // Combine errors
  const error = agentError || sessionError || streamingError

  // (THE EXA-CHAT BRIDGE — REMOVED in the _21 purge (2026-08-28):
  // the Exa's on its own first-class page now — the sendToExa +
  // the resolveExaApproval + the ws-bridge's all gone!)
  const handleSendMessage = useCallback(async (content: string, overrideModel?: string, attachments?: File[]) => {
    // traceService.trace('ChatFlow', 'handleSendMessage', { contentLength: content.length })


    const state = useCognitiveHubStore.getState()
    const providerStatus = state.activeProvider ? state.providerHealth[state.activeProvider] : 'up'

    if (providerStatus === 'down') {
      throw new Error(`Provider ${state.activeProvider} is currently unavailable`)
    }

    const freshState = useCognitiveHubStore.getState()
    const freshSession = freshState.activeSession

    if (!freshSession) {
      // traceService.trace('ChatFlow', 'noSession', { error: 'No session available' })
      throw new Error('No session available')
    }

    // Upload attachments and collect IDs
    let attachmentIds: number[] | undefined
    if (attachments && attachments.length > 0) {
      try {
        const sessionId = parseInt(freshSession.id)
        frontendLoggingService.info('AttachmentUpload', `Uploading ${attachments.length} file(s)`, {
          sessionId,
          fileCount: attachments.length,
          fileNames: attachments.map(f => f.name)
        })

        // Upload all files and collect their IDs
        attachmentIds = []
        for (let i = 0; i < attachments.length; i++) {
          const file = attachments[i]
          const result = await attachmentService.uploadAttachment(sessionId, file)
          attachmentIds.push(result.id)
          frontendLoggingService.info('AttachmentUpload', `File uploaded: ${result.original_filename}`, {
            attachmentId: result.id,
            fileSize: result.file_size
          })
        }
      } catch (error) {
        frontendLoggingService.error('AttachmentUpload', 'Failed to upload attachments', error as Error)
        // Continue without attachments if upload fails
        attachmentIds = undefined
      }
    }

    // NOTE: User message is added by StreamingService via onAddMessage callback
    // We do NOT add it here to avoid duplicates

    // NOTE: Temp session commit moved to handleStreamComplete (AFTER streaming)
    // This ensures messages are added BEFORE the session is replaced

    // traceService.trace('ChatFlow', 'startStream', { contentLength: content.length })
    await startStream(content, overrideModel, attachmentIds)
    // traceService.trace('ChatFlow', 'handleSendMessageComplete', { sessionId: useCognitiveHubStore.getState().activeSession?.id })
  }, [startStream])

  // Create new session (lazy - not synced until first message)
  const createNewSession = useCallback((agent?: Agent) => {
    const agentToUse = agent || selectedAgent
    if (!agentToUse) return null

    // FIX: Use unique temp session ID to prevent collisions
    // Format: session-{timestamp}-{random} to ensure uniqueness even with rapid creation
    const tempSessionId = IdService.generateTempId()
    
    // FIX: Use unique temporary title to prevent "New Session" placeholder collision
    // This ensures each session has a unique title even before title generation
    const uniqueTitle = `New Session ${Date.now()}`
    
    const newSession: ConversationSession = {
      id: tempSessionId,
      title: uniqueTitle,
      agentId: agentToUse.id,
      messages: [],
      createdAt: new Date(),
      updatedAt: new Date(),
      isActive: true
    }

    // traceService.trace('SessionLifecycleDebug', 'createNewSession', {
      // tempSessionId,
      // title: 'New Session',
      // agentId: agentToUse.id,
      // sessionsBefore: useCognitiveHubStore.getState().sessions.length
    // }, ['lifecycle'])

    addLocalSession(newSession)
    useCognitiveHubStore.getState().setPendingSession(true)

    // traceService.trace('SessionLifecycleDebug', 'createNewSessionComplete', {
      // tempSessionId,
      // sessionsAfter: useCognitiveHubStore.getState().sessions.length,
      // activeSessionId: useCognitiveHubStore.getState().activeSession?.id
    // }, ['lifecycle', 'state-change'])

    return newSession
  }, [selectedAgent, addLocalSession])

  // Delete message
  const handleDeleteMessage = useCallback(async (messageId: string) => {
    if (currentSession) {
      try {
        await sessionSyncService.deleteMessage(currentSession.id, messageId)
      } catch {
        frontendLoggingService.warning('AgentInteraction', 'Failed to delete message', { messageId })
      }
    }
  }, [currentSession])

  // Export conversation
  const handleExportConversation = useCallback(async () => {
    if (!currentSession) {
      useNotificationStore.getState().addError('No Active Session', 'There is no session to export.')
      return
    }

    try {
      const exportData = {
        sessionId: currentSession.id,
        agentName: selectedAgent?.name || 'Unknown',
        exportedAt: new Date().toISOString(),
        messages: currentSession.messages || []
      }

      const textContent = exportData.messages.map((msg: ConversationMessage) =>
        `[${new Date(msg.timestamp).toLocaleString()}] ${msg.role.toUpperCase()}: ${msg.content}`
      ).join('\n\n')

      const header = `Conversation Export\nAgent: ${exportData.agentName}\nExported: ${exportData.exportedAt}\nMessages: ${exportData.messages.length}\n${'='.repeat(50)}\n\n`

      const blob = new Blob([header + textContent], { type: 'text/plain' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `conversation-${currentSession.id}-${Date.now()}.txt`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)

      useNotificationStore.getState().addSuccess('Export Complete', `${exportData.messages.length} messages saved.`)
    } catch (err) {
      useNotificationStore.getState().addError('Export Failed', err instanceof Error ? err.message : 'Failed to export')
    }
  }, [currentSession, selectedAgent])

  // Import session
  const handleImportSession = useCallback((importedSession: ConversationSession) => {
    const newSession: ConversationSession = {
      ...importedSession,
      id: IdService.generateTempId(),
      createdAt: new Date(),
      updatedAt: new Date()
    }
    
    // FIX: Log warning when model is missing instead of silent fallback
    const sessionModel = selectedAgent?.model || 'llama3.1:latest'
    if (!selectedAgent?.model) {
      frontendLoggingService.warning('AgentInteraction', 'Agent model missing, using fallback', {
        agentId: selectedAgent?.id,
        agentName: selectedAgent?.name,
        fallbackModel: sessionModel
      })
    }

    sessionSyncService.createSession(
      newSession.id,
      newSession.title,
      newSession.agentId,
      sessionModel
    ).catch(err => {
      frontendLoggingService.warning('AgentInteraction', 'Failed to sync imported session', { error: err })
    })
  }, [selectedAgent])

  // Save session
  const handleSaveSession = useCallback(async () => {
    if (!currentSession) return

    try {
      await sessionSyncService.updateSessionTitle(currentSession.id, currentSession.title)

      for (const message of currentSession.messages || []) {
        await sessionSyncService.syncMessage(currentSession.id, message).catch(() => {
          setTimeout(() => sessionSyncService.syncMessage(currentSession.id, message).catch(() => {}), 1000)
        })
      }
    } catch (err) {
      frontendLoggingService.error('AgentInteraction', 'Failed to save session', err)
    }
  }, [currentSession])

  // Generate title for a session (called from Rename button)
  const handleGenerateTitle = useCallback(async (sessionId: string): Promise<void> => {
    // traceService.trace('SessionActions', 'handleGenerateTitle called', {
      // sessionId
    // })

    const hubState = useCognitiveHubStore.getState()
    const session = hubState.sessions.find(s => s.id === sessionId)

    const sessionMessages = session?.messages || []
    if (!session || sessionMessages.length < 2) {
      // traceService.trace('SessionActions', 'handleGenerateTitle: insufficient messages', {
        // sessionId,
        // hasSession: !!session,
        // messageCount: sessionMessages.length,
        // hasAtLeastTwoMessages: sessionMessages.length >= 2
      // })
      throw new Error('Need at least 2 messages (user + assistant) to generate title')
    }

    // Find assistant messages
    const assistantMessages = sessionMessages.filter(msg => msg.role === 'assistant')
    
    if (assistantMessages.length === 0) {
      // traceService.trace('SessionActions', 'handleGenerateTitle: no assistant messages', {
        // sessionId,
        // totalMessages: sessionMessages.length,
        // userMessages: sessionMessages.filter(msg => msg.role === 'user').length
      // })
      throw new Error('No assistant messages found to generate title from')
    }

    // Use full conversation for better title context
    const assistantMessageContent = sessionMessages
      .slice(-10)  // last 10 messages max
      .map(m => `${m.role}: ${(m.content || '').substring(0, 500)}`)
      .join('\n')
    
    // Get agent from session's agentId (preferred) or fall back to activeAgent
    const hubStoreState = useCognitiveHubStore.getState()
    const agentFromSession = hubStoreState.agents.find(a => IdService.equals(a.id, session.agentId))
    const agent = agentFromSession || hubState.activeAgent

    if (!assistantMessageContent || !agent) {
      // traceService.trace('SessionActions', 'handleGenerateTitle: missing data', {
        // sessionId,
        // hasAssistantMessage: !!assistantMessageContent,
        // hasAgent: !!agent,
        // agentId: session.agentId,
        // foundAgentById: !!agentFromSession,
        // hasActiveAgent: !!hubState.activeAgent,
        // assistantMessageLength: assistantMessageContent.length
      // })
      throw new Error(
        agentFromSession
          ? 'Missing assistant message to generate title from'
          : 'Missing agent information. Session has no associated agent or no active agent selected.'
      )
    }

    // traceService.trace('SessionActions', 'handleGenerateTitle: calling titleService', {
      // sessionId,
      // model: `${agent.provider}/${agent.model}`,
      // assistantMessagePreview: assistantMessageContent.substring(0, 100),
      // totalAssistantMessages: assistantMessages.length
    // })

    // Resolve model string from the title preference — the ONE shared
    // resolver (2026-09-03, the Local Services arc): agent / custom /
    // backend_default. The Sessions-page smart rename uses the same.
    const settings = useSettingsStore.getState().settings.general
    const resolvedModelString = resolveTitleModel(agent, settings)

    // Use titleService to generate title
    titleService.generateTitleInBackground(
      sessionId,
      assistantMessageContent,
      resolvedModelString,
      true // User explicitly requested title generation
    )

    // Show toast when complete (titleService already shows toasts)
    // traceService.trace('SessionActions', 'handleGenerateTitle: title generation queued', {
      // sessionId
    // })
  }, [])

  // Build state object
  const state: AgentInteractionState = {
    selectedAgent,
    currentSession,
    isStreaming,
    connectionStatus: 'idle',
    error,
    isLoadingAgents,
    isReloadingSessions
  }

  /**
   * THE DESELECT BUTTON (2026-09-11, the user's ask — "sometimes I want to
   * select nothing. That is a gap I have noticed"). Clears the active session
   * without deleting it. Nothing new is modelled: this is exactly the state
   * the page starts in, and `disabled={!currentSession}` in AgentInteraction
   * already blanks the input with "Select or create a session to start
   * chatting..." — so the behaviour is the existing one, just reachable.
   */
  const handleDeselectSession = useCallback(() => {
    frontendLoggingService.info('useAgentInteraction:deselectSession', 'Session deselected', {
      sessionId: currentSession?.id ?? null,
    })
    clearCurrentSession()
  }, [clearCurrentSession, currentSession])

  /**
   * THE TOSS BUTTON (2026-09-11, the user's ask — "I want to be able to throw
   * chats away quickly and start a new chat with one button push"): delete the
   * current session and open a fresh one with the SAME agent.
   *
   * No confirm and no toast — the user's call: the new blank session is its own
   * confirmation. The log line names what was tossed, so the act is auditable
   * afterwards without a notification interrupting the flow.
   *
   * `deleteSession` already tolerates a temp id (a session created but never
   * persisted has no backend row), so the empty-session case needs no guard
   * here.
   */
  const handleTossSession = useCallback(() => {
    const victim = currentSession
    const agent = selectedAgent ?? undefined
    if (victim) {
      frontendLoggingService.info('useAgentInteraction:tossSession', 'Session tossed — starting fresh', {
        sessionId: victim.id,
        title: victim.title,
        messageCount: victim.messages?.length ?? 0,
        agentId: agent?.id,
      })
      deleteSession(victim.id)
    }
    createNewSession(agent)
  }, [currentSession, selectedAgent, deleteSession, createNewSession])

  return {
    // State
    agents,
    sessions,
    state,

    // Agent actions
    handleAgentSelect: selectAgent,

    // Session actions
    handleSessionSelect: switchSession,
    handleSessionDelete: deleteSession,
    handleSessionRename: renameSession,
    handleSessionSmartRename: smartRenameSession,
    handleGenerateTitle,
    handleReloadSessions: reloadSessions,
    handleCloseSession: closeSession,
    handleDeselectSession,
    handleTossSession,

    // Chat actions
    handleSendMessage,
    addMessage,
    updateMessage,
    handleClearMessages: clearCurrentSessionMessages,
    handleDeleteMessage,
    handleExportConversation,
    handleImportSession,
    handleSaveSession,
    createNewSession,
    stopStreaming: stopStream,

    // Selected agent
    selectedAgent,

    // Cognitive pipeline state
    cognitiveState,
    getCognitiveState,
  }
}

export default useAgentInteraction
