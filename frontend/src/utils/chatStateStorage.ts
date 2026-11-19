/**
 * Utility functions for chat state persistence to sessionStorage
 */

import { frontendLoggingService } from '../services/frontendLoggingService'

export const PERSISTENCE_KEY = 'chat_state_v1'

export interface ChatStateData {
  selectedAgentId: string | null
  currentSessionId: string | null
  timestamp: number
}

/**
 * Restore chat state from sessionStorage
 */
export function restoreChatState(): Partial<ChatStateData> {
  try {
    const saved = sessionStorage.getItem(PERSISTENCE_KEY)
    if (saved) {
      const { selectedAgentId, currentSessionId } = JSON.parse(saved)
      frontendLoggingService.debug('chatStateStorage', 'Restored chat state from sessionStorage', { selectedAgentId, currentSessionId })
      return { selectedAgentId, currentSessionId }
    }
  } catch (err) {
    frontendLoggingService.warning('chatStateStorage', 'Failed to restore chat state', err as unknown as Record<string, unknown>)
  }
  return {}
}

/**
 * Save chat state to sessionStorage
 */
export function saveChatState(selectedAgentId: string | null, currentSessionId: string | null): void {
  try {
    const state: ChatStateData = {
      selectedAgentId,
      currentSessionId,
      timestamp: Date.now()
    }
    sessionStorage.setItem(PERSISTENCE_KEY, JSON.stringify(state))
  } catch (err) {
    frontendLoggingService.warning('chatStateStorage', 'Failed to save chat state', err as unknown as Record<string, unknown>)
  }
}

/**
 * Clear chat state from sessionStorage
 */
export function clearChatState(): void {
  try {
    sessionStorage.removeItem(PERSISTENCE_KEY)
  } catch (err) {
    frontendLoggingService.warning('chatStateStorage', 'Failed to clear chat state', err as unknown as Record<string, unknown>)
  }
}
