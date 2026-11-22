/**
 * Shared types for Cognitive Hub sub-stores.
 *
 * Extracted from [`cognitiveHubStore.ts`](cognitiveHubStore.ts) during
 * Phase C1 refactoring. These types are used across multiple sub-stores
 * and are re-exported from [`cognitiveHubStore.ts`](cognitiveHubStore.ts) for
 * backward compatibility.
 */

import type { ConversationMessage } from '../types/agentInteraction'

/**
 * Persistence scope setting
 * Controls where active context survives
 */
export type PersistenceScope = 'local' | 'session' | 'none'

/**
 * Pending message for offline sync queue
 */
export interface PendingMessage {
  id: string
  sessionId: string
  message: ConversationMessage
  retryCount: number
  createdAt: number
  lastAttemptAt: number
}
