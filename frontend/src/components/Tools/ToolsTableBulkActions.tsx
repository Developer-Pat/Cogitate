// import React from 'react'

interface ToolsTableBulkActionsProps {
  selectedCount: number
  onBulkDelete: () => Promise<void>
  onClearSelection: () => void
}

export default function ToolsTableBulkActions({
  selectedCount,
  onBulkDelete,
  onClearSelection
}: ToolsTableBulkActionsProps) {
  const handleDelete = async () => {
    const confirmed = confirm(
      `Are you sure you want to delete ${selectedCount} tool(s)? This action cannot be undone.`
    )
    if (confirmed) {
      await onBulkDelete()
    }
  }

  return (
    <div className="px-4 py-3 bg-primary/10 border-b border-base-300 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <span className="font-medium text-primary">
          {selectedCount} tool{selectedCount > 1 ? 's' : ''} selected
        </span>
        <button
          className="btn btn-outline btn-xs"
          onClick={onClearSelection}
        >
          Clear selection
        </button>
      </div>

      <div className="flex items-center gap-2">
        <button
          className="btn btn-error btn-sm"
          onClick={handleDelete}
        >
          Delete {selectedCount}
        </button>
      </div>
    </div>
  )
}
