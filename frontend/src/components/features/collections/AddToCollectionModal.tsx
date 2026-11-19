/**
 * Add to Collection Modal
 *
 * Modal dialog for adding an entity to one or more collections.
 * Integrated with backend API via CollectionsService.
 */

import React, { useState, useMemo, useEffect } from 'react'
import { collectionsService } from '@/services/domain/CollectionsService'
import type { Collection, CollectionEntityType } from '@/types/collections'
import { useNotificationStore } from '@/stores/notificationStore'

interface AddToCollectionModalProps {
  entityId: string
  entityName: string
  entityType: CollectionEntityType
  onClose: () => void
  onAdded: (collectionIds: string[]) => void
}

export const AddToCollectionModal: React.FC<AddToCollectionModalProps> = ({
  entityId,
  entityName,
  entityType,
  onClose,
  onAdded,
}) => {
  const [collections, setCollections] = useState<Collection[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [selectedCollectionIds, setSelectedCollectionIds] = useState<string[]>([])
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [newCollectionName, setNewCollectionName] = useState('')

  // Load collections from backend
  useEffect(() => {
    const loadCollections = async () => {
      try {
        setIsLoading(true)
        const response = await collectionsService.listCollections({ entity_type: entityType })
        setCollections(response.collections)
      } catch (error) {
        console.error('Failed to load collections:', error)
        setCollections([])
      } finally {
        setIsLoading(false)
      }
    }
    loadCollections()
  }, [entityType])

  // Get collections that already contain this entity
  const collectionsWithEntity = useMemo(
    () => collections.filter(c =>
      c.items.some(item => item.entity_id === entityId && item.entity_type === entityType)
    ),
    [collections, entityId, entityType]
  )

  // Collections available to add to (not already containing this entity)
  const availableCollections = useMemo(
    () => collections.filter(c =>
      !c.items.some(item => item.entity_id === entityId && item.entity_type === entityType)
    ),
    [collections, entityId, entityType]
  )

  const handleToggleCollection = (collectionId: string) => {
    setSelectedCollectionIds(prev =>
      prev.includes(collectionId)
        ? prev.filter(id => id !== collectionId)
        : [...prev, collectionId]
    )
  }

  const handleSave = async () => {
    try {
      // Add entity to selected collections
      for (const collectionId of selectedCollectionIds) {
        await collectionsService.addItemToCollection(collectionId, {
          entity_id: entityId,
          entity_type: entityType,
          entity_name: entityName,
        })
      }
      useNotificationStore.getState().addSuccess(
        'Added to Collection',
        `Added to ${selectedCollectionIds.length} collection${selectedCollectionIds.length !== 1 ? 's' : ''}`
      )
      onAdded(selectedCollectionIds)
    } catch (error) {
      console.error('Failed to add to collections:', error)
      useNotificationStore.getState().addError(
        'Failed to Add',
        'Could not add to collection. Please try again.'
      )
    }
  }

  const handleCreateCollection = () => {
    if (!newCollectionName.trim()) return
    // For now, just close the modal - creation handled elsewhere
    onClose()
  }

  if (isLoading) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9999]">
        <div className="bg-base-200 rounded-lg shadow-xl p-6">
          <span className="loading loading-lg"></span>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9999]">
      <div className="bg-base-200 rounded-lg shadow-xl w-[var(--dialog-width-md)] max-w-[var(--dialog-width-full)] mx-4 max-h-[80vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-base-300">
          <div>
            <h2 className="text-2xl font-bold text-base-content">Add to Collection</h2>
            <p className="text-sm text-readout mt-1">
              Add "{entityName}" to one or more collections
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-base-content/50 hover:text-base-content/70"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Collections with entity */}
          {collectionsWithEntity.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-base-content mb-2">
                Already in these collections:
              </h3>
              <div className="space-y-2">
                {collectionsWithEntity.map(collection => (
                  <div
                    key={collection.id}
                    className="flex items-center gap-3 p-3 rounded bg-base-300"
                  >
                    <svg className="w-5 h-5 text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    <span className="text-base-content">{collection.name}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Available collections */}
          {availableCollections.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-base-content mb-2">
                Add to collections:
              </h3>
              <div className="space-y-2 max-h-60 overflow-y-auto">
                {availableCollections.map(collection => (
                  <label
                    key={collection.id}
                    className="flex items-center gap-3 p-3 rounded hover:bg-base-300 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={selectedCollectionIds.includes(collection.id)}
                      onChange={() => handleToggleCollection(collection.id)}
                      className="checkbox checkbox-sm checkbox-primary"
                    />
                    <span className="text-base-content">{collection.name}</span>
                  </label>
                ))}
              </div>
            </div>
          )}

          {/* Create new collection */}
          {!showCreateForm ? (
            <button
              onClick={() => setShowCreateForm(true)}
              className="btn btn-outline btn-sm"
            >
              Create new collection
            </button>
          ) : (
            <div className="p-4 border border-base-300 rounded">
              <input
                type="text"
                value={newCollectionName}
                onChange={(e) => setNewCollectionName(e.target.value)}
                placeholder="Enter collection name"
                className="input input-bordered w-full mb-2"
                autoFocus
              />
              <div className="flex gap-2">
                <button
                  onClick={handleCreateCollection}
                  className="btn btn-primary btn-sm"
                  disabled={!newCollectionName.trim()}
                >
                  Create
                </button>
                <button
                  onClick={() => {
                    setShowCreateForm(false)
                    setNewCollectionName('')
                  }}
                  className="btn btn-neutral btn-ghost btn-sm"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {/* Empty state */}
          {collections.length === 0 && (
            <div className="text-center py-8">
              <p className="text-readout mb-4">No collections found for this entity type</p>
              <button
                onClick={() => setShowCreateForm(true)}
                className="btn btn-primary"
              >
                Create your first collection
              </button>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-base-300 flex justify-end gap-2">
          <button onClick={onClose} className="btn btn-neutral btn-ghost">
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="btn btn-primary"
            disabled={selectedCollectionIds.length === 0}
          >
            Add to Collections ({selectedCollectionIds.length})
          </button>
        </div>
      </div>
    </div>
  )
}
