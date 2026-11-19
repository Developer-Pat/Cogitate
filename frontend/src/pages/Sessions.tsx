import { API_BASE_URL } from '../services/apiClient';
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { PageBanner } from '../components/ui/PageBanner';
import { PageContainer } from '../components/ui/PageContainer';
import { usePageTitle } from '../hooks/usePageTitle';
import { HelpButton } from '../components/help';
import { SessionFilters } from '../components/sessions/SessionFilters';
import { SessionTable } from '../components/sessions/SessionTable';
import { SessionDetailsModal } from '../components/sessions/SessionDetailsModal';
import { sessionsService } from '../services/domain/SessionsService';
import { useCognitiveHubStore } from '../stores/cognitiveHubStore';
import { useSettingsStore } from '../stores/settingsStore';
import { resolveTitleModel } from '../utils/titleModelResolver';
import { frontendLoggingService } from '../services/frontendLoggingService';
import { useNotificationStore } from '../stores/notificationStore';
import type { ConversationSession } from '../types/agentInteraction';

interface FilterState {
  searchQuery: string;
  sortBy: 'date' | 'title' | 'count';
  sortOrder: 'asc' | 'desc';
  dateRange: 'all' | 'today' | 'week' | 'month';
  agents: AgentInfo[];
  agentFilter?: string | number;
  unnamedOnly: boolean;
}

interface AgentInfo {
  id: string | number;
  name: string;
}

const Sessions: React.FC = () => {
  usePageTitle('Sessions', 'Manage and organize your conversation sessions')
  
  // Read sessions directly from Zustand store (single source of truth)
  const sessions = useCognitiveHubStore(state => state.sessions)

  const [filteredSessions, setFilteredSessions] = useState<ConversationSession[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [filters, setFilters] = useState<FilterState>({
    searchQuery: '',
    sortBy: 'date',
    sortOrder: 'desc',
    dateRange: 'all',
    agents: [],
    unnamedOnly: false
  });

  const [selectedSession, setSelectedSession] = useState<ConversationSession | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  // THE SMART-RENAME GUARD (2026-09-03): one click = one rename. The
  // button keeps focus after click and Space/Enter re-activates it; a
  // buggy mouse double-fires too. An in-flight run disables the button
  // until it completes. The REF is the synchronous lock (two clicks in
  // the same tick both see the state as null — React state is async);
  // the STATE drives the disabled UI.
  const renamingRef = useRef<string | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [isBulkModalOpen, setIsBulkModalOpen] = useState(false);
const [isDeleting, setIsDeleting] = useState(false);

  // Load sessions on mount (no subscription needed - Zustand handles reactivity)
  useEffect(() => {
    const loadSessions = async () => {
      try {
        setIsLoading(true);
        // Load sessions WITH messages from database for full data
        await sessionsService.loadFromBackend(true);
        frontendLoggingService.info('Sessions', 'Initial load complete', {
          count: sessionsService.getSessions().length
        });
      } catch (error) {
        frontendLoggingService.error('Sessions', 'Failed to load sessions', { error });
      } finally {
        setIsLoading(false);
      }
    };

    loadSessions();
  }, []);

  // Apply filters whenever sessions or filter state changes
  useEffect(() => {
    frontendLoggingService.debug('Sessions', 'Applying filters', {
      sessionsCount: sessions.length,
      filters
    });

    let result = [...sessions];

    // Apply date range filter
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
    const monthAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);

    if (filters.dateRange !== 'all') {
      const beforeCount = result.length;
      result = result.filter(session => {
        const sessionDate = new Date(session.createdAt);
        switch (filters.dateRange) {
          case 'today': return sessionDate >= today;
          case 'week': return sessionDate >= weekAgo;
          case 'month': return sessionDate >= monthAgo;
        }
      });
      frontendLoggingService.debug('Sessions', 'Date range filter applied', {
        before: beforeCount,
        after: result.length,
        dateRange: filters.dateRange
      });
    }

    // Apply unnamed-only filter — sessions with default/untitled names
    if (filters.unnamedOnly) {
      result = result.filter(s => !s.title || s.title === '' || s.title === 'None' || s.title.startsWith('New Session '));
    }

    // Apply agent filter
    if (filters.agentFilter) {
      const beforeCount = result.length;
      result = result.filter(session =>
        String(session.agentId) === String(filters.agentFilter)
      );
      frontendLoggingService.debug('Sessions', 'Agent filter applied', {
        before: beforeCount,
        after: result.length,
        agentFilter: filters.agentFilter
      });
    }

    // Apply search filter
    if (filters.searchQuery.trim()) {
      const beforeCount = result.length;
      const query = filters.searchQuery.toLowerCase();
      result = result.filter(session =>
        session.title.toLowerCase().includes(query)
      );
      frontendLoggingService.debug('Sessions', 'Search filter applied', {
        before: beforeCount,
        after: result.length,
        query
      });
    }

    // Apply sorting
    result.sort((a, b) => {
      let comparison = 0;

      switch (filters.sortBy) {
        case 'date':
          comparison = new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime();
          break;
        case 'title':
          comparison = a.title.localeCompare(b.title);
          break;
        case 'count':
          comparison = (a.messages?.length || 0) - (b.messages?.length || 0);
          break;
      }

      return filters.sortOrder === 'asc' ? comparison : -comparison;
    });

    frontendLoggingService.info('Sessions', 'Filtered sessions', {
      totalSessions: sessions.length,
      filteredCount: result.length,
      sessionIds: result.map(s => s.id)
    });

    setFilteredSessions(result);
  }, [sessions, filters]);

  const handleFilterChange = useCallback((newFilters: FilterState) => {
    setFilters(newFilters);
  }, []);

  const handleDeleteSession = useCallback(async (sessionId: string) => {
    // Show confirmation dialog
    if (!window.confirm('Are you sure you want to delete this session? This action cannot be undone.')) {
      return;
    }

    try {
      // Call backend API directly
      const response = await fetch(`${API_BASE_URL}/api/v1/sessions/${sessionId}`, {
        method: 'DELETE'
      });

      if (!response.ok) {
        throw new Error('Failed to delete session');
      }

      useNotificationStore.getState().addSuccess('Session Deleted', `Session ${sessionId} deleted`);
      // Refresh
      await sessionsService.loadFromBackend(false);
    } catch (error) {
      frontendLoggingService.error('Sessions', 'Failed to delete session', { error, sessionId });
      useNotificationStore.getState().addError('Delete Failed', 'Failed to delete session');
    }
  }, []);

  // THE SMART RENAME (2026-08-22, user): generate a title from the
  // FULL session conversation via the local title service.
  const handleSmartRenameSession = useCallback(async (sessionId: string) => {
    // THE GUARD: ignore a second trigger while a rename is in flight —
    // double-clicks, focused-button Space/Enter re-activation, or a
    // buggy mouse must not fire a second LLM call. The REF lock is
    // synchronous (catches same-tick double-fire); the state drives
    // the disabled button UI.
    if (renamingRef.current) return;
    renamingRef.current = sessionId;
    setRenamingId(sessionId);
    try {
      // THE MODEL SOURCE (2026-09-03, the Local Services arc): the
      // session's agent + the title preference — the SAME resolver the
      // chat-page rename uses. Sessions-page smart rename previously
      // ignored the preference (always the DB default); now both
      // surfaces honor the user's choice consistently.
      const hub = useCognitiveHubStore.getState()
      const sess = hub.sessions.find(s => String(s.id) === String(sessionId))
      const agent = hub.agents.find(a => String(a.id) === String(sess?.agentId)) || null
      const general = useSettingsStore.getState().settings.general
      const modelOverride = resolveTitleModel(agent, general)
      const res = await fetch(`/api/v1/sessions/${sessionId}/title`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: modelOverride }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error((body as { detail?: string }).detail || 'Title generation failed');
      }
      const data = await res.json() as { title: string };
      if (data.title) {
        useCognitiveHubStore.getState().renameSessionById(sessionId, data.title);
        await fetch(`${API_BASE_URL}/api/v1/sessions/${sessionId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: data.title }),
        });
        useNotificationStore.getState().addSuccess('Renamed', `Session titled: ${data.title}`);
      }
    } catch (error) {
      useNotificationStore.getState().addError(
        'Rename failed',
        error instanceof Error ? error.message : 'Could not generate a title'
      );
    } finally {
      renamingRef.current = null;
      setRenamingId(null);
    }
  }, []);

  const handleRenameSession = useCallback(async (sessionId: string, newTitle: string) => {
    try {
      frontendLoggingService.info('Sessions', 'Renaming session', { sessionId, newTitle });
      
      // Update in Zustand store (single source of truth)
      useCognitiveHubStore.getState().renameSessionById(sessionId, newTitle);
      
      // Sync to backend
      const response = await fetch(`${API_BASE_URL}/api/v1/sessions/${sessionId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ title: newTitle })
      });

      if (!response.ok) {
        throw new Error('Failed to rename session on backend');
      }

      frontendLoggingService.info('Sessions', 'Session renamed successfully', { sessionId, newTitle });
    } catch (error) {
      frontendLoggingService.error('Sessions', 'Failed to rename session', { error, sessionId });
      alert('Failed to rename session. Please try again.');
    }
  }, []);

  const handleViewDetails = useCallback((session: ConversationSession) => {
    setSelectedSession(session);
    setIsModalOpen(true);
  }, []);

  // THE DEEP-LINK (2026-08-22, user): ?session=<id> opens the page WITH
  // that session selected — the eye toast's 'Go to Sessions page' link
  // carries it. No surprise navigation: the link label says it leaves
  // the current page, and this handler just selects the target.
  // Positioned AFTER handleViewDetails (fixed 2026-08-22): the effect
  // referenced the useCallback const before its initialization (TDZ —
  // 'can't access lexical declaration before initialization'). FIRE-ONCE
  // also guards against the modal's store write re-triggering it.
  const deepLinkHandledRef = useRef(false);
  useEffect(() => {
    if (deepLinkHandledRef.current) return;
    const params = new URLSearchParams(window.location.search);
    const targetId = params.get('session');
    if (!targetId) return;
    const found = sessions.find((s) => String(s.id) === targetId);
    if (found) {
      deepLinkHandledRef.current = true;
      handleViewDetails(found);
      // Clear the param so a later sessions change can't re-trigger it.
      const url = new URL(window.location.href);
      url.searchParams.delete('session');
      window.history.replaceState({}, '', url.toString());
    }
  }, [sessions, handleViewDetails]);

  const handleCloseModal = useCallback(() => {
    setIsModalOpen(false);
    setSelectedSession(null);
  }, []);

  const handleBulkDelete = async (idsToDelete: number[]) => {
    setIsDeleting(true);
    try {
      const res = await fetch('/api/v1/sessions/bulk-delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(idsToDelete),
      });
      const result = await res.json();
      if (res.ok) {
        useNotificationStore.getState().addSuccess(
          'Sessions Deleted',
          `Deleted ${result.total_deleted} session(s)`
        );
        setSelectedIds(new Set());
        setIsDeleting(false);
        setIsBulkModalOpen(false);
        await sessionsService.loadFromBackend(false);
      } else {
        throw new Error(result.detail || 'Bulk delete failed');
      }
    } catch (error: any) { // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
      setIsDeleting(false);
      useNotificationStore.getState().addError('Bulk Delete Failed', error.message);
    }
  };

  const handleRefresh = useCallback(async () => {
    try {
      setIsLoading(true);
      // Refresh with full message data from database
      await sessionsService.loadFromBackend(false);
      frontendLoggingService.info('Sessions', 'Refresh complete', {
        count: sessionsService.getSessions().length
      });
    } catch (error) {
      frontendLoggingService.error('Sessions', 'Failed to refresh sessions', { error });
    } finally {
      setIsLoading(false);
    }
  }, []);

  return (
    <PageContainer>
      {/* Page Header — the icon is gone (2026-08-22, user) and the
          Help + Refresh buttons sit ON the title row via the banner's
          action slot (reclaims the vertical space of the old row). */}
      <PageBanner
        title="Session Management"
        tooltip="Manage and organize your conversation sessions"
        action={
          <div className="flex items-center gap-2">
            {/* THE APP-STANDARD HELP BUTTON (2026-08-22, user): most pages
                use the DEFAULT widget — the HelpCircle icon + 'Help' label
                in btn btn-ghost rounded-lg (Dashboard, Logs, Macros,
                Settings, SkillsManagement, ToolManagement, ...). The
                text-only override was the chat-page outlier; Sessions now
                matches the majority for consistency. */}
            <HelpButton context="sessions" tooltipPosition="bottom" />
            {/* Refresh — the PRIMARY PILL (2026-08-22, user: 'the refresh
                button should have the same style'): bg-primary/20
                text-primary border-primary/30 — the app's assist-button
                style, matching the Help button next to it. */}
            <button
              className="btn rounded-lg bg-primary/20 text-primary border-primary/30 hover:bg-primary/30 hover:border-primary/40"
              onClick={handleRefresh}
              disabled={isLoading}
            >
              Refresh
            </button>
          </div>
        }
      />

      {/* Filters */}
      <SessionFilters onFilterChange={handleFilterChange} />

      {/* Session Table */}
      <div className="mt-4">
        <SessionTable
          sessions={filteredSessions}
          agents={filters.agents}
          onDeleteSession={handleDeleteSession}
          onRenameSession={handleRenameSession}
          onSmartRenameSession={handleSmartRenameSession}
          renamingId={renamingId}
          onViewDetails={handleViewDetails}
          isLoading={isLoading}
          selectedIds={selectedIds}
          onSelectionChange={setSelectedIds}
        />
      </div>

      {/* Bulk Delete Button */}
      {selectedIds.size > 1 && (
        <div className="flex justify-end mt-2">
          <button
            className="btn btn-error btn-sm"
            onClick={() => setIsBulkModalOpen(true)}
          >
            Delete {selectedIds.size} Selected Sessions
          </button>
        </div>
      )}

      {/* Bulk Delete Confirmation Modal */}
      <dialog className={`modal ${isBulkModalOpen ? 'modal-open' : ''}`}>
        <div className="modal-box">
          <h3 className="font-bold text-lg">Delete {selectedIds.size} Sessions?</h3>
          <p className="py-4 text-readout">
            This action cannot be undone. All messages, tool calls, and trace data for
            the selected sessions will be permanently removed.
          </p>
          <div className="modal-action">
            <button className="btn btn-neutral btn-ghost" onClick={() => setIsBulkModalOpen(false)}>Cancel</button>
            <button className="btn btn-error" onClick={() => handleBulkDelete(Array.from(selectedIds).map(Number))} disabled={isDeleting}>{isDeleting ? 'Deleting...' : `Delete ${selectedIds.size} Sessions`}</button>
          </div>
        </div>
        <form method="dialog" className="modal-backdrop">
          <button onClick={() => setIsBulkModalOpen(false)}>close</button>
        </form>
      </dialog>

      {/* Session Details Modal */}
      <SessionDetailsModal
        session={selectedSession}
        agents={filters.agents}
        isOpen={isModalOpen}
        onClose={handleCloseModal}
      />
    </PageContainer>
  );
};

export default Sessions;
