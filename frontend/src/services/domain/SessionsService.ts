/**
 * SessionsService - Thin wrapper for session state management
 *
 * REDESIGNED: This service no longer maintains its own cache.
 * It writes directly to the Zustand store (single source of truth).
 *
 * Purpose:
 * - Direct writes to Zustand store
 * - Background sync with backend (titles-only loading)
 * - Backward compatibility for existing consumers
 *
 * Benefits:
 * - Single source of truth (Zustand only)
 * - No state sync issues
 * - Lazy loading support (titles only by default)
 */

import { sessionSyncService, carriedLimitExtras, type SessionSyncResponse } from '../sessionSyncService'

import { frontendLoggingService } from '../frontendLoggingService'
import { useCognitiveHubStore } from '@/stores/cognitiveHubStore'
import type { ConversationSession, ConversationMessage } from '@/types/agentInteraction'

type SessionSubscriber = (sessions: ConversationSession[]) => void

export class SessionsService {
  private subscribers: Set<SessionSubscriber> = new Set()
  private syncInterval: ReturnType<typeof setInterval> | null = null
  private isLoading: boolean = false
  private lastSyncTime: Date | null = null

  constructor() {
    // Start background sync
    this.startBackgroundSync()
    // traceService.trace('SessionsService', 'initialized', {}, ['lifecycle', 'sync'])
  }

  /**
   * Get all sessions from Zustand store
   */
  getSessions(): ConversationSession[] {
    return [...useCognitiveHubStore.getState().sessions]
  }

  /**
   * Get single session from Zustand store by ID
   */
  getSession(sessionId: string): ConversationSession | null {
    return useCognitiveHubStore.getState().sessions.find(s => s.id === sessionId) || null
  }

  /**
   * Get current/active session from Zustand store
   */
  getCurrentSession(): ConversationSession | null {
    const state = useCognitiveHubStore.getState()
    return state.activeSession || state.sessions.find(s => s.isActive) || null
  }

  /**
   * Subscribe to session changes (reads from Zustand)
   *
   * @param callback - Function called when sessions change
   * @returns Unsubscribe function
   */
  subscribe(callback: SessionSubscriber): () => void {
    // Track subscriber for status reporting
    this.subscribers.add(callback)

    // Subscribe to Zustand store changes
    const unsubscribe = useCognitiveHubStore.subscribe(
      (state) => {
        callback(state.sessions)
      }
    )

    // Immediately call with current state
    const currentSessions = this.getSessions()
    // traceService.trace('SessionsService', 'subscribe:initial call', {
      // sessionCount: currentSessions.length,
      // sessionIds: currentSessions.map(s => s.id)
    // }, ['state-change'])
    callback(currentSessions)

    // Return cleanup function that removes from local set and Zustand
    return () => {
      this.subscribers.delete(callback)
      unsubscribe()
    }
  }

  /**
   * Load sessions from backend and update Zustand store
   * Uses titles-only loading by default (fast, lazy loading)
   * Set includeMessages=true to load full message history from database
   */
  async loadFromBackend(includeMessages: boolean = false): Promise<void> {
    if (this.isLoading) {
      // traceService.trace('SessionLifecycleDebug', 'loadFromBackend:alreadyLoading', {}, ['sync'])
      return
    }

    this.isLoading = true
    const hubStateBefore = useCognitiveHubStore.getState()
    const cachedSessions = hubStateBefore.sessions
    // traceService.trace('SessionLifecycleDebug', 'loadFromBackendEntry', {
      // includeMessages,
      // cachedSessionsCount: cachedSessions.length,
      // tempSessionsCount: tempSessionsBefore.length,
      // currentSessionIds: cachedSessions.map(s => s.id)
    // }, ['sync', 'lifecycle'])

    try {
      // Load sessions with optional messages
      // includeMessages=true: loads full message history from database (slower)
      // includeMessages=false: loads titles only (fast, lazy loading)
      let backendSessions: SessionSyncResponse[]
      if (includeMessages) {
        backendSessions = await sessionSyncService.reloadSessionsWithMessages()
      } else {
        backendSessions = await sessionSyncService.getSessions()
      }

      // Convert backend sessions to frontend format
      const sessions = backendSessions.map(backend => ({
        id: backend.id,
        title: backend.title,
        agentId: backend.agent_id,
        messages: (backend.messages || []).map(msg => ({
          id: msg.id,
          role: msg.role as 'user' | 'assistant' | 'system',
          content: msg.content,
          timestamp: this.parseTimestamp(msg.created_at),
          agentId: backend.agent_id,
          metadata: msg.metadata ? {
            tokenCount: msg.metadata.tokenCount,
            totalTimeMs: msg.metadata.totalTimeMs,
            tokensPerSecond: msg.metadata.tokensPerSecond,
            model: msg.metadata.model,
            provider: msg.metadata.provider,
            // THE NOTE AND THE FLAGS (2026-09-23): this map LISTS its fields, so
            // whatever it omits is dropped — the note was being thrown away here
            // on the way back from the backend, which is why a limit note
            // survived the live turn but vanished on the next reload.
            ...carriedLimitExtras(msg.metadata as unknown as Record<string, unknown>)
          } : undefined
        })),
        createdAt: new Date(backend.created ?? Date.now()),
        updatedAt: new Date(backend.updated ?? Date.now()),
        isActive: false,
        // THE MESSAGE COUNT (2026-09-15). Carried through explicitly — this map
        // lists its fields, so anything omitted is dropped. Note the merge below
        // deliberately keeps CACHED messages over the backend's, which is exactly
        // how the old count went stale after a delete: the cached array survived
        // and `messages.length` kept reporting the pre-delete number.
        message_count: backend.message_count
      }))

      this.lastSyncTime = new Date()

      // traceService.trace('SessionLifecycleDebug', 'loadFromBackend:backendSessionsLoaded', {
        // backendSessionsCount: sessions.length,
        // backendSessionIds: sessions.map(s => s.id),
        // backendSessionTitles: sessions.map(s => s.title)
      // }, ['sync'])

      // CRITICAL: Preserve messages and title changes from cached sessions (localStorage)
      // Backend returns sessions without messages (include_messages=false)
      // Backend also doesn't have locally renamed titles (not synced to backend)
      // We need to merge cached data with backend session data
      const mergedSessions = sessions.map(backendSession => {
        // Find matching cached session
        const cachedSession = cachedSessions.find(s => s.id === backendSession.id)

        // Start with backend session as base
        const merged = { ...backendSession, messages: backendSession.messages as ConversationMessage[] }

        // Preserve cached messages if available
        if (cachedSession && cachedSession.messages && cachedSession.messages.length > 0) {
          merged.messages = cachedSession.messages as ConversationMessage[]
        }

        // Preserve cached title if it was changed locally (not "New Session")
        if (cachedSession && cachedSession.title && cachedSession.title !== 'New Session') {
          // Only use cached title if it's different from backend title
          // This means user renamed it locally
          merged.title = cachedSession.title
        }

        return merged
      })

      // Preserve temp sessions (not yet synced to backend)
      const tempSessions = cachedSessions.filter(s => String(s.id).startsWith('session-'))

      // traceService.trace('SessionLifecycleDebug', 'loadFromBackend:preservingCachedAndTemp', {
        // cachedSessionsCount: cachedSessions.length,
        // tempSessionsCount: tempSessions.length,
        // backendSessionsCount: sessions.length,
        // sessionsWithMessages: mergedSessions.filter(s => s.messages && s.messages.length > 0).length
      // }, ['sync'])

      // Write to Zustand store, preserving temp sessions and cached
      // messages. THE TEMP-COMMIT DROP (2026-08-27 — the user's
      // duplicate-sessions report: "a session on the NEW button, a
      // second on the first prompt"): the commit's createSession
      // carries the temp's TITLE into the backend create — the
      // identical title IS the committed-pair signature. A temp whose
      // title matches a merged session was committed; dropping it
      // prevents the phantom twin. Plus the stringified-id collapse
      // (the string-vs-integer id types).
      const mergedTitles = new Set(mergedSessions.map((s) => s.title))
      const uncommittedTemps = tempSessions.filter((s) => !mergedTitles.has(s.title))
      const deduped = new Map<string, ConversationSession>()
      for (const s of [...mergedSessions, ...uncommittedTemps]) {
        deduped.set(String(s.id), s)
      }
      useCognitiveHubStore.getState().setSessions([...deduped.values()])

      // traceService.trace('SessionLifecycleDebug', 'loadFromBackendComplete', {
        // backendSessionsCount: sessions.length,
        // tempSessionsPreserved: tempSessions.length,
        // finalSessionsCount: finalState.sessions.length,
        // finalSessionIds: finalState.sessions.map(s => s.id),
        // finalSessionTitles: finalState.sessions.map(s => s.title),
        // sessionsWithMessages: finalState.sessions.filter(s => s.messages && s.messages.length > 0).length
      // }, ['sync'])

      // traceService.trace('SessionsService', 'loadFromBackend:success', {
        // count: mergedSessions.length,
        // preservedTempSessions: tempSessions.length,
        // preservedCachedMessages: mergedSessions.filter(s => s.messages && s.messages.length > 0).length
      // }, ['lifecycle', 'api-call', 'sync'])

      // TODO: Re-enable when debugging is needed - clogs logs
      // frontendLoggingService.info('SessionsService', 'Sessions loaded from backend', {
      //   count: mergedSessions.length
      // })
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error)
      frontendLoggingService.error('SessionsService', 'Failed to load sessions from backend', {
        error: errorMessage
      })

      // traceService.trace('SessionsService', 'loadFromBackend:error', {
        // error: errorMessage
      // }, ['error'])

      throw error
    } finally {
      this.isLoading = false
    }
  }

  /**
   * Add session to Zustand store
   */
  addSession(session: ConversationSession): void {
    useCognitiveHubStore.getState().upsertSession(session)

    // traceService.trace('SessionsService', 'addSession', {
      // sessionId: session.id,
      // title: session.title
    // }, ['lifecycle', 'state-change'])
  }

  /**
   * Update session in Zustand store
   */
  updateSession(sessionId: string, updates: Partial<ConversationSession>): void {
    const state = useCognitiveHubStore.getState()
    const session = state.sessions.find(s => s.id === sessionId)

    if (!session) {
      // traceService.trace('SessionsService', 'updateSession:not found', {
        // sessionId
      // }, ['error'])
      frontendLoggingService.warning('SessionsService', 'Attempted to update non-existent session', {
        sessionId
      })
      return
    }

    // Use renameSessionById for atomic title updates, otherwise use upsertSession
    if ('title' in updates && Object.keys(updates).length === 1) {
      state.renameSessionById(sessionId, updates.title!)
    } else {
      useCognitiveHubStore.getState().upsertSession({ ...session, ...updates })
    }

    // traceService.trace('SessionsService', 'updateSession:success', {
      // sessionId,
      // updates: Object.keys(updates)
    // }, ['state-change'])
  }

  /**
   * Remove session from Zustand store
   */
  removeSession(sessionId: string): void {
    useCognitiveHubStore.getState().removeSession(sessionId)

    // traceService.trace('SessionsService', 'removeSession', {
      // sessionId
    // }, ['lifecycle', 'state-change'])
  }

  /**
   * Set active session in Zustand store
   */
  setActiveSession(sessionId: string): void {
    const state = useCognitiveHubStore.getState()
    const session = state.sessions.find(s => s.id === sessionId)
    if (session) {
      // Update isActive on all sessions and set the target as active
      const updatedSessions = state.sessions.map(s => ({
        ...s,
        isActive: s.id === sessionId,
      }))
      const updatedSession = updatedSessions.find(s => s.id === sessionId)!
      state.setSessions(updatedSessions)
      state.setActiveSession(updatedSession)
    }

    // traceService.trace('SessionsService', 'setActiveSession', {
      // sessionId
    // }, ['state-change'])
  }

  /**
   * Clear all sessions from Zustand store
   */
  clearAll(): void {
    useCognitiveHubStore.getState().setSessions([])

    // traceService.trace('SessionsService', 'clearAll', {}, ['state-change'])
  }

  /**
   * Start background sync with backend
   * DISABLED: 2026-03-09 - causes old test sessions to appear unexpectedly
   * Alternative: Manual refresh and operation-based updates
   */
  private startBackgroundSync(): void {
    // DISABLED: 30-second interval causes unnecessary API calls and React re-renders
    // this.syncInterval = setInterval(async () => {
    //   traceService.trace('SessionsService', 'background sync:starting', {
    //     intervalMs: 30000
    //   }, ['sync'])
    //   await this.loadFromBackend()
    //   traceService.trace('SessionsService', 'background sync:completed', {}, ['sync'])
    // }, 30000)

    // traceService.trace('SessionsService', 'background sync:DISABLED', {
      // reason: 'Prevents old test sessions from appearing unexpectedly',
      // alternative: 'Manual refresh and operation-based updates'
    // }, ['sync'])
  }

  /**
   * Stop background sync
   * Call this when unmounting to prevent memory leaks
   */
  stopBackgroundSync(): void {
    if (this.syncInterval) {
      clearInterval(this.syncInterval)
      this.syncInterval = null

      // traceService.trace('SessionsService', 'background sync:stopped', {}, ['sync'])
    }
  }

  /**
   * Cleanup - stop background sync and clear subscribers
   */
  destroy(): void {
    this.stopBackgroundSync()
    this.subscribers.clear()

    // traceService.trace('SessionsService', 'destroyed', {}, ['lifecycle'])
  }

  /**
   * Get service status
   */
  getStatus(): {
    sessionCount: number
    subscriberCount: number
    isLoading: boolean
    lastSyncTime: Date | null
  } {
    return {
      sessionCount: this.getSessions().length,
      subscriberCount: this.subscribers.size,
      isLoading: this.isLoading,
      lastSyncTime: this.lastSyncTime
    }
  }

  /**
   * Parse timestamp from backend
   */
  private parseTimestamp(timestamp: number | string): Date {
    if (typeof timestamp === 'string') {
      return new Date(timestamp)
    } else if (typeof timestamp === 'number') {
      return new Date(timestamp)
    } else {
      frontendLoggingService.warning('SessionsService', 'Unknown timestamp format', { timestamp })
      return new Date()
    }
  }
}

// Export singleton instance
export const sessionsService = new SessionsService()
