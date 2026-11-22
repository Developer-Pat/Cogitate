/**
 * Sync Queue Slice for Cognitive Hub Store
 *
 * Manages offline sync queue — messages pending background sync to backend.
 * Extracted from [`cognitiveHubStore.ts`](cognitiveHubStore.ts) during Phase C1 refactoring.
 *
 * @see [`cognitiveHubStore.ts`](cognitiveHubStore.ts) for the combined store
 */

import { type StateCreator } from 'zustand'
import type { AgentSlice } from './agentStore'
import type { StreamSlice } from './streamStore'
import type { PendingMessage } from './types'
import type { ConversationMessage } from '../types/agentInteraction'

// ─────────────────────────────────────────────────────────────────────────────
// State Interface
// ─────────────────────────────────────────────────────────────────────────────

export interface SyncQueueSlice {
  /** Messages pending sync to backend */
  pendingMessages: PendingMessage[]

  /** Number of messages pending sync */
  pendingSyncCount: number

  /** Add message to pending sync queue */
  addToPendingQueue: (sessionId: string, message: ConversationMessage) => void

  /** Remove message from pending queue (on successful sync) */
  removeFromPendingQueue: (messageId: string) => void

  /** Increment retry count for a message */
  incrementRetryCount: (messageId: string) => void

  /** Clear all pending messages */
  clearPendingQueue: () => void
}

/**
 * Combined store type used for cross-slice access.
 */
type CombinedState = AgentSlice & StreamSlice & SyncQueueSlice

/**
 * Creates the sync queue slice of the Cognitive Hub store.
 */
export const createSyncQueueSlice: StateCreator<
  CombinedState,
  [],
  [],
  SyncQueueSlice
> = (set) => ({
  pendingMessages: [],
  pendingSyncCount: 0,

  addToPendingQueue: (sessionId, message) => {
    set((state) => {
      const pendingMessage: PendingMessage = {
        id: message.id,
        sessionId,
        message,
        retryCount: 0,
        createdAt: Date.now(),
        lastAttemptAt: Date.now(),
      }
      return {
        pendingMessages: [...state.pendingMessages, pendingMessage],
        pendingSyncCount: state.pendingMessages.length + 1,
      }
    })
  },

  removeFromPendingQueue: (messageId) => {
    set((state) => {
      const filtered = state.pendingMessages.filter(pm => pm.message.id !== messageId)
      return {
        pendingMessages: filtered,
        pendingSyncCount: filtered.length,
      }
    })
  },

  incrementRetryCount: (messageId) => {
    set((state) => ({
      pendingMessages: state.pendingMessages.map(pm =>
        pm.message.id === messageId
          ? { ...pm, retryCount: pm.retryCount + 1, lastAttemptAt: Date.now() }
          : pm,
      ),
    }))
  },

  clearPendingQueue: () => {
    set({ pendingMessages: [], pendingSyncCount: 0 })
  },
})
