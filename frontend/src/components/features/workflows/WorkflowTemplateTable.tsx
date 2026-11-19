import { useState, useMemo } from 'react'
import type { WorkflowTemplate } from '@/types/workflows'
import WorkflowTemplateTableHeader from './WorkflowTemplateTableHeader'
import WorkflowTemplateTableRow from './WorkflowTemplateTableRow'
import WorkflowTemplateTableFilters from './WorkflowTemplateTableFilters'
import WorkflowTablePagination from './WorkflowTablePagination'

interface WorkflowTemplateTableProps {
  templates: WorkflowTemplate[]
  selectedTemplateId?: string
  onSelect: (template: WorkflowTemplate) => void
  onEdit: (template: WorkflowTemplate) => void
  onExecute: (templateId: string) => void
  onReset?: (templateId: string) => void
  onDelete?: (template: WorkflowTemplate) => Promise<void>
  isLoading?: boolean
  tags?: string[]
  filterTags?: string[]
  onFilterTagsChange?: (tags: string[]) => void
}

export type SortColumn = 'name' | 'category' | 'workflow_type' | 'version' | 'updated_at' | 'tags'
export type SortDirection = 'asc' | 'desc'

const MONITOR_TEMPLATE_IDS = new Set(['rss-monitor', 'market-watch']);

function isMonitorTemplate(tpl: WorkflowTemplate): boolean {
  return MONITOR_TEMPLATE_IDS.has(tpl.id) || (tpl.tags || []).includes('monitor');
}

interface State {
  sortColumn: SortColumn
  sortDirection: SortDirection
  searchQuery: string
  filterCategory: string
  filterType: string
  currentPage: number
  pageSize: number
}

const DEFAULT_STATE: State = {
  sortColumn: 'name',
  sortDirection: 'asc',
  searchQuery: '',
  filterCategory: '',
  filterType: '',
  currentPage: 1,
  pageSize: 25
}

export default function WorkflowTemplateTable({
  templates,
  selectedTemplateId,
  onSelect,
  onEdit,
  onExecute,
  onReset,
  onDelete,
  isLoading = false,
  tags = [],
  filterTags = [],
  onFilterTagsChange
}: WorkflowTemplateTableProps) {
  const [state, setState] = useState<State>(DEFAULT_STATE)

  // Extract unique categories and types from templates
  const categories = useMemo(() => {
    const cats = new Set(templates.map(t => t.category).filter(Boolean))
    return Array.from(cats).sort()
  }, [templates])

  const types = useMemo(() => {
    const ts = new Set(templates.map(t => t.workflowType || 'simple').filter(Boolean))
    return Array.from(ts).sort()
  }, [templates])

  // Filter and sort
  const filteredAndSorted = useMemo(() => {
    let result = [...templates]

    // Search
    if (state.searchQuery.trim()) {
      const query = state.searchQuery.toLowerCase().trim()
      result = result.filter(t =>
        t.name.toLowerCase().includes(query) ||
        t.description.toLowerCase().includes(query) ||
        t.tags.some(tag => tag.toLowerCase().includes(query))
      )
    }

    // Category filter
    if (state.filterCategory) {
      result = result.filter(t => t.category === state.filterCategory)
    }

    // Type filter
    if (state.filterType) {
      result = result.filter(t => (t.workflowType || 'simple') === state.filterType)
    }

    // Tag filter
    if (filterTags.length > 0) {
      result = result.filter(t => t.tags.some(tag => filterTags.includes(tag)))
    }

    // Sort
    result.sort((a, b) => {
      let aVal: string | number
      let bVal: string | number

      switch (state.sortColumn) {
        case 'name':
          aVal = a.name.toLowerCase()
          bVal = b.name.toLowerCase()
          break
        case 'category':
          aVal = a.category.toLowerCase()
          bVal = b.category.toLowerCase()
          break
        case 'workflow_type':
          aVal = (a.workflowType || 'simple').toLowerCase()
          bVal = (b.workflowType || 'simple').toLowerCase()
          break
        case 'version':
          aVal = a.version
          bVal = b.version
          break
        case 'updated_at':
          aVal = new Date(a.updatedAt || a.createdAt).getTime()
          bVal = new Date(b.updatedAt || b.createdAt).getTime()
          break
        case 'tags':
          aVal = a.tags.length
          bVal = b.tags.length
          break
        default:
          aVal = a.name.toLowerCase()
          bVal = b.name.toLowerCase()
      }

      if (aVal < bVal) return state.sortDirection === 'asc' ? -1 : 1
      if (aVal > bVal) return state.sortDirection === 'asc' ? 1 : -1
      return 0
    })

    return result
  }, [templates, state.searchQuery, state.filterCategory, state.filterType, filterTags, state.sortColumn, state.sortDirection])

  // Pagination
  const paginated = useMemo(() => {
    const start = (state.currentPage - 1) * state.pageSize
    return filteredAndSorted.slice(start, start + state.pageSize)
  }, [filteredAndSorted, state.currentPage, state.pageSize])

  const handleSort = (column: SortColumn) => {
    setState(prev => ({
      ...prev,
      sortColumn: column,
      sortDirection: prev.sortColumn === column && prev.sortDirection === 'asc' ? 'desc' : 'asc'
    }))
  }

  const handleSearch = (query: string) => {
    setState(prev => ({ ...prev, searchQuery: query, currentPage: 1 }))
  }

  const handleCategoryFilter = (category: string) => {
    setState(prev => ({ ...prev, filterCategory: category, currentPage: 1 }))
  }

  const handleTypeFilter = (type: string) => {
    setState(prev => ({ ...prev, filterType: type, currentPage: 1 }))
  }

  const handlePageChange = (page: number) => {
    setState(prev => ({ ...prev, currentPage: page }))
  }

  const handlePageSizeChange = (pageSize: number) => {
    setState(prev => ({ ...prev, pageSize, currentPage: 1 }))
  }

  const clearFilters = () => {
    setState(prev => ({
      ...prev,
      searchQuery: '',
      filterCategory: '',
      filterType: '',
      currentPage: 1
    }))
    onFilterTagsChange?.([])
  }

  const hasActiveFilters = !!(state.searchQuery || state.filterCategory || state.filterType || filterTags.length > 0)

  return (
    <div className="w-full bg-base-100 border border-base-300 rounded-lg flex flex-col h-full">
      {/* Filters */}
      <WorkflowTemplateTableFilters
        searchQuery={state.searchQuery}
        categories={categories}
        types={types}
        tags={tags}
        filterTags={filterTags}
        filterCategory={state.filterCategory}
        filterType={state.filterType}
        onSearch={handleSearch}
        onCategoryFilter={handleCategoryFilter}
        onTypeFilter={handleTypeFilter}
        onFilterTagsChange={onFilterTagsChange || (() => {})}
        onClear={clearFilters}
        hasActiveFilters={hasActiveFilters}
      />

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="table table-zebra w-full">
          <thead className="bg-base-200 sticky top-0 z-10">
            <WorkflowTemplateTableHeader
              sortColumn={state.sortColumn}
              sortDirection={state.sortDirection}
              onSort={handleSort}
            />
          </thead>
          <tbody>
            {paginated.length === 0 ? (
              <tr>
                <td colSpan={7} className="text-center py-8 text-readout">
                  {templates.length === 0 ? (
                    <div>
                      <p className="text-sm">No templates yet</p>
                      <p className="text-xs mt-2">Create one to get started</p>
                    </div>
                  ) : (
                    <p className="text-sm">No templates match your filters</p>
                  )}
                </td>
              </tr>
            ) : (
              paginated.map(tpl => (
                <WorkflowTemplateTableRow
                  key={tpl.id}
                  template={tpl}
                  isSelected={selectedTemplateId === tpl.id}
                  onSelect={() => onSelect(tpl)}
                  onEdit={() => onEdit(tpl)}
                  onExecute={() => onExecute(tpl.id)}
                  onReset={onReset && isMonitorTemplate(tpl) ? () => onReset(tpl.id) : undefined}
                  onDelete={onDelete ? () => onDelete(tpl) : undefined}
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
        totalItems={filteredAndSorted.length}
        onPageChange={handlePageChange}
        onPageSizeChange={handlePageSizeChange}
      />
    </div>
  )
}
