/**
 * Provider Health Slice for Cognitive Hub Store
 *
 * Manages provider health status and active provider tracking.
 * Extracted from [`cognitiveHubStore.ts`](cognitiveHubStore.ts) during Phase C1 refactoring.
 *
 * @see [`cognitiveHubStore.ts`](cognitiveHubStore.ts) for the combined store
 */

import { type StateCreator } from 'zustand'
import type { AgentSlice } from './agentStore'
import type { StreamSlice } from './streamStore'
import type { SyncQueueSlice } from './syncQueueStore'
import type { ProviderHealthStatus } from './types'

// ─────────────────────────────────────────────────────────────────────────────
// State Interface
// ─────────────────────────────────────────────────────────────────────────────

export interface ProviderHealthSlice {
  /** Health status per provider */
  providerHealth: Record<string, ProviderHealthStatus>

  /** Currently active provider (from activeAgent) */
  activeProvider: string | null

  /** Update provider health map */
  setProviderHealth: (health: Record<string, ProviderHealthStatus>) => void
}

/**
 * Combined store type used for cross-slice access.
 */
type CombinedState = AgentSlice & StreamSlice & ProviderHealthSlice & SyncQueueSlice

/**
 * Creates the provider health slice of the Cognitive Hub store.
 */
export const createProviderHealthSlice: StateCreator<
  CombinedState,
  [],
  [],
  ProviderHealthSlice
> = (set) => ({
  providerHealth: {},
  activeProvider: null,

  setProviderHealth: (health) => {
    set({ providerHealth: health })
  },
})
