/**
 * Team Members Tab Component
 *
 * Displays and manages team members (agents).
 */

import React, { useState } from 'react'
import type { Team } from '@/types/team_tools'
import type { Agent } from '@/types/agentInteraction'
import { AgentService } from '@/services/domain/AgentService'
import { useNotificationStore } from '@/stores/notificationStore'
import { frontendLoggingService } from '@/services/frontendLoggingService'

interface TeamMembersTabProps {
  team: Team
  onAddMember: (agentId: string, agentName: string) => Promise<void>
  onRemoveMember: (memberId: string) => Promise<void>
}

export const TeamMembersTab: React.FC<TeamMembersTabProps> = ({
  team,
  onAddMember,
  onRemoveMember,
}) => {
  const addNotification = useNotificationStore((s) => s.addNotification)
  const [isAddingMember, setIsAddingMember] = useState(false)
  const [availableAgents, setAvailableAgents] = useState<Agent[]>([])
  const [selectedAgentId, setSelectedAgentId] = useState('')
  const [isLoadingAgents, setIsLoadingAgents] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

  const handleShowAddMember = async () => {
    setIsAddingMember(true)
    setIsLoadingAgents(true)
    setSearchQuery('')
    try {
      const agentService = new AgentService()
      const agents = await agentService.getAgents()
      // Filter out agents already in the team
      const memberIds = (team.members || []).map((m) => m.entity_id)
      const available = agents.filter((a: Agent) => !memberIds.includes(String(a.id)))
      setAvailableAgents(available)
      frontendLoggingService.info('TeamMembersTab', `Loaded ${available.length} available agents`)
    } catch (err) {
      frontendLoggingService.error('TeamMembersTab', 'Failed to load agents', err as Error)
      addNotification({
        type: 'error',
        title: 'Failed to Load Agents',
        message: err instanceof Error ? err.message : 'Could not load agent list',
        duration: 4000,
      })
      setIsAddingMember(false)
    } finally {
      setIsLoadingAgents(false)
    }
  }

  const handleAddMember = async () => {
    if (!selectedAgentId) return
    const agent = filteredAgents.find(a => String(a.id) === selectedAgentId)
    if (!agent) return

    try {
      await onAddMember(selectedAgentId, agent.name)
      setIsAddingMember(false)
      setSelectedAgentId('')
      setAvailableAgents([])
      setSearchQuery('')
    } catch (err) {
      frontendLoggingService.error('TeamMembersTab', 'Failed to add member', err as Error)
      addNotification({
        type: 'error',
        title: 'Failed to Add Member',
        message: err instanceof Error ? err.message : 'Could not add agent to team',
        duration: 4000,
      })
    }
  }

  const members = team.members || []

  // Filter agents by search query
  const filteredAgents = searchQuery
    ? availableAgents.filter(a =>
        a.name.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : availableAgents

  if (members.length === 0) {
    return (
      <div>
        <div className="text-center py-12">
          <div className="text-6xl mb-4">👥</div>
          <h3 className="text-xl font-semibold text-base-content mb-2">No members yet</h3>
          <p className="text-readout mb-6">
            Add agents to this team to share tools and configurations
          </p>
          <button
            onClick={handleShowAddMember}
            className="btn btn-primary"
          >
            Add Members
          </button>
        </div>

        {/* Add Member Modal - must be here since this branch returns early */}
        {renderAddMemberModal()}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <button
          onClick={handleShowAddMember}
          className="btn btn-primary btn-sm gap-2"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Add Member
        </button>
      </div>

      <div className="overflow-x-auto bg-base-100 border border-base-300 rounded-lg">
        <table className="table table-zebra w-full">
          <thead>
            <tr>
              <th>Agent</th>
              <th className="w-32">Added</th>
              <th className="w-20 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {team.members.map(member => (
              <tr key={member.id}>
                <td className="font-medium">{member.entity_name}</td>
                <td className="text-sm text-readout">
                  {new Date(member.added_at).toLocaleDateString()}
                </td>
                <td className="text-right">
                  <button
                    onClick={() => onRemoveMember(member.id)}
                    className="btn btn-ghost btn-xs text-error"
                    data-tip="Remove from team"
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Add Member Modal */}
      {renderAddMemberModal()}
    </div>
  )

  function renderAddMemberModal() {
    if (!isAddingMember) return null

    return (
      <div className="modal modal-open">
        <div className="modal-box">
          <h3 className="font-bold text-lg mb-4">Add Member</h3>

          {isLoadingAgents ? (
            <div className="flex items-center justify-center py-8">
              <span className="loading loading-spinner loading-lg"></span>
            </div>
          ) : availableAgents.length === 0 ? (
            <div className="text-center py-4">
              <p className="text-readout">No available agents to add.</p>
              <p className="text-sm text-readout mt-1">All agents are already members of this collective.</p>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="form-control">
                <label className="label">
                  <span className="label-text">Search Agents</span>
                </label>
                <input
                  type="text"
                  className="input input-bordered"
                  placeholder="Type to filter agents..."
                  value={searchQuery}
                  onChange={(e) => {
                    setSearchQuery(e.target.value)
                    setSelectedAgentId('')
                  }}
                  autoFocus
                />
              </div>

              <div className="form-control">
                <label className="label">
                  <span className="label-text">
                    Select Agent
                    {searchQuery && (
                      <span className="text-xs text-readout ml-2">
                        ({filteredAgents.length} of {availableAgents.length})
                      </span>
                    )}
                  </span>
                </label>
                <select
                  className="select select-bordered"
                  value={selectedAgentId}
                  onChange={(e) => setSelectedAgentId(e.target.value)}
                >
                  <option value="">-- Select an agent --</option>
                  {filteredAgents.map(agent => (
                    <option key={agent.id} value={String(agent.id)}>
                      {agent.name}
                    </option>
                  ))}
                </select>
              </div>

              {searchQuery && filteredAgents.length === 0 && (
                <p className="text-sm text-readout text-center py-2">
                  No agents match "{searchQuery}"
                </p>
              )}
            </div>
          )}

          <div className="modal-action">
            <button
              className="btn btn-ghost"
              onClick={() => {
                setIsAddingMember(false)
                setSelectedAgentId('')
                setAvailableAgents([])
                setSearchQuery('')
              }}
            >
              Cancel
            </button>
            {!isLoadingAgents && availableAgents.length > 0 && filteredAgents.length > 0 && (
              <button
                className="btn btn-primary"
                onClick={handleAddMember}
                disabled={!selectedAgentId}
              >
                Add Member
              </button>
            )}
          </div>
        </div>
        <div className="modal-backdrop" onClick={() => {
          setIsAddingMember(false)
          setSelectedAgentId('')
          setAvailableAgents([])
          setSearchQuery('')
        }}></div>
      </div>
    )
  }
}
