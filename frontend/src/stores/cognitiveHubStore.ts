/**
 * Cognitive Hub Store
 *
 * Central Zustand store for AI context state management.
 * Replaces local useState in useSessionManagement and useChatPersistence.
 *
 * This file now composes focused sub-store slices using the Zustand
 * slices pattern. Each slice manages a single concern:
 *
 * - [`agentStore.ts`](agentStore.ts) — Agent list, active agent, sessions, lifecycle
 * - [`streamStore.ts`](streamStore.ts) — Streaming status flags
 * - [`providerHealthStore.ts`](providerHealthStore.ts) — Provider health map
 * - [`syncQueueStore.ts`](syncQueueStore.ts) — Offline sync queue
 *
 * Features:
 * - Survives navigation (singleton, not unmounted)
 * - Configurable persistence (localStorage/sessionStorage/none)
 * - DevTools integration for debugging
 *
 * @see docs/hub/PHASED-IMPLEMENTATION-PLAN.md
 */

import { create } from 'zustand'
import { devtools, persist, createJSONStorage } from 'zustand/middleware'

import { createAgentSlice, type AgentSlice } from './agentStore'
import { createStreamSlice, type StreamSlice } from './streamStore'
import { createSyncQueueSlice, type SyncQueueSlice } from './syncQueueStore'
import type { PersistenceScope } from './types'

// ─────────────────────────────────────────────────────────────────────────────
// Combined State Interface
// ─────────────────────────────────────────────────────────────────────────────

interface CognitiveHubState
  extends AgentSlice,
    StreamSlice,
    SyncQueueSlice {
  // ─────────────────────────────────────────────────────────────
  // User Preferences (kept here — tightly coupled to persist config)
  // ─────────────────────────────────────────────────────────────

  /** Where to persist active context */
  persistenceScope: PersistenceScope

  /** Set persistence scope preference */
  setPersistenceScope: (scope: PersistenceScope) => void
}

// ─────────────────────────────────────────────────────────────────────────────
// Custom Storage (routes based on persistenceScope)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Custom storage that routes based on persistenceScope
 * This is a wrapper around localStorage/sessionStorage
 */
const createScopedStorage = () => {
  // THE PER-TAB DOCTRINE (2026-09-10, the multi-agent-tabs vision): the
  // volatile context (active agent, active session, the session cache)
  // belongs to THIS TAB, not to the browser. localStorage is shared
  // across tabs, so two tabs overwrote each other's agent and session.
  let currentScope: PersistenceScope = 'session'

  return {
    /** Set the current scope (called when state changes) */
    setScope: (scope: PersistenceScope) => {
      currentScope = scope
    },

    /** Get item from appropriate storage */
    getItem: (name: string): string | null => {
      if (currentScope === 'none') return null
      if (currentScope === 'session') {
        return typeof sessionStorage !== 'undefined' ? sessionStorage.getItem(name) : null
      }
      // Default to localStorage
      return typeof localStorage !== 'undefined' ? localStorage.getItem(name) : null
    },

    /** Set item to appropriate storage */
    setItem: (name: string, value: string): void => {
      if (currentScope === 'none') return
      if (currentScope === 'session') {
        if (typeof sessionStorage !== 'undefined') {
          sessionStorage.setItem(name, value)
        }
        return
      }
      // Default to localStorage
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem(name, value)
      }
    },

    /** Remove item from appropriate storage */
    removeItem: (name: string): void => {
      if (currentScope === 'none') return
      if (currentScope === 'session') {
        if (typeof sessionStorage !== 'undefined') {
          sessionStorage.removeItem(name)
        }
        return
      }
      // Default to localStorage
      if (typeof localStorage !== 'undefined') {
        localStorage.removeItem(name)
      }
    },
  }
}

const scopedStorage = createScopedStorage()

// ─────────────────────────────────────────────────────────────────────────────
// Combined Store
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Cognitive Hub Store
 *
 * Singleton Zustand store for AI context state.
 * Use `useCognitiveHubStore()` hook to access state.
 *
 * @example
 * ```typescript
 * const { activeAgent, activeSession, selectAgent } = useCognitiveHubStore()
 * ```
 */
export const useCognitiveHubStore = create<CognitiveHubState>()(
  devtools(
    persist(
      (set, get, store) => ({
        // Compose sub-store slices
        ...createAgentSlice(set, get, store),
        ...createStreamSlice(set, get, store),
        ...createSyncQueueSlice(set, get, store),

        // ─────────────────────────────────────────────────────────────
        // User Preferences (kept in composing layer)
        // ─────────────────────────────────────────────────────────────

        // THE PER-TAB DOCTRINE: 'session' = sessionStorage (per-tab).
        // 'local' remains available via setPersistenceScope for anyone
        // who wants the shared behaviour back.
        persistenceScope: 'session',

        setPersistenceScope: (scope) => {
          scopedStorage.setScope(scope)
          set({ persistenceScope: scope })
        },
      }),

      {
        name: 'cogitate-hub-storage',

        /**
         * Persist sessions, agents, and active context
         * Sessions include messages for offline access
         * Agents are persisted for faster restore
         * Only activeAgentId is persisted (not full object) to avoid stale data
         */
        partialize: ((state: CognitiveHubState) => ({
          agents: state.agents,
          activeAgentId: state.activeAgent?.id ?? null,
          activeSessionId: state.activeSession?.id ?? null,
          activeSession: state.activeSession,
          persistenceScope: state.persistenceScope,
          sessions: state.sessions,
        })) as unknown as (state: CognitiveHubState) => CognitiveHubState,

        /**
         * Custom storage that routes based on persistenceScope
         */
        // THE JSON-STORAGE WRAP (2026-09-09, the rehydration bug):
        // the custom scoped storage is a plain string StateStorage,
        // but zustand v5's persist passes it the serialized
        // StorageValue OBJECT — without createJSONStorage the value
        // was coerced to "[object Object]" and every reload
        // rehydrated EMPTY (no active session restore, no cached
        // sessions). createJSONStorage bridges the two shapes.
        storage: createJSONStorage(() => scopedStorage),

        /**
         * Called when state is rehydrated from storage
         */
        onRehydrateStorage: () => (state, error) => {
          if (error) {
            // Rehydration failed - will use default state
            console.error('[CognitiveHubStore] Rehydration failed:', error)
            return
          }

          if (state) {
            // Update scoped storage with persisted scope
            scopedStorage.setScope(state.persistenceScope)

            // Note: activeAgent is automatically restored by Zustand from persisted state
            // The partialize function persists activeAgentId, and Zustand reconstructs
            // activeAgent from the agents list during rehydration

            // Log what was restored
            console.log('[CognitiveHubStore] Rehydrated state:', {
              agentsCount: state.agents?.length || 0,
              hasActiveAgent: !!state.activeAgent,
              activeAgentName: state.activeAgent?.name,
              sessionsCount: state.sessions?.length || 0,
              hasActiveSession: !!state.activeSession,
              activeSessionTitle: state.activeSession?.title,
            })
          }
        },
      },
    ),

    {
      name: 'CognitiveHubStore',
      enabled: import.meta.env.DEV,
    },
  ),
)

// ─────────────────────────────────────────────────────────────────────────────
// Re-exports for backward compatibility
// ─────────────────────────────────────────────────────────────────────────────

// Re-export types used by consumers
export type { PersistenceScope, PendingMessage } from './types'

// Default export for convenience
export default useCognitiveHubStore
