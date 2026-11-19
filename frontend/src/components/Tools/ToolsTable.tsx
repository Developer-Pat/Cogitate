import { useState, useMemo } from 'react'
import type { Tool } from '@/types/tools'
import ToolsTableHeader from './ToolsTableHeader'
import ToolsTableRow from './ToolsTableRow'
import ToolsTableFilters from './ToolsTableFilters'
import ToolsTablePagination from './ToolsTablePagination'
import ToolsTableBulkActions from './ToolsTableBulkActions'

interface ToolsTableProps {
  tools: Tool[]
  selectedToolIds?: Set<string>
  onSelectionChange?: (selectedIds: Set<string>) => void
  onDuplicate: (tool: Tool) => void
  onDelete: (toolId: string) => Promise<void>
  isLoading?: boolean
}

export type SortColumn = 'name' | 'type' | 'status' | 'capability'
export type SortDirection = 'asc' | 'desc'

interface ToolsTableState {
  sortColumn: SortColumn
  sortDirection: SortDirection
  searchQuery: string
  typeFilter: string[]
  tagFilter: string[]
  statusFilter: 'all' | 'active' | 'inactive'
  currentPage: number
  pageSize: number
}

const DEFAULT_STATE: ToolsTableState = {
  sortColumn: 'name',
  sortDirection: 'asc',
  searchQuery: '',
  typeFilter: [],
  tagFilter: [],
  statusFilter: 'all',
  currentPage: 1,
  pageSize: 25
}

export default function ToolsTable({
  tools,
  selectedToolIds = new Set(),
  onSelectionChange,
  onDuplicate,
  onDelete,
  isLoading = false
}: ToolsTableProps) {
  const [state, setState] = useState<ToolsTableState>(DEFAULT_STATE)

  // Extract unique types for filter dropdown
  const types = useMemo(() => {
    return Array.from(new Set(tools.map(t => t.type).filter(Boolean))).sort() as string[]
  }, [tools])

  // Filter and sort tools
  const filteredAndSortedTools = useMemo(() => {
    let result = [...tools]

    // Apply search filter
    if (state.searchQuery.trim()) {
      const query = state.searchQuery.toLowerCase().trim()
      result = result.filter(
        tool =>
          tool.name.toLowerCase().includes(query) ||
          tool.description.toLowerCase().includes(query)
      )
    }

    // Apply type filter
    if (state.typeFilter.length > 0) {
      result = result.filter(tool =>
        state.typeFilter.includes(tool.type || '')
      )
    }

    // Apply tag filter
    if (state.tagFilter.length > 0) {
      result = result.filter(tool =>
        tool.tags && state.tagFilter.every(tag => tool.tags?.includes(tag))
      )
    }

    // Apply status filter
    if (state.statusFilter === 'active') {
      result = result.filter(tool => tool.is_active)
    } else if (state.statusFilter === 'inactive') {
      result = result.filter(tool => !tool.is_active)
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
        case 'type':
          aValue = (a.type || '').toLowerCase()
          bValue = (b.type || '').toLowerCase()
          break
        case 'status':
          aValue = a.is_active ? 'active' : 'inactive'
          bValue = b.is_active ? 'active' : 'inactive'
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tools, state.searchQuery, state.typeFilter, state.statusFilter, state.sortColumn, state.sortDirection])

  // Apply pagination
  const paginatedTools = useMemo(() => {
    const startIndex = (state.currentPage - 1) * state.pageSize
    const endIndex = startIndex + state.pageSize
    return filteredAndSortedTools.slice(startIndex, endIndex)
  }, [filteredAndSortedTools, state.currentPage, state.pageSize])

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
      currentPage: 1
    }))
  }

  // Handle type filter
  const handleTypeFilter = (types: string[]) => {
    setState(prev => ({
      ...prev,
      typeFilter: types,
      currentPage: 1
    }))
  }

  // Handle tag filter
  const handleTagFilter = (tags: string[]) => {
    setState(prev => ({
      ...prev,
      tagFilter: tags,
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

  // Handle select single tool
  const handleSelectTool = (toolId: string) => {
    const newSelected = new Set(selectedToolIds)
    if (newSelected.has(toolId)) {
      newSelected.delete(toolId)
    } else {
      newSelected.add(toolId)
    }
    onSelectionChange?.(newSelected)
  }

  // Handle select all
  const handleSelectAll = () => {
    if (selectedToolIds.size === paginatedTools.length) {
      onSelectionChange?.(new Set())
    } else {
      const newSelected = new Set<string>()
      paginatedTools.forEach(t => newSelected.add(t.id))
      onSelectionChange?.(newSelected)
    }
  }

  // Handle bulk delete
  const handleBulkDelete = async () => {
    const deletePromises = Array.from(selectedToolIds).map(id => onDelete(id))
    await Promise.all(deletePromises)
    onSelectionChange?.(new Set())
  }

  // Check if all on current page are selected
  const allSelected = paginatedTools.length > 0 &&
    paginatedTools.every(t => selectedToolIds.has(t.id))

  return (
    <div className="flex-1 bg-base-100 rounded-lg border border-base-300 flex flex-col overflow-hidden">
      {/* Filters */}
      <ToolsTableFilters
        searchQuery={state.searchQuery}
        types={types}
        typeFilter={state.typeFilter}
        tagFilter={state.tagFilter}
        statusFilter={state.statusFilter}
        onSearch={handleSearch}
        onTypeFilter={handleTypeFilter}
        onTagFilter={handleTagFilter}
        onStatusFilter={handleStatusFilter}
      />

      {/* Bulk Actions */}
      {selectedToolIds.size > 0 && (
        <ToolsTableBulkActions
          selectedCount={selectedToolIds.size}
          onBulkDelete={handleBulkDelete}
          onClearSelection={() => onSelectionChange?.(new Set())}
        />
      )}

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="table table-zebra w-full">
          <thead className="bg-base-200 sticky top-0 z-10">
            <ToolsTableHeader
              sortColumn={state.sortColumn}
              sortDirection={state.sortDirection}
              allSelected={allSelected}
              onSort={handleSort}
              onSelectAll={handleSelectAll}
            />
          </thead>
          <tbody>
            {paginatedTools.length === 0 ? (
              <tr>
                <td colSpan={5} className="text-center py-8 text-readout">
                  {tools.length === 0 ? (
                    <div>
                      <p className="text-sm">No tools yet</p>
                      <p className="text-xs mt-2">Create one to get started</p>
                    </div>
                  ) : (
                    <p className="text-sm">No tools match your filters</p>
                  )}
                </td>
              </tr>
            ) : (
              paginatedTools.map(tool => (
                <ToolsTableRow
                  key={tool.id}
                  tool={tool}
                  isSelected={selectedToolIds.has(tool.id)}
                  onSelect={() => handleSelectTool(tool.id)}
                  onDuplicate={() => onDuplicate(tool)}
                  isLoading={isLoading}
                />
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <ToolsTablePagination
        currentPage={state.currentPage}
        pageSize={state.pageSize}
        totalItems={filteredAndSortedTools.length}
        onPageChange={handlePageChange}
        onPageSizeChange={handlePageSizeChange}
      />
    </div>
  )
}
