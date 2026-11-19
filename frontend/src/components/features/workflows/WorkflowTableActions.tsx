import type { WorkflowList } from '@/types/workflows'

interface WorkflowTableActionsProps {
  list: WorkflowList
  onEdit: () => void
  onDelete: () => Promise<void>
  isLoading: boolean
}

export default function WorkflowTableActions({
  list,
  onEdit,
  onDelete,
  isLoading
}: WorkflowTableActionsProps) {
  const handleDelete = async () => {
    if (confirm(`Are you sure you want to delete "${list.name}"?`)) {
      await onDelete()
    }
  }

  return (
    <div className="flex items-center gap-2 justify-end">
      {/* Edit Button */}
      <span className="tooltip tooltip-top" data-tip="Edit workflow list">
      <button
        onClick={onEdit}
        className="btn btn-ghost btn-xs"
        disabled={isLoading}
        aria-label="Edit workflow list"
      >
        <svg
          className="w-4 h-4"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
          />
        </svg>
      </button>
      </span>

      {/* Delete Button */}
      <span className="tooltip tooltip-top" data-tip="Delete workflow list">
      <button
        onClick={handleDelete}
        className="btn btn-ghost btn-xs text-error hover:bg-error/10"
        disabled={isLoading}
        aria-label="Delete workflow list"
      >
        <svg
          className="w-4 h-4"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
          />
        </svg>
      </button>
      </span>
    </div>
  )
}
