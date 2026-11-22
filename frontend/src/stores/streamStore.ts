/**
 * Stream Slice for Cognitive Hub Store
 *
 * Manages streaming status flags.
 * Extracted from [`cognitiveHubStore.ts`](cognitiveHubStore.ts) during Phase C1 refactoring.
 *
 * @see [`cognitiveHubStore.ts`](cognitiveHubStore.ts) for the combined store
 */

import { type StateCreator } from 'zustand'
import type { AgentSlice } from './agentStore'
import type { SyncQueueSlice } from './syncQueueStore'

// ─────────────────────────────────────────────────────────────────────────────
// State Interface
// ─────────────────────────────────────────────────────────────────────────────

export interface StreamSlice {
  /** Whether currently streaming a response */
  isStreaming: boolean

  /** Session ID currently being streamed to */
  streamingFor: string | null

  /** Update streaming status */
  setIsStreaming: (streaming: boolean, sessionId?: string) => void
}

/**
 * Combined store type used for cross-slice access.
 */
type CombinedState = AgentSlice & StreamSlice & SyncQueueSlice

/**
 * Creates the stream slice of the Cognitive Hub store.
 */
export const createStreamSlice: StateCreator<
  CombinedState,
  [],
  [],
  StreamSlice
> = (set) => ({
  isStreaming: false,
  streamingFor: null,

  setIsStreaming: (streaming, sessionId) => {
    set({
      isStreaming: streaming,
      streamingFor: sessionId || null,
    })
  },
})
