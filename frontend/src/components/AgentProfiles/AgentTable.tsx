import { useState, useMemo } from 'react'
import type { Profile } from '@/services/domain/ProfileService'
import type { Collection } from '@/types/collections'
import AgentTableHeader from './AgentTableHeader'
import AgentTableRow from './AgentTableRow'
import AgentTableFilters from './AgentTableFilters'
import AgentTablePagination from './AgentTablePagination'
import AgentTableBulkActions from './AgentTableBulkActions'

interface AgentTableProps {
  profiles: Profile[]
  selectedProfileId?: string
  onSelectProfile: (profile: Profile) => void
  onDuplicate: (profile: Profile) => void
  onDelete: (profileId: string) => Promise<Record<string, unknown> | null>
  isLoading?: boolean
  onViewModeChange?: (mode: 'list' | 'table') => void
  onManageTools?: (agentId: string) => void
  // Team filtering props
  teams?: Collection[]
  selectedTeamId?: string | 'all'
  onTeamChange?: (teamId: string | 'all') => void
  loadingTeams?: boolean
  totalProfiles?: number
}

export type SortColumn = 'name' | 'provider' | 'model' | 'status'
export type SortDirection = 'asc' | 'desc'

interface AgentTableState {
  // Sorting
  sortColumn: SortColumn
  sortDirection: SortDirection

  // Filtering
  searchQuery: string
  providerFilter: string[]
  statusFilter: 'all' | 'active' | 'inactive'

  // Pagination
  currentPage: number
  pageSize: number

  // Selection
  selectedAgentIds: Set<string>
}

const DEFAULT_STATE: AgentTableState = {
  sortColumn: 'name',
  sortDirection: 'asc',
  searchQuery: '',
  providerFilter: [],
  statusFilter: 'all',
  currentPage: 1,
  pageSize: 25,
  selectedAgentIds: new Set()
}

export default function AgentTable({
  profiles,
  selectedProfileId,
  onSelectProfile,
  onDuplicate,
  onDelete,
  isLoading = false,
  onViewModeChange,
  onManageTools,
  teams = [],
  selectedTeamId = 'all',
  onTeamChange,
  loadingTeams = false,
  totalProfiles = 0
}: AgentTableProps) {
  const [state, setState] = useState<AgentTableState>(DEFAULT_STATE)

  // Extract unique providers for filter dropdown
  const providers = useMemo(() => {
    return Array.from(new Set(profiles.map(p => p.provider))).sort()
  }, [profiles])

  // Filter and sort profiles
  const filteredAndSortedProfiles = useMemo(() => {
    let result = [...profiles]

    // Apply search filter
    if (state.searchQuery.trim()) {
      const query = state.searchQuery.toLowerCase().trim()
      result = result.filter(
        profile =>
          profile.name.toLowerCase().includes(query) ||
          profile.description.toLowerCase().includes(query)
      )
    }

    // Apply provider filter
    if (state.providerFilter.length > 0) {
      result = result.filter(profile =>
        state.providerFilter.includes(profile.provider)
      )
    }

    // Apply status filter (all profiles are considered active for now)
    if (state.statusFilter === 'active') {
      // All profiles are active by default
      // Could add is_active field filtering if needed
    } else if (state.statusFilter === 'inactive') {
      // No inactive profiles for now
      result = []
    }

    // Apply sorting
    result.sort((a, b) => {
      let aValue: string
      let bValue: string

      switch (state.sortColumn) {
        case 'name':
          aValue = a.name.toLowerCase()
          bValue = b.name.toLowerCase()
          break
        case 'provider':
          aValue = a.provider.toLowerCase()
          bValue = b.provider.toLowerCase()
          break
        case 'model':
          aValue = a.model.toLowerCase()
          bValue = b.model.toLowerCase()
          break
        case 'status':
          // All are active, so sort alphabetically
          aValue = 'active'
          bValue = 'active'
          break
        default:
          aValue = a.name.toLowerCase()
          bValue = b.name.toLowerCase()
      }

      if (aValue < bValue) return state.sortDirection === 'asc' ? -1 : 1
      if (aValue > bValue) return state.sortDirection === 'asc' ? 1 : -1
      return 0
    })

    return result
  }, [profiles, state.searchQuery, state.providerFilter, state.statusFilter, state.sortColumn, state.sortDirection])

  // Apply pagination
  const paginatedProfiles = useMemo(() => {
    const startIndex = (state.currentPage - 1) * state.pageSize
    const endIndex = startIndex + state.pageSize
    return filteredAndSortedProfiles.slice(startIndex, endIndex)
  }, [filteredAndSortedProfiles, state.currentPage, state.pageSize])

  // Handle sorting
  const handleSort = (column: SortColumn) => {
    setState(prev => ({
      ...prev,
      sortColumn: column,
      sortDirection: prev.sortColumn === column && prev.sortDirection === 'asc' ? 'desc' : 'asc'
    }))
  }

  // Handle search
  const handleSearch = (query: string) => {
    setState(prev => ({
      ...prev,
      searchQuery: query,
      currentPage: 1 // Reset to first page when searching
    }))
  }

  // Handle provider filter
  const handleProviderFilter = (providers: string[]) => {
    setState(prev => ({
      ...prev,
      providerFilter: providers,
      currentPage: 1
    }))
  }

  // Handle status filter
  const handleStatusFilter = (status: 'all' | 'active' | 'inactive') => {
    setState(prev => ({
      ...prev,
      statusFilter: status,
      currentPage: 1
    }))
  }

  // Handle page change
  const handlePageChange = (page: number) => {
    setState(prev => ({ ...prev, currentPage: page }))
  }

  // Handle page size change
  const handlePageSizeChange = (pageSize: number) => {
    setState(prev => ({
      ...prev,
      pageSize,
      currentPage: 1
    }))
  }

  // Handle select single agent
  const handleSelectAgent = (agentId: string) => {
    setState(prev => {
      const newSelected = new Set(prev.selectedAgentIds)
      if (newSelected.has(agentId)) {
        newSelected.delete(agentId)
      } else {
        newSelected.add(agentId)
      }
      return { ...prev, selectedAgentIds: newSelected }
    })
  }

  // Handle select all
  const handleSelectAll = () => {
    if (state.selectedAgentIds.size === paginatedProfiles.length) {
      // Deselect all
      setState(prev => ({ ...prev, selectedAgentIds: new Set() }))
    } else {
      // Select all on current page
      const newSelected = new Set<string>()
      paginatedProfiles.forEach(p => newSelected.add(p.id))
      setState(prev => ({ ...prev, selectedAgentIds: newSelected }))
    }
  }

  // Handle bulk delete
  const handleBulkDelete = async () => {
    const deletePromises = Array.from(state.selectedAgentIds).map(id => onDelete(id))
    await Promise.all(deletePromises)
    setState(prev => ({ ...prev, selectedAgentIds: new Set() }))
  }

  // Check if all on current page are selected
  const allSelected = paginatedProfiles.length > 0 &&
    paginatedProfiles.every(p => state.selectedAgentIds.has(p.id))

  return (
    <div className="w-[600px] bg-base-100 border-l border-base-300 flex flex-col h-full">
      {/* Header with View Toggle */}
      <div className="p-4 border-b border-base-300">
        <div className="flex justify-end">
          <div className="btn-group">
            <div className="tooltip tooltip-left" data-tip="Switch to List view">
              <button
                className="btn btn-sm btn-ghost"
                onClick={() => onViewModeChange?.('list')}
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              </button>
            </div>
            <div className="tooltip tooltip-left" data-tip="Table view (active)">
              <button
                className="btn btn-sm btn-active"
                disabled
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              </button>
            </div>
          </div>
        </div>
        
        {/* Team Filter Dropdown */}
        {onTeamChange && (
          <div className="mt-3">
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

      {/* Filters */}
      <AgentTableFilters
        searchQuery={state.searchQuery}
        providers={providers}
        providerFilter={state.providerFilter}
        statusFilter={state.statusFilter}
        onSearch={handleSearch}
        onProviderFilter={handleProviderFilter}
        onStatusFilter={handleStatusFilter}
      />

      {/* Bulk Actions */}
      {state.selectedAgentIds.size > 0 && (
        <AgentTableBulkActions
          selectedCount={state.selectedAgentIds.size}
          onBulkDelete={handleBulkDelete}
          onClearSelection={() => setState(prev => ({ ...prev, selectedAgentIds: new Set() }))}
        />
      )}

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="table table-zebra w-full">
          <thead className="bg-base-200 sticky top-0 z-10">
            <AgentTableHeader
              sortColumn={state.sortColumn}
              sortDirection={state.sortDirection}
              allSelected={allSelected}
              onSort={handleSort}
              onSelectAll={handleSelectAll}
            />
          </thead>
          <tbody>
            {paginatedProfiles.length === 0 ? (
              <tr>
                <td colSpan={4} className="text-center py-8 text-readout">
                  {profiles.length === 0 ? (
                    <div>
                      <p className="text-sm">No agents yet</p>
                      <p className="text-xs mt-2">Create one to get started</p>
                    </div>
                  ) : (
                    <p className="text-sm">No agents match your filters</p>
                  )}
                </td>
              </tr>
            ) : (
              paginatedProfiles.map(profile => (
                <AgentTableRow
                  key={profile.id}
                  profile={profile}
                  isSelected={state.selectedAgentIds.has(profile.id)}
                  isRowSelected={selectedProfileId === profile.id}
                  onSelect={() => handleSelectAgent(profile.id)}
                  onSelectProfile={() => onSelectProfile(profile)}
                  onDuplicate={() => onDuplicate(profile)}
                  isLoading={isLoading}
                  onManageTools={onManageTools}
                />
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <AgentTablePagination
        currentPage={state.currentPage}
        pageSize={state.pageSize}
        totalItems={filteredAndSortedProfiles.length}
        onPageChange={handlePageChange}
        onPageSizeChange={handlePageSizeChange}
      />
    </div>
  )
}
