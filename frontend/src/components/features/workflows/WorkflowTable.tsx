import { useState, useMemo } from 'react'
import type { WorkflowList } from '@/types/workflows'
import WorkflowTableHeader from './WorkflowTableHeader'
import WorkflowTableRow from './WorkflowTableRow'
import WorkflowTableFilters from './WorkflowTableFilters'
import WorkflowTablePagination from './WorkflowTablePagination'

interface WorkflowTableProps {
  workflowLists: WorkflowList[]
  selectedListId?: string
  onSelectList: (list: WorkflowList) => void
  onEdit: (list: WorkflowList) => void
  onDelete: (list: WorkflowList) => Promise<void>
  isLoading?: boolean
  onViewModeChange?: (mode: string) => void
  tags?: string[]
  filterTags?: string[]
  onFilterTagsChange?: (tags: string[]) => void
}

export type SortColumn = 'name' | 'workflow_count' | 'updated_at' | 'tags'
export type SortDirection = 'asc' | 'desc'

interface WorkflowTableState {
  // Sorting
  sortColumn: SortColumn
  sortDirection: SortDirection

  // Filtering
  searchQuery: string

  // Pagination
  currentPage: number
  pageSize: number
}

const DEFAULT_STATE: WorkflowTableState = {
  sortColumn: 'name',
  sortDirection: 'asc',
  searchQuery: '',
  currentPage: 1,
  pageSize: 25
}

export default function WorkflowTable({
  workflowLists,
  selectedListId,
  onSelectList,
  onEdit,
  onDelete,
  isLoading = false,
  onViewModeChange: _onViewModeChange,
  tags = [],
  filterTags = [],
  onFilterTagsChange
}: WorkflowTableProps) {
  const [state, setState] = useState<WorkflowTableState>(DEFAULT_STATE)

  // Filter and sort workflow lists
  const filteredAndSortedLists = useMemo(() => {
    let result = [...workflowLists]

    // Apply search filter
    if (state.searchQuery.trim()) {
      const query = state.searchQuery.toLowerCase().trim()
      result = result.filter(
        list =>
          list.name.toLowerCase().includes(query) ||
          (list.description && list.description.toLowerCase().includes(query))
      )
    }

    // Apply tag filter
    if (filterTags.length > 0) {
      result = result.filter(list =>
        list.tags?.some(tag => filterTags.includes(tag))
      )
    }

    // Apply sorting
    result.sort((a, b) => {
      let aValue: string | number
      let bValue: string | number

      switch (state.sortColumn) {
        case 'name':
          aValue = a.name.toLowerCase()
          bValue = b.name.toLowerCase()
          break
        case 'workflow_count':
          aValue = a.workflow_count
          bValue = b.workflow_count
          break
        case 'updated_at':
          aValue = new Date(a.updated_at).getTime()
          bValue = new Date(b.updated_at).getTime()
          break
        case 'tags':
          aValue = (a.tags?.length || 0)
          bValue = (b.tags?.length || 0)
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
  }, [workflowLists, state.searchQuery, filterTags, state.sortColumn, state.sortDirection])

  // Apply pagination
  const paginatedLists = useMemo(() => {
    const startIndex = (state.currentPage - 1) * state.pageSize
    const endIndex = startIndex + state.pageSize
    return filteredAndSortedLists.slice(startIndex, endIndex)
  }, [filteredAndSortedLists, state.currentPage, state.pageSize])

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

  return (
    <div className="w-full bg-base-100 border border-base-300 rounded-lg flex flex-col h-full">
      {/* Filters */}
      <WorkflowTableFilters
        searchQuery={state.searchQuery}
        tags={tags}
        filterTags={filterTags}
        onSearch={handleSearch}
        onFilterTagsChange={onFilterTagsChange || (() => {})}
      />

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="table table-zebra w-full">
          <thead className="bg-base-200 sticky top-0 z-10">
            <WorkflowTableHeader
              sortColumn={state.sortColumn}
              sortDirection={state.sortDirection}
              onSort={handleSort}
            />
          </thead>
          <tbody>
            {paginatedLists.length === 0 ? (
              <tr>
                <td colSpan={5} className="text-center py-8 text-readout">
                  {workflowLists.length === 0 ? (
                    <div>
                      <p className="text-sm">No workflow lists yet</p>
                      <p className="text-xs mt-2">Create one to get started</p>
                    </div>
                  ) : (
                    <p className="text-sm">No workflow lists match your filters</p>
                  )}
                </td>
              </tr>
            ) : (
              paginatedLists.map(list => (
                <WorkflowTableRow
                  key={list.id}
                  list={list}
                  isSelected={selectedListId === list.id}
                  onSelect={() => onSelectList(list)}
                  onEdit={() => onEdit(list)}
                  onDelete={() => onDelete(list)}
                  isLoading={isLoading}
                />
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <WorkflowTablePagination
        currentPage={state.currentPage}
        pageSize={state.pageSize}
        totalItems={filteredAndSortedLists.length}
        onPageChange={handlePageChange}
        onPageSizeChange={handlePageSizeChange}
      />
    </div>
  )
}
