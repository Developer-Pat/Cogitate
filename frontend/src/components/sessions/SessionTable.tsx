import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCognitiveHubStore } from '@/stores/cognitiveHubStore';
import { AgentService } from '@/services/domain/AgentService';
import { frontendLoggingService } from '@/services/frontendLoggingService';
import type { ConversationSession } from '@/types/agentInteraction';

interface AgentInfo {
  id: string | number;
  name: string;
  profile_image_url?: string;
}

interface SessionTableProps {
  sessions: ConversationSession[];
  agents?: AgentInfo[];
  onDeleteSession: (sessionId: string) => void;
  onRenameSession: (sessionId: string, newTitle: string) => void;
  onSmartRenameSession?: (sessionId: string) => void;
  renamingId?: string | null;
  onViewDetails: (session: ConversationSession) => void;
  onOpenInChat?: (session: ConversationSession) => void;
  isLoading?: boolean;
  selectedIds?: Set<string>;
  onSelectionChange?: (ids: Set<string>) => void;
}

export const SessionTable: React.FC<SessionTableProps> = ({
  sessions,
  agents = [],
  onDeleteSession,
  onRenameSession,
  onSmartRenameSession,
  renamingId,
  onViewDetails,
  onOpenInChat,
  isLoading = false,
  selectedIds = new Set(),
  onSelectionChange,
}) => {
  const navigate = useNavigate();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');

  const handleRenameClick = (session: ConversationSession) => {
    setEditingId(session.id);
    setEditingTitle(session.title);
  };

  const handleRenameSubmit = (sessionId: string) => {
    if (editingTitle.trim()) {
      onRenameSession(sessionId, editingTitle.trim());
    }
    setEditingId(null);
    setEditingTitle('');
  };

  const handleRenameCancel = () => {
    setEditingId(null);
    setEditingTitle('');
  };

  const handleOpenInChat = async (session: ConversationSession) => {
    try {
      // If callback provided, use it
      if (onOpenInChat) {
        onOpenInChat(session);
        return;
      }

      // Load agent and set session
      const agentService = new AgentService();
      const agents = await agentService.getAgents();
      const agent = agents.find(a => String(a.id) === String(session.agentId));

      if (agent) {
        // Set the agent as selected in agent store
        await agentService.selectAgent(String(session.agentId));
      }

      // Reload session from backend to ensure we have latest messages
      try {
        const sessionSyncService = await import('@/services/sessionSyncService');
        const backendSession = await sessionSyncService.sessionSyncService.getSession(session.id);
        const sessionWithMessages = sessionSyncService.sessionSyncService.convertToFrontendSession(backendSession);
        
        // Set as active session in Cognitive Hub store
        useCognitiveHubStore.getState().setActiveSession(sessionWithMessages);
      } catch (err) {
        // Fallback: use local session if backend fails
        frontendLoggingService.warning('SessionTable', 'Failed to reload session, using local data', {
          sessionId: session.id,
          error: err
        });
        useCognitiveHubStore.getState().setActiveSession(session);
      }

      frontendLoggingService.info('SessionTable', 'Opened session in chat', {
        sessionId: session.id,
        sessionTitle: session.title,
        agentId: session.agentId
      });

      // Navigate to chat page
      navigate('/agent-interaction');
    } catch (error) {
      frontendLoggingService.error('SessionTable', 'Failed to open session in chat', {
        error,
        sessionId: session.id
      });
      alert('Failed to open session. Please try again.');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent, sessionId: string) => {
    if (e.key === 'Enter') {
      handleRenameSubmit(sessionId);
    } else if (e.key === 'Escape') {
      handleRenameCancel();
    }
  };

  const formatRelativeTime = (date: Date) => {
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  const truncateTitle = (title: string, maxLength: number = 50) => {
    if (title.length <= maxLength) return title;
    return title.substring(0, maxLength - 3) + '...';
  };

  const getAgentName = (agentId: string | number | null | undefined) => {
    // THE EXA LABEL (2026-08-22, user): Exa sessions carry agent_id
    // = null (source='exa' — the system agent is NOT a DB agent).
    // They were showing as 'Agent ' — now they say 'Exa'.
    if (agentId === null || agentId === undefined || agentId === '') {
      return 'Exa';
    }
    const agent = agents.find(a => String(a.id) === String(agentId));
    return agent ? agent.name : `Agent ${agentId}`;
  };

  // ── Selection handlers ──────────────────────────────────────────
  const allSelected = sessions.length > 0 && sessions.every((s) => selectedIds.has(s.id));

  const toggleSelect = (sessionId: string) => {
    const next = new Set(selectedIds);
    if (next.has(sessionId)) {
      next.delete(sessionId);
    } else {
      next.add(sessionId);
    }
    onSelectionChange?.(next);
  };

  const toggleSelectAll = () => {
    if (allSelected) {
      onSelectionChange?.(new Set());
    } else {
      onSelectionChange?.(new Set(sessions.map((s) => s.id)));
    }
  };

  if (isLoading) {
    return (
      <div className="card bg-base-100 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
        <div className="card-body gap-[var(--card-gap)]">
          <div className="flex items-center justify-center py-12">
            <div className="flex flex-col items-center gap-4">
              <span className="loading loading-spinner loading-lg text-primary"></span>
              <p className="text-readout">Loading sessions...</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (sessions.length === 0) {
    return (
      <div className="card bg-base-100 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
        <div className="card-body gap-[var(--card-gap)]">
          <div className="flex items-center justify-center py-12">
            <div className="flex flex-col items-center gap-4">
              <div className="text-6xl">📭</div>
              <h3 className="text-xl font-semibold">No sessions found</h3>
              <p className="text-readout text-center">
                Start a new conversation to create your first session.
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ── Bulk action bar ──────────────────────────────────────────────
  const BulkBar = selectedIds.size > 0 ? (
    <div className="flex items-center gap-3 mb-3 px-2 py-2 bg-base-200 rounded-box">
      <span className="text-sm font-medium">{selectedIds.size} selected</span>
      <button
        className="btn btn-xs btn-outline"
        onClick={() => onSelectionChange?.(new Set())}
      >
        Clear selection
      </button>
    </div>
  ) : null;

  return (
    <>
      {BulkBar}
    <div className="card bg-base-100 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
      <div className="card-body gap-[var(--card-gap)]">
        <div className="overflow-x-auto">
          <table className="table">
            <thead>
              <tr>
                <th style={{ width: '40px' }}>
                  <input
                    type="checkbox"
                    className="checkbox checkbox-sm checkbox-primary"
                    checked={allSelected && selectedIds.size > 0}
                    onChange={toggleSelectAll}
                  />
                </th>
                <th style={{ width: '40px' }}>#</th>
                <th style={{ width: '40%' }}>Title</th>
                <th>Agent</th>
                <th>Messages</th>
                <th>Created</th>
                <th>Updated</th>
                <th style={{ width: '120px' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((session, index) => (
                <tr key={session.id} className="hover">
                  <td>
                    <input
                      type="checkbox"
                      className="checkbox checkbox-sm checkbox-primary"
                      checked={selectedIds.has(session.id)}
                      onChange={() => toggleSelect(session.id)}
                    />
                  </td>
                  <td className="text-readout">{index + 1}</td>
                  <td>
                    {editingId === session.id ? (
                      <div className="flex items-center gap-2">
                        <input
                          type="text"
                          className="input input-bordered input-sm w-full"
                          value={editingTitle}
                          onChange={(e) => setEditingTitle(e.target.value)}
                          onKeyDown={(e) => handleKeyDown(e, session.id)}
                          autoFocus
                        />
                        <div className="tooltip tooltip-top" data-tip="Save name">
                        <button
                          className="btn btn-ghost btn-xs"
                          onClick={() => handleRenameSubmit(session.id)}
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                          </svg>
                        </button>
                        </div>
                        <div className="tooltip tooltip-top" data-tip="Cancel rename">
                        <button
                          className="btn btn-ghost btn-xs"
                          onClick={handleRenameCancel}
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2">
                        <div className="tooltip tooltip-top" data-tip={session.title}>
                          <span
                            className="cursor-pointer hover:text-primary transition-colors"
                            onClick={() => onViewDetails(session)}
                          >
                            {truncateTitle(session.title)}
                          </span>
                        </div>
                        {session.isActive && (
                          <span className="badge badge-success badge-outline badge-xs">Active</span>
                        )}
                      </div>
                    )}
                  </td>
                  <td>
                    <div className="tooltip tooltip-top" data-tip={`Agent ID: ${session.agentId}`}>
                      <span className="badge badge-ghost badge-sm">
                        {getAgentName(session.agentId)}
                      </span>
                    </div>
                  </td>
                  <td>
                    <span className="badge badge-ghost badge-sm">
                      {session.messages?.length || 0}
                    </span>
                  </td>
                  <td className="text-readout">
                    {formatRelativeTime(new Date(session.createdAt))}
                  </td>
                  <td className="text-readout">
                    {formatRelativeTime(new Date(session.updatedAt))}
                  </td>
                  <td>
                    <div className="flex items-center gap-1">
                      <div className="tooltip tooltip-top" data-tip="Open in chat">
                      <button
                        className="btn btn-ghost btn-xs"
                        onClick={() => handleOpenInChat(session)}
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                        </svg>
                      </button>
                      </div>
                      <div className="tooltip tooltip-top" data-tip="View details">
                      <button
                        className="btn btn-ghost btn-xs"
                        onClick={() => onViewDetails(session)}
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                        </svg>
                      </button>
                      </div>
                      {onSmartRenameSession && (
                        <div className="tooltip tooltip-top" data-tip="Rename from the conversation">
                        <button
                          className="btn btn-ghost btn-xs text-primary"
                          disabled={renamingId === session.id}
                          onClick={(e) => {
                            // Blur so Space/Enter cannot re-activate the
                            // focused button on a stray keystroke.
                            e.currentTarget.blur();
                            onSmartRenameSession(session.id);
                          }}
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                          </svg>
                        </button>
                        </div>
                      )}
                      <div className="tooltip tooltip-top" data-tip="Edit name">
                      <button
                        className="btn btn-ghost btn-xs"
                        onClick={() => handleRenameClick(session)}
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                        </svg>
                      </button>
                      </div>
                      <div className="tooltip tooltip-top" data-tip="Delete">
                      <button
                        className="btn btn-ghost btn-xs text-error hover:bg-error hover:text-error-content"
                        onClick={() => onDeleteSession(session.id)}
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                      </div>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </>
  );
};
