import type { ConversationSession, ConversationMessage } from '@/types/agentInteraction'
import { sessionSyncService, carriedLimitExtras, type BackendSession, type SessionSyncResponse } from '../sessionSyncService'
import { frontendLoggingService } from '../frontendLoggingService'
import { IdService } from './IdService'

/**
 * SessionService - Manage conversation sessions
 *
 * Handles session CRUD operations, backend synchronization, and session state management.
 * Works with cognitiveHubStore for state management.
 *
 * @example
 * ```typescript
 * const sessionService = new SessionService()
 * const sessions = await sessionService.loadSessions()
 * const session = await sessionService.createSession('My Chat', 'agent-1', 'gpt-4')
 * await sessionService.deleteSession(sessionId)
 * ```
 */
export class SessionService {
  /**
   * Load all sessions from backend
   *
   * @returns Array of sessions
   */
  async loadSessions(source?: string): Promise<ConversationSession[]> {
    try {
      // source-scoped (2026-09-04): pass SessionSource.EXA from the
      // Exa surfaces to skip the client-side filter; omit = all
      const backendSessions = await sessionSyncService.getSessions(source as never)

      if (!backendSessions || backendSessions.length === 0) {
        return []
      }

      const sessions = backendSessions.map(session =>
        this.convertBackendSession(session)
      )

      frontendLoggingService.debug('SessionService', `Loaded ${sessions.length} sessions`, {
        sessionCount: sessions.length,
        sessionIds: sessions.map(s => s.id)
      })

      return sessions
    } catch (error) {
      frontendLoggingService.error('SessionService', 'Failed to load sessions', error)
      throw new Error('Failed to load sessions')
    }
  }

  /**
   * Load a single session with messages from backend
   *
   * @param sessionId - The session ID to load
   * @returns Session with messages
   */
  async loadSession(sessionId: string): Promise<ConversationSession> {
    try {
      const backendSession = await sessionSyncService.getSession(sessionId)
      const session = this.convertBackendSession(backendSession)

      frontendLoggingService.debug('SessionService', `Loaded session with messages`, {
        sessionId,
        messageCount: session.messages?.length
      })

      return session
    } catch (error) {
      frontendLoggingService.error('SessionService', 'Failed to load session', error)
      throw new Error(`Failed to load session: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  /**
   * Create a new session
   *
   * @param title - Session title
   * @param agentId - Agent ID
   * @param model - Model name
   * @returns Created session
   */
  async createSession(
    title: string,
    agentId: string,
    model: string
  ): Promise<ConversationSession> {
    const tempSessionId = IdService.generateTempId()

    try {
      frontendLoggingService.debug('SessionService', 'Creating new session', {
        tempSessionId,
        title,
        agentId,
        model
      })

      // Create on backend first
      const backendSession = await sessionSyncService.createSession(
        tempSessionId,
        title,
        agentId,
        model
      )

      // Convert to frontend session
      const session = this.convertBackendSession(backendSession)

      frontendLoggingService.info('SessionService', 'Session created successfully', {
        sessionId: session.id,
        title: session.title
      })

      return session
    } catch (error) {
      frontendLoggingService.error('SessionService', 'Failed to create session', error)
      throw new Error(`Failed to create session: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  /**
   * Delete a session
   * Deletes from backend (if not temp session) and returns success status
   *
   * @param sessionId - Session ID to delete
   * @returns True if deleted successfully
   */
  async deleteSession(sessionId: string): Promise<boolean> {
    // Check if this is a temp session (not yet synced to backend)
    const isTempSession = IdService.isTempId(sessionId)

    if (isTempSession) {
      frontendLoggingService.debug('SessionService', 'Skipping backend delete for temp session', {
        sessionId
      })
      return true
    }

    try {
      await sessionSyncService.deleteSession(sessionId)

      frontendLoggingService.info('SessionService', 'Session deleted successfully', {
        sessionId
      })

      return true
    } catch (error) {
      frontendLoggingService.error('SessionService', 'Failed to delete session', error)
      throw new Error(`Failed to delete session: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  /**
   * Update session title
   *
   * @param sessionId - Session ID
   * @param newTitle - New title
   * @returns Updated session
   */
  async updateSessionTitle(sessionId: string, newTitle: string): Promise<ConversationSession> {
    try {
      await sessionSyncService.updateSessionTitle(sessionId, newTitle)

      frontendLoggingService.debug('SessionService', 'Session title updated', {
        sessionId,
        newTitle
      })

      // Return updated session object (caller merges into state)
      return {
        id: sessionId,
        title: newTitle,
        updatedAt: new Date()
      } as ConversationSession
    } catch (error) {
      frontendLoggingService.error('SessionService', 'Failed to update session title', error)
      throw new Error(`Failed to update session title: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  /**
   * Reload all sessions with messages
   * Used for full synchronization with backend
   *
   * @returns Array of sessions with messages
   */
  async reloadSessionsWithMessages(): Promise<ConversationSession[]> {
    try {
      const backendSessions = await sessionSyncService.reloadSessionsWithMessages()

      if (!backendSessions || backendSessions.length === 0) {
        return []
      }

      const sessions = backendSessions.map(session =>
        this.convertBackendSession(session)
      )

      frontendLoggingService.debug('SessionService', `Reloaded ${sessions.length} sessions with messages`, {
        sessionCount: sessions.length
      })

      return sessions
    } catch (error) {
      frontendLoggingService.error('SessionService', 'Failed to reload sessions', error)
      throw new Error(`Failed to reload sessions: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  /**
   * Convert backend session to frontend session format
   * Accepts both BackendSession and SessionSyncResponse types
   */
  private convertBackendSession(backendSession: BackendSession | SessionSyncResponse): ConversationSession {
    // Handle both BackendSession (has is_active) and SessionSyncResponse (has memory)
    const isActive = 'is_active' in backendSession
      ? backendSession.is_active
      : ('memory' in backendSession ? backendSession.memory : true)
    
    const session: ConversationSession = {
      id: IdService.toFrontend(backendSession.id),
      title: backendSession.title || `New Session ${Date.now()}`,
      agentId: IdService.toFrontend(backendSession.agent_id),
      messages: (backendSession.messages || []).map(msg => {
        // Handle both BackendSession messages (have token_count, etc. directly)
        // and SessionSyncMessage (have metadata object)
        const msgUnknown = msg as Record<string, unknown>
        const hasDirectMetadata = msgUnknown.token_count || msgUnknown.total_time_ms || msgUnknown.model || msgUnknown.provider
        const nestedMetadata = msgUnknown.metadata
        // THE NOTE AND THE FLAGS (2026-09-23): they can arrive nested (the detail
        // endpoint) or on the message itself (older shapes), and this branch LISTS
        // its fields — so it dropped what a limit note rides. `carriedLimitExtras`
        // is the one place the three key names live (see sessionSyncService) and
        // it is fed BOTH shapes, because which one arrives is not this mapper's
        // business to guess.
        const extras = carriedLimitExtras({
          ...((nestedMetadata as Record<string, unknown>) || {}),
          ...msgUnknown,
        })
        
        return {
          id: IdService.toFrontend(msg.id),
          role: msg.role as 'user' | 'assistant' | 'system',
          content: msg.content,
          timestamp: new Date(msg.created_at ?? Date.now()),
          agentId: IdService.toFrontend(backendSession.agent_id),
          metadata: (hasDirectMetadata || Object.keys(extras).length) ? {
            tokenCount: msgUnknown.token_count as number,
            totalTimeMs: msgUnknown.total_time_ms as number,
            tokensPerSecond: msgUnknown.tokens_per_second as number,
            model: msgUnknown.model as string,
            provider: msgUnknown.provider as string,
            ...extras
          } : nestedMetadata as Record<string, unknown>
        }
      }),
      createdAt: new Date(backendSession.created_at ?? Date.now()),
      updatedAt: new Date(backendSession.updated_at ?? Date.now()),
      // THE SOURCE (2026-09-04, the leak dig): the converter DROPPED
      // the source field — the frontend sessions never knew their
      // surface, so the SessionManager source-guard (exa shows only
      // source='exa') filtered EVERYTHING out. Mapped now.
      source: backendSession.source,
      isActive
    }

    return session
  }

  /**
   * Create an empty session (for UI-only temporary sessions)
   *
   * @param title - Session title
   * @param agentId - Agent ID
   * @param model - Model name
   * @returns Temporary session (not synced to backend)
   */
  createTempSession(title: string, agentId: string, _model: string): ConversationSession {
    const now = new Date()
    const tempId = IdService.generateTempId()

    const session: ConversationSession = {
      id: tempId,
      title,
      agentId,
      messages: [],
      createdAt: now,
      updatedAt: now,
      isActive: true
    }

    frontendLoggingService.debug('SessionService', 'Created temporary session', {
      tempId,
      title
    })

    return session
  }

  /**
   * Check if a session ID is a temporary (not synced) session
   *
   * @param sessionId - Session ID to check
   * @returns True if temporary session
   */
  isTempSession(sessionId: string): boolean {
    return IdService.isTempId(sessionId)
  }

  /**
   * Merge messages from two sessions
   * Used when replacing temp session with backend session
   *
   * @param targetSession - Session to merge messages into
   * @param sourceSession - Session to take messages from
   * @returns New session with merged messages
   */
  mergeSessionMessages(
    targetSession: ConversationSession,
    sourceSession: ConversationSession
  ): ConversationSession {
    // If target already has messages, keep them
    // Otherwise use source messages
    const messages = (targetSession.messages?.length || 0) > 0
      ? targetSession.messages
      : sourceSession.messages || []

    return {
      ...sourceSession,
      messages,
      updatedAt: new Date()
    }
  }

  /**
   * Clear session messages
   *
   * @param session - Session to clear
   * @returns Updated session with empty messages
   */
  clearMessages(session: ConversationSession): ConversationSession {
    return {
      ...session,
      messages: [],
      updatedAt: new Date()
    }
  }

  /**
   * Add a message to session (returns updated session, doesn't mutate)
   *
   * @param session - Session to add message to
   * @param message - Message to add
   * @returns Updated session
   */
  addMessage(session: ConversationSession, message: ConversationMessage): ConversationSession {
    return {
      ...session,
      messages: [...(session.messages || []), message],
      updatedAt: new Date()
    }
  }

  /**
   * Update a message in session (returns updated session, doesn't mutate)
   *
   * @param session - Session containing the message
   * @param messageId - Message ID to update
   * @param content - New content
   * @param metadata - Optional metadata
   * @returns Updated session, or null if message not found
   */
  updateMessage(
    session: ConversationSession,
    messageId: string,
    content: string,
    metadata?: Record<string, unknown>
  ): ConversationSession | null {
    const messageIndex = (session.messages || []).findIndex(msg => msg.id === messageId)

    if (messageIndex === -1) {
      return null
    }

    const updatedMessage = {
      ...session.messages![messageIndex],
      content,
      ...(metadata ? { metadata } : {})
    }

    const updatedMessages = [
      ...(session.messages || []).slice(0, messageIndex),
      updatedMessage,
      ...(session.messages || []).slice(messageIndex + 1)
    ]

    return {
      ...session,
      messages: updatedMessages,
      updatedAt: new Date()
    }
  }

  /**
   * Remove a message from session (returns updated session, doesn't mutate)
   *
   * @param session - Session to remove message from
   * @param messageId - Message ID to remove
   * @returns Updated session, or null if message not found
   */
  removeMessage(session: ConversationSession, messageId: string): ConversationSession | null {
    const messageIndex = (session.messages || []).findIndex(msg => msg.id === messageId)

    if (messageIndex === -1) {
      return null
    }

    const updatedMessages = [
      ...(session.messages || []).slice(0, messageIndex),
      ...(session.messages || []).slice(messageIndex + 1)
    ]

    return {
      ...session,
      messages: updatedMessages,
      updatedAt: new Date()
    }
  }

  /**
   * Find a session by ID
   *
   * @param sessions - Array of sessions to search
   * @param sessionId - Session ID to find
   * @returns Found session or undefined
   */
  findById(sessions: ConversationSession[], sessionId: string): ConversationSession | undefined {
    return sessions.find(s => s.id === sessionId)
  }

  /**
   * Get active session from sessions array
   *
   * @param sessions - Array of sessions
   * @returns Active session or undefined
   */
  getActiveSession(sessions: ConversationSession[]): ConversationSession | undefined {
    return sessions.find(s => s.isActive)
  }
}
