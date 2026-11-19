// import React from 'react'
import type { SortColumn, SortDirection } from './ToolsTable'

interface ToolsTableHeaderProps {
  sortColumn: SortColumn
  sortDirection: SortDirection
  allSelected: boolean
  onSort: (column: SortColumn) => void
  onSelectAll: () => void
}

export default function ToolsTableHeader({
  sortColumn,
  sortDirection,
  allSelected,
  onSort,
  onSelectAll
}: ToolsTableHeaderProps) {
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
      {/* Select All Checkbox */}
      <th className="w-12">
        <label className="flex items-center justify-center cursor-pointer">
          <input
            type="checkbox"
            checked={allSelected}
            onChange={onSelectAll}
            className="checkbox checkbox-sm checkbox-primary"
          />
        </label>
      </th>

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

      {/* Type Column */}
      <th
        className="cursor-pointer group hover:bg-base-300 transition-colors"
        onClick={() => handleSortClick('type')}
      >
        <div className="flex items-center gap-2">
          Type
          <span className="text-xs">{renderSortIcon('type')}</span>
        </div>
      </th>

      {/* Capability Column (Phase A) */}
      <th
        className="cursor-pointer group hover:bg-base-300 transition-colors"
        onClick={() => handleSortClick('capability')}
      >
        <div className="flex items-center gap-2">
          Capability
          <span className="text-xs">{renderSortIcon('capability')}</span>
        </div>
      </th>

      {/* Status Column */}
      <th
        className="cursor-pointer group hover:bg-base-300 transition-colors"
        onClick={() => handleSortClick('status')}
      >
        <div className="flex items-center gap-2">
          Status
          <span className="text-xs">{renderSortIcon('status')}</span>
        </div>
      </th>

      {/* Access Column — the tool's registry tier (keyed vs GRAS) */}
      <th>
        <div className="flex items-center gap-2">
          Access
        </div>
      </th>

      {/* Actions Column */}
      <th className="w-20">Actions</th>
    </tr>
  )
}
