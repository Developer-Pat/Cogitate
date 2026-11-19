import { useState } from 'react'
import type { Tool } from '@/types/tools'
import { useNotificationStore } from '@/stores/notificationStore'

import { AddToCollectionModal } from '../features/collections/AddToCollectionModal'
import { ToolPermissionsManager } from './ToolPermissionsManager'

interface ToolsTableActionsProps {
  tool: Tool
  onDuplicate: () => void
  isLoading: boolean
}

export default function ToolsTableActions({
  tool,
  onDuplicate,
  isLoading
}: ToolsTableActionsProps) {
  const [, setShowActions] = useState(false);
  const [showAddToCollection, setShowAddToCollection] = useState(false)
  const [showPermissionsManager, setShowPermissionsManager] = useState(false)
  const addNotification = useNotificationStore((state) => state.addNotification)

  const handleAddToCollection = () => {
    setShowAddToCollection(true)
  }

  const handleManagePermissions = () => {
    setShowPermissionsManager(true)
  }

  const handleAddedToCollections = () => {
    addNotification({
      type: 'success',
      title: 'Added to Collection',
      message: `"${tool.name}" has been added to the collection`
    })
    setShowAddToCollection(false)
  }

  const handlePermissionsUpdated = () => {
    // Trigger a refresh in the parent component if needed
    setShowPermissionsManager(false)
  }

  return (
    <>
      <div className="dropdown dropdown-end">
        <div className="tooltip tooltip-left" data-tip="Actions">
          <label
            tabIndex={0}
            className="btn btn-ghost btn-xs btn-square"
            onMouseEnter={() => setShowActions(true)}
            onMouseLeave={() => setShowActions(false)}
          >
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 8c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 2c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0 6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z" />
            </svg>
          </label>
        </div>
        <ul
          tabIndex={0}
          className="dropdown-content z-[1] menu p-2 shadow bg-base-100 rounded-box w-52"
          onMouseEnter={() => setShowActions(true)}
          onMouseLeave={() => setShowActions(false)}
        >
          <li>
            <button
              onClick={handleManagePermissions}
              className="text-secondary"
            >
              Manage Permissions
            </button>
          </li>
          <li>
            <button
              onClick={handleAddToCollection}
              className="text-primary"
            >
              Add to Collection
            </button>
          </li>
          <li>
            <button
              onClick={onDuplicate}
              disabled={isLoading}
            >
              Duplicate
            </button>
          </li>
          <li>
            <button className="text-error">
              Delete
            </button>
          </li>
        </ul>
      </div>

      {showAddToCollection && (
        <AddToCollectionModal
          entityId={tool.id}
          entityName={tool.name}
          entityType="tool"
          onClose={() => setShowAddToCollection(false)}
          onAdded={handleAddedToCollections}
        />
      )}

      {showPermissionsManager && (
        <ToolPermissionsManager
          toolId={tool.id}
          toolName={tool.name}
          onClose={() => setShowPermissionsManager(false)}
          onPermissionsUpdated={handlePermissionsUpdated}
        />
      )}
    </>
  )
}
