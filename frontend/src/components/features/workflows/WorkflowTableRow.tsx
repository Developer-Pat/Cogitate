import type { WorkflowList } from '@/types/workflows'
import WorkflowTableActions from './WorkflowTableActions'

interface WorkflowTableRowProps {
  list: WorkflowList
  isSelected: boolean
  onSelect: () => void
  onEdit: () => void
  onDelete: () => Promise<void>
  isLoading: boolean
}

export default function WorkflowTableRow({
  list,
  isSelected,
  onSelect,
  onEdit,
  onDelete,
  isLoading
}: WorkflowTableRowProps) {

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  return (
    <tr
      className={`hover:bg-base-200 transition-colors ${
        isSelected ? 'bg-primary/10' : ''
      }`}
    >
      {/* Name */}
      <td>
        <button
          onClick={onSelect}
          className="flex items-center gap-3 text-left hover:bg-base-200 p-2 rounded -ml-2"
        >
          <div className="flex-1 min-w-0">
            <div className="font-medium text-sm truncate">{list.name}</div>
            {list.description && (
              <div className="text-xs text-readout truncate max-w-xs">
                {list.description}
              </div>
            )}
          </div>
        </button>
      </td>

      {/* Description - Show on larger screens */}
      <td className="hidden lg:table-cell">
        <div className="text-sm truncate max-w-xs text-readout">
          {list.description || <span className="text-readout">—</span>}
        </div>
      </td>

      {/* Workflow Count */}
      <td>
        <div className="badge badge-ghost badge-sm">
          {list.workflow_count} {list.workflow_count === 1 ? 'workflow' : 'workflows'}
        </div>
      </td>

      {/* Tags */}
      <td className="hidden md:table-cell">
        <div className="flex flex-wrap gap-1 max-w-[200px]">
          {list.tags && list.tags.length > 0 ? (
            list.tags.slice(0, 3).map((tag) => (
              <div key={tag} className="badge badge-primary badge-xs">
                {tag}
              </div>
            ))
          ) : (
            <span className="text-readout text-sm">—</span>
          )}
          {list.tags && list.tags.length > 3 && (
            <span className="text-xs text-readout">
              +{list.tags.length - 3}
            </span>
          )}
        </div>
      </td>

      {/* Updated At */}
      <td className="hidden xl:table-cell">
        <div className="text-xs text-readout">
          {formatDate(list.updated_at)}
        </div>
      </td>

      {/* Actions */}
      <td>
        <WorkflowTableActions
            list={list}
            onEdit={onEdit}
            onDelete={onDelete}
            isLoading={isLoading}
          />
      </td>
    </tr>
  )
}
