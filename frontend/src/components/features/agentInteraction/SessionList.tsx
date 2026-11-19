import { useState } from 'react'
import type { ConversationSession } from '@/types/agentInteraction'
import SessionListItem from './SessionListItem'


interface SessionListProps {
  sessions: ConversationSession[]
  currentSession: ConversationSession | null
  onSessionSelect: (session: ConversationSession) => Promise<void>
  onSessionDelete: (sessionId: string) => void
  onSessionRename?: (sessionId: string, newTitle: string) => void
  onSessionSmartRename?: (session: ConversationSession) => void
  requireDeleteConfirm?: boolean
  isBulkDeleteMode?: boolean
  selectedSessions?: Set<string>
  onSessionToggleSelect?: (sessionId: string) => void
}

export default function SessionList({
  sessions,
  currentSession,
  onSessionSelect,
  onSessionDelete,
  onSessionRename,
  onSessionSmartRename,
  requireDeleteConfirm = true,
  isBulkDeleteMode = false,
  selectedSessions = new Set(),
  onSessionToggleSelect = () => {}
}: SessionListProps) {
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [loadingSessionId, setLoadingSessionId] = useState<string | null>(null)

  const handleRenameStart = (session: ConversationSession) => {
    // traceService.trace('RenameButton', 'handleRenameStart', {
      // sessionId: session.id,
      // currentTitle: session.title,
      // renamingIdBefore: renamingId
    // })
    setRenamingId(session.id)
    setRenameValue(session.title)
    
    // Verify state update
    setTimeout(() => {
      // traceService.trace('RenameButton', 'handleRenameStart: state updated', {
        // sessionId: session.id,
        // renamingIdAfter: session.id
      // })
    }, 0)
  }

  const handleRenameSave = (sessionId: string) => {
    // traceService.trace('RenameButton', 'handleRenameSave', {
      // sessionId,
      // renameValue,
      // renameValueTrimmed: renameValue.trim()
    // })

    if (renameValue.trim() && onSessionRename) {
      // traceService.trace('RenameButton', 'calling onSessionRename', {
        // sessionId,
        // newTitle: renameValue.trim()
      // })
      onSessionRename(sessionId, renameValue.trim())
    }
    setRenamingId(null)
    setRenameValue('')
    
    // traceService.trace('RenameButton', 'handleRenameSave: complete', {
      // sessionId,
      // renamingIdAfter: null
    // })
  }

  const handleRenameCancel = () => {
    // traceService.trace('RenameButton', 'handleRenameCancel', {
      // renamingIdBefore: renamingId
    // })
    setRenamingId(null)
    setRenameValue('')
    
    // traceService.trace('RenameButton', 'handleRenameCancel: complete', {
      // renamingIdAfter: null
    // })
  }

  return (
    <div className="divide-y divide-base-300">
      {sessions.map(session => (
        <SessionListItem
          key={session.id}
          session={session}
          isActive={currentSession?.id === session.id}
          isRenaming={renamingId === session.id}
          renameValue={renameValue}
          onSelect={async () => {
            setLoadingSessionId(session.id)
            try {
              await onSessionSelect(session)
            } finally {
              setLoadingSessionId(null)
            }
          }}
          isLoading={loadingSessionId === session.id}
          onDelete={() => onSessionDelete(session.id)}
          onRenameStart={() => handleRenameStart(session)}
          onSmartRename={() => onSessionSmartRename ? onSessionSmartRename(session) : handleRenameStart(session)}
          onRenameSave={() => handleRenameSave(session.id)}
          onRenameCancel={handleRenameCancel}
          onRenameChange={(value) => setRenameValue(value)}
          requireDeleteConfirm={requireDeleteConfirm}
          isBulkDeleteMode={isBulkDeleteMode}
          isSelected={selectedSessions.has(session.id)}
          onToggleSelect={() => onSessionToggleSelect(session.id)}
        />
      ))}
    </div>
  )
}

