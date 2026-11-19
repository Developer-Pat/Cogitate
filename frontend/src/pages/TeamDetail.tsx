/**
 * Collective Detail Page
 *
 * View and manage a collective and its members.
 */

import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { teamToolService } from '../services/domain/TeamToolService'
import type { Team } from '../types/team_tools'
import type { CollectionUpdate } from '../types/collections'
import { EditCollectionModal } from '@/components/features/collections/EditCollectionModal'
import { DeleteConfirmationModal } from '@/components/features/collections/DeleteConfirmationModal'
import { TeamMembersTab } from '@/components/Teams/TeamMembersTab'
import { TeamToolsTab } from '@/components/Teams/TeamToolsTab'
import { AddToolsModal } from '@/components/Teams/AddToolsModal'
import { AddToolboxesModal } from '@/components/Teams/AddToolboxesModal'
import { useNotificationStore } from '../stores/notificationStore'
import { frontendLoggingService } from '../services/frontendLoggingService'

type ActiveTab = 'members' | 'tools'

export default function TeamDetail() {
  const { teamId } = useParams<{ teamId: string }>()
  const navigate = useNavigate()
  const addNotification = useNotificationStore((s) => s.addNotification)
  const [team, setTeam] = useState<Team | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<ActiveTab>('members')
  const [editingTeam, setEditingTeam] = useState<Team | null>(null)
  const [deletingTeam, setDeletingTeam] = useState<Team | null>(null)
  const [showAddToolsModal, setShowAddToolsModal] = useState(false)
  const [showAddToolboxesModal, setShowAddToolboxesModal] = useState(false)
  const [isSyncing, setIsSyncing] = useState(false)

  // Load team from backend
  const loadTeam = useCallback(async () => {
    if (!teamId) return
    try {
      setIsLoading(true)
      setError(null)
      const found = await teamToolService.getTeam(teamId)
      setTeam(found)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load collective')
      setTeam(null)
    } finally {
      setIsLoading(false)
    }
  }, [teamId])

  // Initial load
  useEffect(() => {
    loadTeam()
  }, [loadTeam])

  const handleBack = () => {
    navigate('/teams')
  }

  const handleEdit = () => {
    setEditingTeam(team)
  }

  const handleSaveEdit = async (_id: string, updates: CollectionUpdate) => {
    if (!team) return
    try {
      await teamToolService.updateTeam(team.id, updates)
      await loadTeam()
      setEditingTeam(null)
    } catch (err) {
      console.error('Failed to update team:', err)
    }
  }

  const handleDelete = () => {
    setDeletingTeam(team)
  }

  const handleConfirmDelete = async (id: string) => {
    try {
      await teamToolService.deleteTeam(id)
      setDeletingTeam(null)
      navigate('/teams')
    } catch (err) {
      console.error('Failed to delete team:', err)
    }
  }

  const handleAddMember = async (agentId: string, agentName: string) => {
    if (!team) return
    try {
      await teamToolService.addMemberToTeam(team.id, {
        entity_id: agentId,
        entity_type: 'agent',
        entity_name: agentName,
      })
      await loadTeam()
    } catch (err) {
      frontendLoggingService.error('TeamDetail', 'Failed to add member', err as Error)
      addNotification({
        type: 'error',
        title: 'Failed to Add Member',
        message: err instanceof Error ? err.message : 'Could not add agent to team',
        duration: 4000,
      })
      throw err // Re-throw so the tab component can also handle it
    }
  }

  const handleRemoveMember = async (memberId: string) => {
    if (!team) return
    try {
      await teamToolService.removeMemberFromTeam(team.id, memberId)
      await loadTeam()
    } catch (err) {
      console.error('Failed to remove member:', err)
    }
  }

  const handleAddTools = () => {
    setShowAddToolsModal(true)
  }

  const handleAddToolboxes = () => {
    setShowAddToolboxesModal(true)
  }

  const handleAssignTool = async (toolId: string, priority: number) => {
    if (!team) return
    try {
      await teamToolService.assignToolToTeam(team.id, {
        tool_id: toolId,
        source_type: 'direct',
        priority,
        is_active: true,
        config: {},
      })
      await loadTeam()
      setShowAddToolsModal(false)
    } catch (err) {
      console.error('Failed to assign tool:', err)
    }
  }

  const handleAssignToolbox = async (toolboxId: string, priority: number) => {
    if (!team) return
    try {
      await teamToolService.assignToolToTeam(team.id, {
        tool_id: toolboxId,
        source_type: 'toolbox',
        priority,
      })
      await loadTeam()
      setShowAddToolboxesModal(false)
    } catch (err) {
      console.error('Failed to assign toolbox:', err)
    }
  }

  const handleRemoveTool = async (toolId: string, sourceType?: 'direct' | 'toolbox') => {
    if (!team) return
    try {
      await teamToolService.removeToolFromTeam(team.id, toolId, sourceType ?? 'direct')
      await loadTeam()
    } catch (err) {
      console.error('Failed to remove tool:', err)
    }
  }

  const handleSyncTools = async () => {
    if (!team) return
    try {
      setIsSyncing(true)
      const result = await teamToolService.syncTeamTools(team.id)
      
      // Show conflict notifications if any
      if (result.conflicts && result.conflicts.length > 0) {
        console.log('Conflicts detected:', result.conflicts)
        // In a real app, show toast notifications here
      }
      
      await loadTeam()
    } catch (err) {
      console.error('Failed to sync tools:', err)
    } finally {
      setIsSyncing(false)
    }
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-base-200 flex items-center justify-center">
        <span className="loading loading-lg"></span>
      </div>
    )
  }

  if (error || !team) {
    return (
      <div className="min-h-screen bg-base-200 flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-base-content mb-2">Collective Not Found</h1>
          <p className="text-readout mb-4">
            {error || "The team you're looking for doesn't exist."}
          </p>
          <button
            onClick={() => navigate('/teams')}
            className="btn btn-primary"
          >
            Back to Teams
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-base-200">
      {/* Header Bar */}
      <div className="bg-base-100 border-b px-6 py-4">
        <button
          onClick={handleBack}
          className="btn btn-ghost gap-2 mb-4"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          Back to Teams
        </button>

        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-start gap-3">
              <div className="text-5xl flex-shrink-0 mt-1">{team.icon}</div>
              <div className="min-w-0">
                <h1 className="text-2xl font-bold text-base-content">{team.name}</h1>
                <p className="text-readout whitespace-normal">{team.description}</p>
              </div>
            </div>
          </div>
          <div className="flex gap-2 flex-shrink-0">
            <button
              onClick={handleEdit}
              className="btn btn-ghost gap-2"
              data-tip="Edit team"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
              Edit
            </button>
            <button
              onClick={handleDelete}
              className="btn btn-ghost text-error gap-2"
              data-tip="Delete team"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
              Delete
            </button>
          </div>
        </div>

        {/* Metadata */}
        <div className="flex items-center gap-4 mt-4 text-sm text-readout">
          <div className="badge badge-outline">{team.members.length} members</div>
          <div className="badge badge-outline">{team.tools.length} tools</div>
          <span>Created {new Date(team.created_at).toLocaleDateString()}</span>
          <span>•</span>
          <span>Updated {new Date(team.updated_at).toLocaleDateString()}</span>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mt-4">
          <button
            onClick={() => setActiveTab('members')}
            className={`btn btn-sm ${activeTab === 'members' ? 'btn-active btn-selected' : 'btn-outline'}`}
          >
            Members ({team.members.length})
          </button>
          <button
            onClick={() => setActiveTab('tools')}
            className={`btn btn-sm ${activeTab === 'tools' ? 'btn-active btn-selected' : 'btn-outline'}`}
          >
            Tools & Toolboxes ({team.tools.length})
          </button>
          <button
            onClick={handleSyncTools}
            className="btn btn-sm btn-ghost gap-2"
            disabled={isSyncing}
          >
            {isSyncing ? (
              <>
                <span className="loading loading-spinner loading-xs"></span>
                Syncing...
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Sync Tools
              </>
            )}
          </button>
        </div>
      </div>

      {/* Tab Content */}
      <div className="p-6">
        {activeTab === 'members' ? (
          <TeamMembersTab
            team={team}
            onAddMember={handleAddMember}
            onRemoveMember={handleRemoveMember}
          />
        ) : (
          <TeamToolsTab
            team={team}
            onAddTools={handleAddTools}
            onAddToolboxes={handleAddToolboxes}
            onRemoveTool={handleRemoveTool}
          />
        )}
      </div>

      {/* Edit Modal */}
      {editingTeam && (
        <EditCollectionModal
          collection={editingTeam}
          onClose={() => setEditingTeam(null)}
          onSave={handleSaveEdit}
        />
      )}

      {/* Delete Confirmation Modal */}
      {deletingTeam && (
        <DeleteConfirmationModal
          collection={deletingTeam}
          onClose={() => setDeletingTeam(null)}
          onConfirm={handleConfirmDelete}
        />
      )}

      {/* Add Tools Modal */}
      {showAddToolsModal && (
        <AddToolsModal
          team={team}
          onClose={() => setShowAddToolsModal(false)}
          onAssign={handleAssignTool}
        />
      )}

      {/* Add Toolboxes Modal */}
      {showAddToolboxesModal && (
        <AddToolboxesModal
          team={team}
          onClose={() => setShowAddToolboxesModal(false)}
          onAssign={handleAssignToolbox}
        />
      )}
    </div>
  )
}
