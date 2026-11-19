/**
 * Offline Sync Queue Service
 * 
 * Manages retry logic for messages that failed to sync to backend.
 * Uses exponential backoff: 1s, 2s, 4s, 8s, 16s (max 5 attempts)
 */

import { useCognitiveHubStore } from '../stores/cognitiveHubStore'
import { sessionSyncService } from '../services/sessionSyncService'
import { frontendLoggingService } from '../services/frontendLoggingService'

const MAX_RETRIES = 5
const BASE_DELAY_MS = 1000

/**
 * Calculate delay with exponential backoff
 * @param retryCount - Number of retries already attempted
 * @returns Delay in milliseconds
 */
function calculateBackoff(retryCount: number): number {
  // Exponential backoff: 1s, 2s, 4s, 8s, 16s
  const delay = Math.min(BASE_DELAY_MS * Math.pow(2, retryCount), 16000)
  // Add jitter (±25%) to prevent thundering herd
  const jitter = delay * 0.25 * (Math.random() * 2 - 1)
  return delay + jitter
}

/**
 * Process pending queue and retry failed messages
 */
export async function processPendingQueue(): Promise<void> {
  const state = useCognitiveHubStore.getState()
  const now = Date.now()
  
  if (state.pendingMessages.length === 0) {
    return
  }

  frontendLoggingService.debug('OfflineSyncQueue', `Processing ${state.pendingMessages.length} pending messages`)

  for (const pending of state.pendingMessages) {
    // Skip if max retries exceeded
    if (pending.retryCount >= MAX_RETRIES) {
      frontendLoggingService.error('OfflineSyncQueue', 'Max retries exceeded, dropping message', {
        messageId: pending.message.id,
        retryCount: pending.retryCount
      })
      useCognitiveHubStore.getState().removeFromPendingQueue(pending.message.id)
      continue
    }

    // Skip if not yet time for next retry
    const nextRetryTime = pending.lastAttemptAt + calculateBackoff(pending.retryCount)
    if (now < nextRetryTime) {
      continue
    }

    // Attempt to sync
    try {
      frontendLoggingService.debug('OfflineSyncQueue', 'Retrying message sync', {
        messageId: pending.message.id,
        retryCount: pending.retryCount + 1
      })

      await sessionSyncService.syncMessage(pending.sessionId, pending.message)
      
      // Success - remove from queue
      useCognitiveHubStore.getState().removeFromPendingQueue(pending.message.id)
      frontendLoggingService.info('OfflineSyncQueue', 'Message synced successfully after retry', {
        messageId: pending.message.id
      })
    } catch (error) {
      // Failed - increment retry count
      useCognitiveHubStore.getState().incrementRetryCount(pending.message.id)
      frontendLoggingService.warning('OfflineSyncQueue', 'Message sync failed, will retry', {
        messageId: pending.message.id,
        retryCount: pending.retryCount + 1,
        error: error instanceof Error ? error.message : 'Unknown error'
      })
    }
  }
}

/**
 * Start the background retry processor
 * Runs every 2 seconds to check for messages ready to retry
 */
let retryIntervalId: ReturnType<typeof setTimeout> | null = null

export function startRetryProcessor(): void {
  if (retryIntervalId) {
    return // Already running
  }

  frontendLoggingService.info('OfflineSyncQueue', 'Starting retry processor')
  
  retryIntervalId = setInterval(() => {
    processPendingQueue()
  }, 2000) // Check every 2 seconds
}

/**
 * Stop the background retry processor
 */
export function stopRetryProcessor(): void {
  if (retryIntervalId) {
    clearInterval(retryIntervalId)
    retryIntervalId = null
    frontendLoggingService.info('OfflineSyncQueue', 'Stopped retry processor')
  }
}
