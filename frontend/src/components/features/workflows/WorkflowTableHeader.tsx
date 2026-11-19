import type { SortColumn, SortDirection } from './WorkflowTable'

interface WorkflowTableHeaderProps {
  sortColumn: SortColumn
  sortDirection: SortDirection
  onSort: (column: SortColumn) => void
}

export default function WorkflowTableHeader({
  sortColumn,
  sortDirection,
  onSort
}: WorkflowTableHeaderProps) {
  const renderSortIcon = (column: SortColumn) => {
    if (sortColumn !== column) {
      return <span className="opacity-0 group-hover:opacity-30">↕</span>
    }
    return sortDirection === 'asc' ? <span>↑</span> : <span>↓</span>
  }

  const handleSortClick = (column: SortColumn) => {
    onSort(column)
  }

  return (
    <tr>
      {/* Name Column */}
      <th
        className="cursor-pointer group hover:bg-base-300 transition-colors"
        onClick={() => handleSortClick('name')}
      >
        <div className="flex items-center gap-2">
          Name
          <span className="text-xs">{renderSortIcon('name')}</span>
        </div>
      </th>

      {/* Description Column */}
      <th className="hidden lg:table-cell">
        Description
      </th>

      {/* Workflow Count Column */}
      <th
        className="cursor-pointer group hover:bg-base-300 transition-colors"
        onClick={() => handleSortClick('workflow_count')}
      >
        <div className="flex items-center gap-2">
          Workflows
          <span className="text-xs">{renderSortIcon('workflow_count')}</span>
        </div>
      </th>

      {/* Tags Column */}
      <th className="hidden md:table-cell">
        Tags
      </th>

      {/* Updated At Column */}
      <th
        className="cursor-pointer group hover:bg-base-300 transition-colors hidden xl:table-cell"
        onClick={() => handleSortClick('updated_at')}
      >
        <div className="flex items-center gap-2">
          Updated
          <span className="text-xs">{renderSortIcon('updated_at')}</span>
        </div>
      </th>

      {/* Actions Column */}
      <th className="w-24">Actions</th>
    </tr>
  )
}
