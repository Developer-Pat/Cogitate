import { useState } from 'react'
import type { Profile } from '@/services/domain/ProfileService'
import { useNotificationStore } from '@/stores/notificationStore'

import { AddToCollectionModal } from '../features/collections/AddToCollectionModal'

interface AgentTableActionsProps {
  profile: Profile
  onDuplicate: () => void
  isLoading: boolean
  onManageTools?: (agentId: string) => void
}

export default function AgentTableActions({
  profile,
  onDuplicate,
  isLoading,
  onManageTools
}: AgentTableActionsProps) {
  const [, setShowActions] = useState(false);
  const [showAddToCollection, setShowAddToCollection] = useState(false)
  const addNotification = useNotificationStore((state) => state.addNotification)

  const handleAddToCollection = () => {
    setShowAddToCollection(true)
  }

  const handleAddedToCollections = () => {
    addNotification({
      type: 'success',
      title: 'Added to Collection',
      message: `"${profile.name}" has been added to the collection`
    })
    setShowAddToCollection(false)
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
              onClick={handleAddToCollection}
              className="text-primary"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
              </svg>
              Add to Collection
            </button>
          </li>
          {onManageTools && (
            <li>
              <button
                onClick={() => onManageTools(profile.id)}
                className="text-info"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                Manage Tools
              </button>
            </li>
          )}
          <li>
            <button
              onClick={onDuplicate}
              disabled={isLoading}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
              Duplicate
            </button>
          </li>
          <li>
            <button className="text-error">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
              Delete
            </button>
          </li>
        </ul>
      </div>

      {/* Add to Collection Modal */}
      {showAddToCollection && (
        <AddToCollectionModal
          entityId={profile.id}
          entityName={profile.name}
          entityType="agent"
          onClose={() => setShowAddToCollection(false)}
          onAdded={handleAddedToCollections}
        />
      )}
    </>
  )
}
