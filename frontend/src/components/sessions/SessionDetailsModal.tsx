import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useCognitiveHubStore } from '@/stores/cognitiveHubStore';
import { AgentService } from '@/services/domain/AgentService';
import { frontendLoggingService } from '@/services/frontendLoggingService';
import type { ConversationSession, ConversationMessage } from '@/types/agentInteraction';

interface AgentInfo {
  id: string | number;
  name: string;
  profile_image_url?: string;
}

interface SessionDetailsModalProps {
  session: ConversationSession | null;
  agents?: AgentInfo[];
  isOpen: boolean;
  onClose: () => void;
}

export const SessionDetailsModal: React.FC<SessionDetailsModalProps> = ({
  session,
  agents = [],
  isOpen,
  onClose
}) => {
  const navigate = useNavigate();

  if (!isOpen || !session) return null;

  const getAgentName = (agentId: string | number) => {
    const agent = agents.find(a => String(a.id) === String(agentId));
    return agent ? agent.name : `Agent ${agentId}`;
  };

  const getAgent = (agentId: string | number) => {
    return agents.find(a => String(a.id) === String(agentId));
  };

  const getUniqueModels = () => {
    const models = new Set<string>();
    (session.messages ?? []).forEach(msg => {
      if (msg.metadata?.model) {
        models.add(msg.metadata.model);
      }
    });
    return Array.from(models);
  };

  const handleOpenInChat = async () => {
    try {
      const agentService = new AgentService();
      const agentsList = await agentService.getAgents();
      const agent = agentsList.find(a => String(a.id) === String(session.agentId));

      if (agent) {
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
        frontendLoggingService.warning('SessionDetailsModal', 'Failed to reload session, using local data', {
          sessionId: session.id,
          error: err
        });
        useCognitiveHubStore.getState().setActiveSession(session);
      }

      frontendLoggingService.info('SessionDetailsModal', 'Opened session in chat', {
        sessionId: session.id,
        sessionTitle: session.title
      });

      onClose();
      navigate('/agent-interaction');
    } catch (error) {
      frontendLoggingService.error('SessionDetailsModal', 'Failed to open session in chat', {
        error,
        sessionId: session.id
      });
      alert('Failed to open session. Please try again.');
    }
  };

  const formatDateTime = (date: Date) => {
    return date.toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
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

  const getTotalTokens = () => {
    return (session.messages ?? []).reduce((sum, msg) => sum + (msg.metadata?.tokenCount || 0), 0);
  };

  const getAverageResponseTime = () => {
    const times = (session.messages ?? [])
      .filter(m => m.metadata?.totalTimeMs)
      .map(m => m.metadata!.totalTimeMs!);
    
    if (times.length === 0) return 0;
    return Math.round(times.reduce((a, b) => a + b, 0) / times.length);
  };

  const getMessagePreview = (message: ConversationMessage) => {
    const preview = message.content.substring(0, 150);
    return preview + (message.content.length > 150 ? '...' : '');
  };

  const getRoleBadgeClass = (role: string) => {
    switch (role) {
      case 'user': return 'badge-primary badge-outline';
      case 'assistant': return 'badge-secondary badge-outline';
      case 'system': return 'badge-ghost';
      default: return 'badge-muted badge-outline';
    }
  };

  return (
    <div className="modal modal-open" onClick={onClose}>
      <div className="modal-box max-w-4xl" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <h3 className="text-2xl font-bold mb-2">{session.title}</h3>
            <div className="flex flex-wrap items-center gap-3">
              {/* Agent Avatar and Name */}
              <div className="flex items-center gap-2 bg-base-200 px-3 py-1.5 rounded-lg">
                {getAgent(session.agentId)?.profile_image_url ? (
                  <img
                    src={getAgent(session.agentId)?.profile_image_url}
                    alt={getAgentName(session.agentId)}
                    className="w-6 h-6 rounded-full object-cover"
                  />
                ) : (
                  <div className="w-6 h-6 rounded-full bg-primary flex items-center justify-center text-primary-content text-xs font-bold">
                    {getAgentName(session.agentId).charAt(0)}
                  </div>
                )}
                <span className="font-medium">{getAgentName(session.agentId)}</span>
              </div>
              {session.isActive && <span className="badge badge-success badge-outline">Active Session</span>}
              {getUniqueModels().length > 0 && (
                <span className="tooltip tooltip-top" data-tip="Models used">
                  <span className="badge badge-info badge-outline">
                    {getUniqueModels().join(', ')}
                  </span>
                </span>
              )}
            </div>
          </div>
          <button
            className="btn btn-ghost btn-sm"
            onClick={onClose}
            aria-label="Close"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Metadata Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="stat bg-base-200 rounded-lg p-4">
            <div className="stat-title text-xs">Messages</div>
            <div className="stat-value text-lg">{(session.messages ?? []).length}</div>
          </div>
          <div className="stat bg-base-200 rounded-lg p-4">
            <div className="stat-title text-xs">Total Tokens</div>
            <div className="stat-value text-lg">{getTotalTokens().toLocaleString()}</div>
          </div>
          <div className="stat bg-base-200 rounded-lg p-4">
            <div className="stat-title text-xs">Avg Response</div>
            <div className="stat-value text-lg">{getAverageResponseTime()}ms</div>
          </div>
          <div className="stat bg-base-200 rounded-lg p-4">
            <div className="stat-title text-xs">Last Activity</div>
            <div className="stat-value text-lg">{formatRelativeTime(new Date(session.updatedAt))}</div>
          </div>
        </div>

        {/* Models Used */}
        {getUniqueModels().length > 0 && (
          <div className="mb-6">
            <h4 className="text-lg font-semibold mb-2">Models Used</h4>
            <div className="flex flex-wrap gap-2">
              {getUniqueModels().map(model => (
                <span key={model} className="badge badge-info badge-outline badge-lg">
                  {model}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Timestamps */}
        <div className="grid grid-cols-2 gap-4 mb-6">
          <div className="text-sm">
            <span className="text-readout">Created:</span>
            <span className="ml-2 font-medium">{formatDateTime(new Date(session.createdAt))}</span>
          </div>
          <div className="text-sm">
            <span className="text-readout">Last Updated:</span>
            <span className="ml-2 font-medium">{formatDateTime(new Date(session.updatedAt))}</span>
          </div>
        </div>

        {/* Messages Preview */}
        <div className="mb-6">
          <h4 className="text-lg font-semibold mb-3">Messages</h4>
          <div className="space-y-3 max-h-96 overflow-y-auto">
            {(session.messages ?? []).length === 0 ? (
              <p className="text-readout text-center py-4">No messages in this session</p>
            ) : (
              (session.messages ?? []).map((message, index) => (
                <div key={message.id} className="card bg-base-200 p-4 rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className={`badge ${getRoleBadgeClass(message.role)} badge-sm`}>
                        {message.role}
                      </span>
                      <span className="text-xs text-readout">
                        #{index + 1}
                      </span>
                      {message.metadata?.model && (
                        <span className="text-xs badge badge-ghost badge-sm">
                          {message.metadata.model}
                        </span>
                      )}
                      {message.metadata?.provider && (
                        <span className="text-xs badge badge-ghost badge-sm">
                          {message.metadata.provider}
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-readout">
                      {formatRelativeTime(message.timestamp)}
                      {message.metadata?.tokenCount && (
                        <span className="ml-2">• {message.metadata.tokenCount} tokens</span>
                      )}
                    </div>
                  </div>
                  <p className="text-sm whitespace-pre-wrap">{getMessagePreview(message)}</p>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Footer Actions */}
        <div className="modal-action">
          <button className="btn btn-primary" onClick={handleOpenInChat}>
            Open in Chat
          </button>
          <button className="btn btn-neutral btn-ghost" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
