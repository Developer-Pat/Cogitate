/**
 * Agent Slice for Cognitive Hub Store
 *
 * Manages agent list, active agent, sessions, and session lifecycle.
 * Extracted from [`cognitiveHubStore.ts`](cognitiveHubStore.ts) during Phase C1 refactoring.
 *
 * @see [`cognitiveHubStore.ts`](cognitiveHubStore.ts) for the combined store
 */

import { type StateCreator } from 'zustand'
import type { Agent, ConversationSession, ConversationMessage } from '../types/agentInteraction'
import { frontendLoggingService } from '../services/frontendLoggingService'
import type { ProviderHealthSlice } from './providerHealthStore'
import type { StreamSlice } from './streamStore'
import type { SyncQueueSlice } from './syncQueueStore'

// ─────────────────────────────────────────────────────────────────────────────
// State Interface
// ─────────────────────────────────────────────────────────────────────────────

export interface AgentSlice {
  // ─────────────────────────────────────────────────────────────
  // Agent Management
  // ─────────────────────────────────────────────────────────────

  /** List of all available agents */
  agents: Agent[]

  /** Whether agents are currently loading */
  isLoadingAgents: boolean

  /** Error loading agents, if any */
  agentError: string | null

  /** Currently selected agent */
  activeAgent: Agent | null

  /** Current active chat session */
  activeSession: ConversationSession | null

  /** All sessions for the active agent */
  sessions: ConversationSession[]

  /** Lazy session flag — true when session created but not yet committed to backend */
  pendingSession: boolean

  // ─────────────────────────────────────────────────────────────
  // Agent Management Actions
  // ─────────────────────────────────────────────────────────────

  /** Set list of all agents */
  setAgents: (agents: Agent[]) => void

  /** Set agents loading state */
  setLoadingAgents: (loading: boolean) => void

  /** Set agent error */
  setAgentError: (error: string | null) => void

  /** Set active agent */
  setActiveAgent: (agent: Agent | null) => void

  /** Set active session */
  setActiveSession: (session: ConversationSession | null) => void

  /** Set all sessions (replaces entire list) */
  setSessions: (sessions: ConversationSession[]) => void

  /** Add or update a single session (prepends to list) */
  upsertSession: (session: ConversationSession) => void

  /** Remove a session by ID */
  removeSession: (sessionId: string) => void

  /** Replace a session by old ID with new session */
  replaceSessionById: (oldId: string, newSession: ConversationSession) => void

  /** Rename a session by ID — atomic update using fresh store state, safe from stale closures */
  renameSessionById: (sessionId: string, title: string) => void

  /** Add message to a session */
  addSessionMessage: (sessionId: string, message: ConversationMessage) => void

  /** Update message content in a session */
  updateSessionMessage: (sessionId: string, messageId: string, content?: string, metadata?: unknown) => void

  /** Set pending session flag */
  setPendingSession: (pending: boolean) => void

  /** Hydrate store from persisted IDs (called on boot) */
  hydrateFromPersistedIds: () => Promise<void>

  // ─────────────────────────────────────────────────────────────
  // Session Lifecycle Actions
  // ─────────────────────────────────────────────────────────────

  /** Update session status */
  updateSessionStatus: (sessionId: string, status: 'active' | 'inactive' | 'unloaded') => void

  /** Unload messages from inactive sessions to save memory */
  unloadInactiveSessions: () => void

  /** Close active session (mark as inactive) */
  closeActiveSession: () => void
}

/**
 * Combined store type used for cross-slice access.
 * All slice types combined so that `get()` and `set()` can access the full store.
 */
type CombinedState = AgentSlice & StreamSlice & ProviderHealthSlice & SyncQueueSlice

/**
 * Creates the agent slice of the Cognitive Hub store.
 *
 * @param set - Zustand `set` function (scoped to combined state)
 * @param get - Zustand `get` function (scoped to combined state)
 */
export const createAgentSlice: StateCreator<
  CombinedState,
  [],
  [],
  AgentSlice
> = (set) => ({
  // ═════════════════════════════════════════════════════════════
  // Initial State
  // ═════════════════════════════════════════════════════════════

  agents: [],
  isLoadingAgents: false,
  agentError: null,
  activeAgent: null,
  activeSession: null,
  sessions: [],
  pendingSession: false,

  // ═════════════════════════════════════════════════════════════
  // Actions
  // ═════════════════════════════════════════════════════════════

  setActiveAgent: (agent) => {
    // [DIAGNOSTIC] Trace when agent is set in store
    if (agent) {
      // traceService.trace('CognitiveHubStore', 'setActiveAgent', {
      // agentId: agent.id,
      // agentName: agent.name,
      // agentModel: agent.model,
      // agentProvider: agent.provider,
      // loadedFrom: agent.loadedFrom,
      // lastRefreshed: agent.lastRefreshed,
      // isStale: agent.isStale
      // }, ['data', 'state-change'])
    }

    set({
      activeAgent: agent,
      activeProvider: agent?.provider || null,
    })
  },

  setAgents: (agents) => {
    set({ agents })
  },

  setLoadingAgents: (loading) => {
    set({ isLoadingAgents: loading })
  },

  setAgentError: (error) => {
    set({ agentError: error })
  },

  setActiveSession: (session) => {
    set({ activeSession: session })
  },

  setSessions: (sessions) => {
    // traceService.trace('SessionLifecycleDebug', 'setSessionsCalled', {
    // count: sessions.length,
    // sessionIds: sessions.map(s => s.id)
    // }, ['state-change', 'sync'])

    set({ sessions })

    // traceService.trace('SessionLifecycleDebug', 'setSessionsComplete', {
    // count: sessions.length,
    // sessionIds: sessions.map(s => s.id)
    // }, ['state-change', 'sync'])
  },

  upsertSession: (session) => {
    set((state) => ({
      sessions: [session, ...state.sessions.filter(s => s.id !== session.id)],
    }))
  },

  removeSession: (sessionId) => {
    // traceService.trace('SessionLifecycleDebug', 'removeSessionCalled', {
    // sessionId
    // }, ['state-change', 'lifecycle'])

    set((state) => ({
      sessions: state.sessions.filter(s => s.id !== sessionId),
    }))

    // traceService.trace('SessionLifecycleDebug', 'removeSessionComplete', {
    // sessionId,
    // sessionsAfter: get().sessions.length
    // }, ['state-change', 'lifecycle'])
  },

  replaceSessionById: (oldId, newSession) => {
    // traceService.trace('SessionLifecycleDebug', 'replaceSessionByIdEntry', {
    // oldId,
    // newId: newSession.id,
    // newTitle: newSession.title,
    // messagesCount: newSession.messages?.length,
    // sessionsBefore: state.sessions.length,
    // sessionIdsBefore: state.sessions.map(s => s.id)
    // }, ['state-change'])

    set((state) => {
      // Find the old session (check both sessions list and activeSession)
      const oldSession =
        state.sessions.find(s => s.id === oldId) ??
        (state.activeSession?.id === oldId ? state.activeSession : null)
      const idx = state.sessions.findIndex(s => s.id === oldId)

      // traceService.trace('SessionLifecycleDebug', 'replaceSessionByIdFindResult', {
      // oldId,
      // oldSessionFound: !!oldSession,
      // oldSessionIndex: idx,
      // searchedInSessions: !!state.sessions.find(s => s.id === oldId),
      // searchedInActiveSession: state.activeSession?.id === oldId
      // }, ['state-change'])

      // Merge messages from old session if they exist
      // This preserves messages added during the pending session phase
      const sessionWithMessages = {
        ...newSession,
        messages: newSession.messages && newSession.messages.length > 0
          ? newSession.messages
          : oldSession?.messages || [],
      }

      const updated = [...state.sessions]
      if (idx >= 0) {
        // Temp session found in list - replace it
        updated[idx] = sessionWithMessages
        // traceService.trace('SessionLifecycleDebug', 'replaceSessionById:replacedInList', {
        // oldId,
        // newId: newSession.id,
        // index: idx
        // }, ['state-change'])
      } else if (state.activeSession?.id === oldId) {
        // Temp session only in activeSession - prepend to list
        updated.unshift(sessionWithMessages)
        // traceService.trace('SessionLifecycleDebug', 'replaceSessionById:addedFromActiveSession', {
        // oldId,
        // newId: newSession.id,
        // reason: 'temp session was only in activeSession, not in sessions list'
        // }, ['state-change'])
      } else {
        // Session not found anywhere - just add it (shouldn't happen)
        updated.unshift(sessionWithMessages)
        // traceService.trace('SessionLifecycleDebug', 'replaceSessionById:notFound', {
        // oldId,
        // newId: newSession.id,
        // reason: 'session not found in sessions list or activeSession'
        // }, ['error', 'state-change'])
      }

      return { sessions: updated, activeSession: sessionWithMessages }
    })

    // traceService.trace('SessionLifecycleDebug', 'replaceSessionByIdComplete', {
    // oldId,
    // newId: newSession.id,
    // sessionsAfter: finalState.sessions.length,
    // sessionIdsAfter: finalState.sessions.map(s => s.id),
    // activeSessionId: finalState.activeSession?.id
    // }, ['state-change'])
  },

  renameSessionById: (sessionId, title) => {
    // traceService.trace('SessionRenameDebug', 'renameSessionById called', {
    // sessionId,
    // title,
    // sessionsCount: stateBefore.sessions.length,
    // sessionIds: stateBefore.sessions.map(s => s.id),
    // activeSessionId: stateBefore.activeSession?.id
    // }, ['lifecycle'])

    set((state) => {
      const session = state.sessions.find(s => s.id === sessionId)

      // traceService.trace('SessionRenameDebug', 'renameSessionById: finding session', {
      // sessionId,
      // sessionFound: !!session,
      // sessionIndex: state.sessions.findIndex(s => s.id === sessionId),
      // currentTitle: session?.title
      // }, ['lifecycle'])

      if (!session) {
        // traceService.trace('SessionRenameDebug', 'renameSessionById: session not found', {
        // sessionId,
        // sessionsCount: state.sessions.length,
        // sessionIds: state.sessions.map(s => s.id)
        // }, ['error'])
        return state
      }

      // Create ONE updated session object. The messages array is a SHALLOW
      // copy — a new array whose elements are the SAME message objects. (This
      // comment previously said "deep copied messages", which was never true.)
      // That element identity is load-bearing: the message list memoizes on it
      // (the streaming-perf arc), so it must not be rebuilt here.
      const updatedSession = {
        ...session,
        title,
        updatedAt: new Date(),
        messages: [...(session.messages || [])],
      }

      // Update sessions list
      const updatedSessions = state.sessions.map(s =>
        s.id === sessionId ? updatedSession : s,
      )

      // Use the SAME object reference for activeSession to avoid sync issues
      const updatedActiveSession = state.activeSession?.id === sessionId
        ? updatedSession  // Use same reference, not a copy
        : state.activeSession

      // traceService.trace('SessionRenameDebug', 'renameSessionById: update complete', {
      // sessionId,
      // title,
      // sessionsUpdated: updatedSessions.length,
      // activeSessionUpdated: !!updatedActiveSession,
      // sessionIdsAfter: updatedSessions.map(s => s.id)
      // }, ['lifecycle'])

      return { sessions: updatedSessions, activeSession: updatedActiveSession }
    })

    // Verify the rename worked
    // traceService.trace('SessionRenameDebug', 'renameSessionById: verification', {
    // sessionId,
    // title,
    // sessionInList: !!renamedSession,
    // actualTitle: renamedSession?.title,
    // titleMatches: renamedSession?.title === title,
    // sessionsCount: stateAfter.sessions.length,
    // sessionIds: stateAfter.sessions.map(s => s.id)
    // }, ['lifecycle', 'validation'])
  },

  addSessionMessage: (sessionId, message) => {
    set((state) => {
      // Find the session to update - prioritize sessions list
      let session = state.sessions.find(s => s.id === sessionId)
      const sessionFoundInList = !!session

      // If session not found in list but is active, use activeSession
      if (!session && state.activeSession?.id === sessionId) {
        session = state.activeSession
      }

      if (!session) {
        // traceService.trace('cognitiveHubStore', 'addSessionMessage: session not found', {
        // sessionId,
        // activeSessionId: state.activeSession?.id,
        // sessionsCount: state.sessions.length
        // })
        return state
      }

      // Check for duplicate message (same ID) to prevent duplicates
      const existingMessageIndex = (session.messages || []).findIndex(m => m.id === message.id)
      if (existingMessageIndex >= 0) {
        frontendLoggingService.warning('cognitiveHubStore', 'addSessionMessage: duplicate message detected, skipping', {
          sessionId,
          messageId: message.id,
          existingMessageIndex,
        })
        return state
      }

      // Create ONE updated session object. The array is rebuilt (a new
      // reference) but the EXISTING messages keep their object identity — only
      // the appended message is new. (This comment previously said "deep copied
      // messages", which was never true.) That identity is load-bearing: the
      // message list memoizes on it (the streaming-perf arc), so the existing
      // elements must not be rebuilt here.
      const updatedSession = {
        ...session,
        messages: [...(session.messages || []), message],
        updatedAt: new Date(),
      }

      // Update sessions list
      let updatedSessions = state.sessions
      if (sessionFoundInList) {
        updatedSessions = state.sessions.map(s => s.id === sessionId ? updatedSession : s)
      } else {
        // Session was only in activeSession, prepend to list
        updatedSessions = [updatedSession, ...state.sessions]
      }

      // Use the SAME object reference for activeSession to avoid sync issues
      const updatedActiveSession = state.activeSession?.id === sessionId
        ? updatedSession
        : state.activeSession

      // traceService.trace('cognitiveHubStore', 'addSessionMessage: message added', {
      // sessionId,
      // messageCount: updatedSession.messages.length,
      // sessionsUpdated: updatedSessions.length,
      // sessionFoundInList
      // })

      return {
        sessions: updatedSessions,
        activeSession: updatedActiveSession,
      }
    })
  },

  updateSessionMessage: (sessionId, messageId, content, metadata?) => {
    set((state) => {
      // Find session in sessions list
      const session = state.sessions.find(s => s.id === sessionId)

      if (!session) {
        // traceService.trace('cognitiveHubStore', 'updateSessionMessage: session not found', { sessionId })
        return state
      }

      // THE TARGETED REPLACE (verified 2026-09-16; this comment previously
      // claimed "deep copied messages", which was never true). Only the
      // message whose id matches becomes a NEW object; every other message
      // keeps its existing reference. That identity is load-bearing: the
      // message list memoizes on it (the streaming-perf arc), so an
      // untargeted rebuild here would silently re-render the whole history
      // on every stream update.
      const updatedSession = {
        ...session,
        messages: (session.messages || []).map(msg => {
          if (msg.id === messageId) {
            // THE METADATA-ONLY UPDATE (2026-08-25, the Exa flicker):
            // an undefined content preserves the existing text — the
            // tool_call chip update must NOT blank the bubble.
            return { ...msg, ...(content !== undefined ? { content } : {}), ...(metadata ? { metadata } : {}) }
          }
          return msg
        }),
        updatedAt: new Date(),
      }

      // Update sessions list
      const updatedSessions = state.sessions.map(s =>
        s.id === sessionId ? updatedSession : s,
      )

      // ALWAYS update activeSession if IDs match - use the same updated object
      const updatedActiveSession = state.activeSession?.id === sessionId
        ? updatedSession  // Use same reference to ensure sync
        : state.activeSession

      return {
        sessions: updatedSessions,
        activeSession: updatedActiveSession,
      }
    })
  },

  setPendingSession: (pending) => {
    set({ pendingSession: pending })
  },

  hydrateFromPersistedIds: async () => {
    // This will be implemented in Phase 3 with CognitiveHubProvider
    // For now, it's a no-op placeholder
  },

  // ─────────────────────────────────────────────────────────────
  // Session Lifecycle Actions
  // ─────────────────────────────────────────────────────────────

  updateSessionStatus: (sessionId, status) => {
    set((state) => ({
      sessions: state.sessions.map(s =>
        s.id === sessionId ? { ...s, status } : s,
      ),
    }))
  },

  unloadInactiveSessions: () => {
    set((state) => {
      const { sessions, activeSession } = state

      return {
        sessions: sessions.map(session => {
          // Keep active session in memory
          if (session.id === activeSession?.id) return session

          // Unload messages from inactive sessions (keep title)
          if (session.messages && session.messages.length > 0) {
            return {
              ...session,
              messages: [],
              status: 'unloaded' as const,
            }
          }
          return session
        }),
      }
    })
  },

  closeActiveSession: () => {
    set((state) => {
      const { activeSession } = state
      if (!activeSession) return state

      // Mark as inactive (messages still in memory)
      return {
        sessions: state.sessions.map(s =>
          s.id === activeSession.id ? { ...s, status: 'inactive' as const, isActive: false } : s,
        ),
        activeSession: {
          ...activeSession,
          status: 'inactive' as const,
          isActive: false,
        },
      }
    })
  },
})
