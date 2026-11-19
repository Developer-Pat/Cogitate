import React, { useState, useMemo } from 'react'
import { frontendLoggingService } from '@/services/frontendLoggingService'
import type { Profile } from '@/services/domain/ProfileService'
import { profileService, archiveFolderName, budgetReasonLabel } from '@/services/domain/ProfileService'
import { useNotificationStore } from '@/stores/notificationStore'

import { AddToCollectionModal } from '../features/collections/AddToCollectionModal'
import CollectionsBadges from './CollectionsBadges'
import AgentHealthCell from './AgentHealthCell'
import AgentServiceBadge from './AgentServiceBadge'

import type { Collection } from '@/types/collections'

interface ProfileListProps {
  profiles: Profile[]
  selectedProfileId?: string
  onSelectProfile: (profile: Profile) => void
  onCreateNew: () => void
  onDuplicate?: (profile: Profile) => void
  isLoading?: boolean
  viewMode?: 'list' | 'table'
  onViewModeChange?: (mode: 'list' | 'table') => void
  // Team filtering props
  teams?: Collection[]
  selectedTeamId?: string | 'all'
  onTeamChange?: (teamId: string | 'all') => void
  loadingTeams?: boolean
  totalProfiles?: number
  // The ARCHIVED section (2026-08-19) — deactivated agents, always
  // visible in the sidebar (not just the empty state)
  archivedAgents?: Array<Record<string, unknown>>
  onRestoreAgent?: (agentId: string, agentName: string) => void
  onHardDeleteAgent?: (agentId: string, agentName: string) => void
  showArchived?: boolean
  onToggleArchived?: () => void
}

export default function ProfileList({
  profiles,
  selectedProfileId,
  onSelectProfile,
  onCreateNew,
  onDuplicate,
  isLoading = false,
  viewMode = 'list',
  onViewModeChange,
  teams = [],
  selectedTeamId = 'all',
  onTeamChange,
  loadingTeams = false,
  totalProfiles = 0,
  archivedAgents = [],
  onRestoreAgent,
  onHardDeleteAgent,
  showArchived = false,
  onToggleArchived,
}: ProfileListProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [duplicatingId, setDuplicatingId] = useState<string | null>(null)
  const [addingToCollectionProfile, setAddingToCollectionProfile] = useState<Profile | null>(null)

  // Filter and sort profiles
  // First sort alphabetically by name, then filter by search query
  const filteredProfiles = useMemo(() => {
    // Sort profiles alphabetically by name
    const sortedProfiles = [...profiles].sort((a, b) => 
      a.name.toLowerCase().localeCompare(b.name.toLowerCase())
    )
    
    // Then filter based on search query
    if (!searchQuery.trim()) return sortedProfiles

    const query = searchQuery.toLowerCase()
    return sortedProfiles.filter(
      (profile) =>
        profile.name.toLowerCase().includes(query) ||
        profile.description.toLowerCase().includes(query)
    )
  }, [profiles, searchQuery])

  const handleDuplicate = async (e: React.MouseEvent, profile: Profile) => {
    e.stopPropagation()
    if (isLoading || duplicatingId) return

    try {
      setDuplicatingId(profile.id)
      if (onDuplicate) {
        await onDuplicate(profile)
      } else {
        // Default behavior: duplicate via API
        await profileService.duplicateAgent(profile.id)
        // Reload profiles after duplication
        window.location.reload()
      }
    } catch (error) {
      frontendLoggingService.error('ProfileList', 'Failed to duplicate profile', error as Error)
      useNotificationStore.getState().addError('Duplicate Failed', 'Failed to duplicate profile')
    } finally {
      setDuplicatingId(null)
    }
  }

  const handleAddToCollection = (e: React.MouseEvent, profile: Profile) => {
    e.stopPropagation()
    setAddingToCollectionProfile(profile)
  }

  const handleAddedToCollections = (_collectionIds: string[]) => {
    // Notification already shown by AddToCollectionModal
    setAddingToCollectionProfile(null)
  }

  return (
    <div className="w-80 bg-base-100 border-l border-base-300 flex flex-col h-full">
      {/* Header with New Button and View Toggle */}
      <div className="p-4 border-b border-base-300">
        <div className="flex gap-2 mb-3">
          <button
            onClick={onCreateNew}
            disabled={isLoading}
            className="btn btn-primary btn-sm flex-1 rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
          >
            <span className="text-lg">+</span>
            New Profile
          </button>
          {onViewModeChange && (
            <div className="btn-group">
              <div className="tooltip tooltip-bottom" data-tip="List view">
                <button
                  className={`btn btn-sm ${viewMode === 'list' ? 'btn-active btn-selected' : 'btn-outline'}`}
                  onClick={() => onViewModeChange('list')}
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                  </svg>
                </button>
              </div>
              <div className="tooltip tooltip-bottom" data-tip="Table view">
                <button
                  className={`btn btn-sm ${viewMode === 'table' ? 'btn-active btn-selected' : 'btn-outline'}`}
                  onClick={() => onViewModeChange('table')}
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                </button>
              </div>
            </div>
          )}
        </div>
        
        {/* Team Filter Dropdown */}
        {onTeamChange && (
          <div>
            <label className="label py-1 px-1">
              <span className="label-text text-xs font-semibold">Filter by Team</span>
            </label>
            <select
              value={selectedTeamId}
              onChange={(e) => onTeamChange(e.target.value as string | 'all')}
              disabled={loadingTeams}
              className="select select-bordered select-sm w-full rounded-[var(--form-input-radius)] bg-[var(--form-input-bg)] text-[var(--form-input-text)]"
            >
              <option value="all">🌐 All Agents ({totalProfiles})</option>
              {loadingTeams && <option value="">Loading teams...</option>}
              {!loadingTeams && teams.map(team => (
                <option key={team.id} value={team.id}>
                  👥 {team.name} ({team.items?.length || 0} agents)
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Search */}
      <div className="p-4 border-b border-base-300">
        <input
          type="text"
          placeholder="Search profiles..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          disabled={isLoading}
          className="input input-bordered input-sm w-full rounded-[var(--form-input-radius)] px-[var(--form-input-padding)] bg-[var(--form-input-bg)] border-[var(--form-input-border)] text-[var(--form-input-text)] focus:border-[var(--form-input-focus-border)] transition-all duration-[var(--button-transition)]"
        />
      </div>

      {/* Profile List */}
      <div className="flex-1 overflow-y-auto">
        {filteredProfiles.length === 0 ? (
          <div className="p-4 text-center text-readout">
            {profiles.length === 0 ? (
              <div>
                <p className="text-sm">No profiles yet</p>
                <p className="text-xs mt-2">Create one to get started</p>
              </div>
            ) : (
              <p className="text-sm">No profiles match your search</p>
            )}
          </div>
        ) : (
          <div className="divide-y divide-base-300">
            {filteredProfiles.map((profile) => (
              <div
                key={profile.id}
                className="group w-full text-left p-3 hover:bg-base-200 transition-colors flex gap-3 items-center min-w-0"
              >
                <button
                  onClick={() => onSelectProfile(profile)}
                  className={`flex-1 flex gap-3 items-center min-w-0 ${
                    selectedProfileId === profile.id ? 'bg-primary/10 border-l-4 border-primary' : ''
                  }`}
                >
                  {/* Thumbnail */}
                  <div className="flex-shrink-0">
                    {profile.image_url ? (
                      <img
                        src={profile.image_url}
                        alt={profile.name}
                        className="w-12 h-12 rounded object-cover"
                      />
                    ) : (
                      <div className="w-12 h-12 rounded bg-base-300 flex items-center justify-center text-lg">
                        👤
                      </div>
                    )}
                  </div>

                  {/* Profile Info */}
                  <div className="flex-1 min-w-0 w-0">
                    <div className="flex items-center gap-2 min-w-0">
                      <h3 className="font-semibold text-sm truncate">{profile.name}</h3>
                      {/* Provider health — the same data the chat's agent-selector
                          badge shows, and the same the table column renders. It
                          lives HERE because this list is the page's default view:
                          a health surface you have to switch views to find is one
                          you never find. */}
                      <AgentHealthCell health={profile.health} agentName={profile.name} compact />
                      {/* The CURRENT question, beside the historical one (G5-F2): only the
                          exception is drawn here — a row that can run is the norm. */}
                      <AgentServiceBadge
                        availability={profile.service_availability}
                        agentName={profile.name}
                        compact
                      />
                    </div>
                    <p className="text-xs text-readout truncate" title={`${profile.provider} • ${profile.model}`}>
                      {profile.provider} • {profile.model}
                    </p>
                    {/* THE DECLARED-VS-SENT READ (G.1) — state ON the row, in the
                        page's default view: `declared → sent` with the reason, the
                        sidebar's own terse form. The arrow is the whole sentence
                        (the full one is the row's aria-label), and the reason is
                        NOT droppable: two numbers without it read as a bug. When
                        nothing is declared the arrow's left side is a dash rather
                        than a borrowed number. */}
                    {profile.output_budget && (
                      <p
                        className="text-xs text-readout"
                        aria-label={`Sends ${profile.output_budget.effective} tokens, declared ${profile.output_budget.declared ?? 'nothing'} — ${budgetReasonLabel(profile.output_budget.reason)}`}
                      >
                        {profile.output_budget.declared === null
                          ? '—'
                          : <span className="font-mono">{profile.output_budget.declared}</span>}
                        {' → '}
                        <span className="font-mono font-semibold">{profile.output_budget.effective}</span>
                        {' · '}{budgetReasonLabel(profile.output_budget.reason)}
                        {/* THE OBSERVED DIFFERENCE (G-A ii) — only when the last turn
                            carried something OTHER than the prediction: the equal case
                            is already said above, a difference is the signal (a
                            declaration changed, a window clamped, a driver's floor
                            moved). */}
                        {profile.output_budget.observed
                          && profile.output_budget.observed.sent !== profile.output_budget.effective && (
                          <> · last {profile.output_budget.observed.sent}</>
                        )}
                      </p>
                    )}
                    {/* Collection Badges */}
                    <CollectionsBadges profileId={profile.id} />
                  </div>
                </button>

                {/* Add to Collection Button */}
                <div className="tooltip tooltip-top" data-tip="Add to collection">
                  <button
                    type="button"
                    onClick={(e) => handleAddToCollection(e, profile)}
                    className="btn btn-ghost btn-xs text-primary"
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      className="h-4 w-4"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"
                      />
                    </svg>
                  </button>
                </div>

                {/* Duplicate Button */}
                <div className="tooltip tooltip-top" data-tip="Duplicate this profile">
                  <button
                    type="button"
                    onClick={(e) => handleDuplicate(e, profile)}
                    disabled={isLoading || duplicatingId === profile.id}
                    className="btn btn-ghost btn-xs "
                  >
                    {duplicatingId === profile.id ? (
                      <span className="loading loading-spinner loading-xs"></span>
                    ) : (
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        className="h-4 w-4"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                        />
                      </svg>
                    )}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* The ARCHIVED section (2026-08-19) — deactivated agents are
          recoverable: the archive record is DB-discoverable. Always
          visible in the sidebar, not buried in the empty state. */}
      <div className="border-t border-base-300 p-3">
        <button
          onClick={onToggleArchived}
          className="btn btn-ghost btn-sm w-full justify-between"
        >
          <span>Archived profiles ({archivedAgents.length})</span>
          <span>{showArchived ? '▾' : '▸'}</span>
        </button>
        {showArchived && (
          <div className="mt-2 space-y-2">
            {archivedAgents.length === 0 ? (
              <div className="text-xs text-readout px-2 py-1">
                No archived profiles — deactivated agents appear here and can be restored.
              </div>
            ) : (
              archivedAgents.map(d => (
                <div key={String(d.id)}
                     className="card bg-base-200 p-3 flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <div className="font-semibold text-sm truncate">{String(d.name)}</div>
                    <div className="text-xs text-readout truncate">
                      {archiveFolderName(String(d.archived_path ?? ''))}
                    </div>
                  </div>
                  <div className="flex gap-1 shrink-0">
                    <button
                      onClick={() => onRestoreAgent?.(String(d.id), String(d.name))}
                      className="btn btn-primary btn-xs"
                    >
                      Restore
                    </button>
                    <button
                      onClick={() => onHardDeleteAgent?.(String(d.id), String(d.name))}
                      className="btn btn-error btn-xs"
                    >
                      Delete permanently
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* Add to Collection Modal */}
      {addingToCollectionProfile && (
        <AddToCollectionModal
          entityId={addingToCollectionProfile.id}
          entityName={addingToCollectionProfile.name}
          entityType="agent"
          onClose={() => setAddingToCollectionProfile(null)}
          onAdded={handleAddedToCollections}
        />
      )}
    </div>
  )
}
