// import React from 'react'

interface AgentTableBulkActionsProps {
  selectedCount: number
  onBulkDelete: () => Promise<void>
  onClearSelection: () => void
}

export default function AgentTableBulkActions({
  selectedCount,
  onBulkDelete,
  onClearSelection
}: AgentTableBulkActionsProps) {
  const handleDelete = async () => {
    const confirmed = confirm(
      `Are you sure you want to delete ${selectedCount} agent(s)? This action cannot be undone.`
    )
    if (confirmed) {
      await onBulkDelete()
    }
  }

  return (
    <div className="px-4 py-3 bg-primary/10 border-b border-base-300 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <span className="font-medium text-primary">
          {selectedCount} agent{selectedCount > 1 ? 's' : ''} selected
        </span>
        <button
          className="btn btn-ghost btn-xs"
          onClick={onClearSelection}
        >
          Clear selection
        </button>
      </div>

      <div className="flex items-center gap-2">
        {/* Bulk Add to Collection - Future enhancement */}
        {/* <button className="btn btn-ghost btn-sm gap-2">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
          </svg>
          Add to Collection
        </button> */}

        {/* Bulk Delete */}
        <button
          className="btn btn-error btn-sm gap-2 text-white"
          onClick={handleDelete}
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
          Delete {selectedCount}
        </button>
      </div>
    </div>
  )
}
