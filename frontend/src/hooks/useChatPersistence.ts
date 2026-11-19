/**
 * Hook for managing chat state persistence to sessionStorage
 * Handles save/restore of selected agent and current session
 */

import { useEffect, useState } from 'react'
import { restoreChatState, saveChatState } from '../utils/chatStateStorage'

interface UseChatPersistenceOptions {
  selectedAgentId: string | null
  currentSessionId: string | null
}

interface UseChatPersistenceReturn {
  isRestored: boolean
  restoredState: {
    selectedAgentId: string | null
    currentSessionId: string | null
  }
  saveState: () => void
  clearState: () => void
}

export function useChatPersistence({
  selectedAgentId,
  currentSessionId
}: UseChatPersistenceOptions): UseChatPersistenceReturn {
  // Read restored state once at mount
  const [restoredState] = useState(() => restoreChatState())
  const [isRestored, setIsRestored] = useState(false)

  // Mark as restored after initial mount
  useEffect(() => {
    setIsRestored(true)
  }, [])

  // Save state to sessionStorage when it changes (only if IDs are non-null)
  useEffect(() => {
    if (selectedAgentId !== null || currentSessionId !== null) {
      saveChatState(selectedAgentId, currentSessionId)
    }
  }, [selectedAgentId, currentSessionId])

  const saveState = () => {
    saveChatState(selectedAgentId, currentSessionId)
  }

  const clearState = () => {
    // Import clearChatState dynamically to avoid circular dependency
    import('../utils/chatStateStorage').then(({ clearChatState }) => {
      clearChatState()
    })
  }

  return {
    isRestored,
    restoredState: {
      selectedAgentId: restoredState?.selectedAgentId ?? null,
      currentSessionId: restoredState?.currentSessionId ?? null
    },
    saveState,
    clearState
  }
}

export default useChatPersistence
