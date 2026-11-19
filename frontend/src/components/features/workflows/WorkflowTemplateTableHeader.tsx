import type { SortColumn, SortDirection } from './WorkflowTemplateTable'

interface Props {
  sortColumn: SortColumn
  sortDirection: SortDirection
  onSort: (column: SortColumn) => void
}

const COLUMNS: { key: SortColumn; label: string }[] = [
  { key: 'name', label: 'Name' },
  { key: 'category', label: 'Category' },
  { key: 'workflow_type', label: 'Type' },
  { key: 'version', label: 'Version' },
  { key: 'tags', label: 'Tags' },
  { key: 'updated_at', label: 'Updated' },
]

function SortIcon({ column, activeColumn, direction }: { column: SortColumn; activeColumn: SortColumn; direction: SortDirection }) {
  if (column !== activeColumn) {
    return <span className="opacity-30 ml-1">↕</span>
  }
  return <span className="ml-1">{direction === 'asc' ? '↑' : '↓'}</span>
}

export default function WorkflowTemplateTableHeader({ sortColumn, sortDirection, onSort }: Props) {
  return (
    <tr>
      {COLUMNS.map(col => (
        <th
          key={col.key}
          className="cursor-pointer select-none hover:bg-base-300"
          onClick={() => onSort(col.key)}
        >
          <span className="flex items-center">
            {col.label}
            <SortIcon column={col.key} activeColumn={sortColumn} direction={sortDirection} />
          </span>
        </th>
      ))}
      <th className="w-32">Actions</th>
    </tr>
  )
}
