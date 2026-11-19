/**
 * Collection Detail Page
 *
 * View and manage items within a specific collection.
 * Integrated with backend API via CollectionsService.
 */

import React, { useState, useEffect, useCallback } from 'react'
import { Package } from 'lucide-react'
import { useParams, useNavigate } from 'react-router-dom'
import { collectionsService } from '../services/domain/CollectionsService'
import type { Collection, CollectionUpdate } from '../types/collections'
import { EditCollectionModal } from '@/components/features/collections/EditCollectionModal'
import { DeleteConfirmationModal } from '@/components/features/collections/DeleteConfirmationModal'

export default function CollectionDetail() {
  const { collectionId } = useParams<{ collectionId: string }>()
  const navigate = useNavigate()
  const [collection, setCollection] = useState<Collection | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [editingCollection, setEditingCollection] = useState<Collection | null>(null)
  const [deletingCollection, setDeletingCollection] = useState<Collection | null>(null)

  // Load collection from backend
  const loadCollection = useCallback(async () => {
    if (!collectionId) return
    try {
      setIsLoading(true)
      setError(null)
      const found = await collectionsService.getCollection(collectionId)
      setCollection(found)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load collection')
      setCollection(null)
    } finally {
      setIsLoading(false)
    }
  }, [collectionId])

  // Initial load
  useEffect(() => {
    loadCollection()
  }, [loadCollection])

  const handleRemoveItem = async (itemId: string) => {
    if (!collection) return
    try {
      await collectionsService.removeItemFromCollection(collection.id, itemId)
      await loadCollection()
    } catch (err) {
      console.error('Failed to remove item:', err)
    }
  }

  const handleBack = () => {
    navigate('/collections')
  }

  const handleEdit = () => {
    setEditingCollection(collection)
  }

  const handleSaveEdit = async (_id: string, updates: CollectionUpdate) => {
    if (!collection) return
    try {
      await collectionsService.updateCollection(collection.id, updates)
      await loadCollection()
      setEditingCollection(null)
    } catch (err) {
      console.error('Failed to update collection:', err)
    }
  }

  const handleDelete = () => {
    setDeletingCollection(collection)
  }

  const handleConfirmDelete = async (id: string) => {
    try {
      await collectionsService.deleteCollection(id)
      setDeletingCollection(null)
      navigate('/collections')
    } catch (err) {
      console.error('Failed to delete collection:', err)
    }
  }

  const handleAddItems = () => {
    // Navigate to appropriate page based on entity type to add items
    // For now, just show a message
    console.log('Would add items to collection:', collection)
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-base-200 flex items-center justify-center">
        <span className="loading loading-lg"></span>
      </div>
    )
  }

  if (error || !collection) {
    return (
      <div className="min-h-screen bg-base-200 flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-base-content mb-2">Collection Not Found</h1>
          <p className="text-readout mb-4">
            {error || "The collection you're looking for doesn't exist."}
          </p>
          <button
            onClick={() => navigate('/collections')}
            className="btn btn-primary"
          >
            Back to Collections
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-base-200">
      {/* Header Bar */}
      <div className="bg-base-100 border-b px-6 py-4">
        <button
          onClick={handleBack}
          className="btn btn-ghost gap-2 mb-4"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          Back to Collections
        </button>

        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="text-5xl">{collection.icon}</div>
            <div>
              <h1 className="text-2xl font-bold text-base-content">{collection.name}</h1>
              <p className="text-readout">{collection.description}</p>
            </div>
          </div>

          <div className="flex gap-2">
            <button
              onClick={handleAddItems}
              className="btn btn-primary gap-2"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Add Items
            </button>
            <button
              onClick={handleEdit}
              className="btn btn-ghost gap-2"
              data-tip="Edit collection"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
              Edit
            </button>
            <button
              onClick={handleDelete}
              className="btn btn-ghost text-error gap-2"
              data-tip="Delete collection"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
              Delete
            </button>
          </div>
        </div>

        {/* Metadata */}
        <div className="flex items-center gap-4 mt-4 text-sm text-readout">
          <div className="badge badge-outline">{collection.item_count} items</div>
          <span>Created {new Date(collection.created_at).toLocaleDateString()}</span>
          <span>•</span>
          <span>Updated {new Date(collection.updated_at).toLocaleDateString()}</span>
        </div>
      </div>

      {/* Items Grid */}
      <div className="p-6">
        {collection.items.length === 0 ? (
          <div className="text-center py-12">
            <div className="text-readout mb-4 flex justify-center">
              <Package className="h-16 w-16" />
            </div>
            <h3 className="text-xl font-semibold text-base-content mb-2">No items yet</h3>
            <p className="text-readout mb-6">
              Add items to this collection to get started
            </p>
            <button
              onClick={handleAddItems}
              className="btn btn-primary"
            >
              Add Items
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {collection.items.map(item => (
              <CollectionItemCard
                key={item.id}
                item={item}
                onRemove={() => handleRemoveItem(item.id)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Edit Modal */}
      {editingCollection && (
        <EditCollectionModal
          collection={editingCollection}
          onClose={() => setEditingCollection(null)}
          onSave={handleSaveEdit}
        />
      )}

      {/* Delete Confirmation Modal */}
      {deletingCollection && (
        <DeleteConfirmationModal
          collection={deletingCollection}
          onClose={() => setDeletingCollection(null)}
          onConfirm={handleConfirmDelete}
        />
      )}
    </div>
  )
}

interface CollectionItemCardProps {
  item: {
    id: string
    entity_id: string
    entity_type: string
    entity_name: string
    added_at: string
  }
  onRemove: () => void
}

const CollectionItemCard: React.FC<CollectionItemCardProps> = ({
  item,
  onRemove,
}) => {
  const entityTypeColors: Record<string, string> = {
    tool: 'badge-info',
    agent: 'badge-success',
    provider: 'badge-secondary',
    macro_set: 'badge-warning',
    template: 'badge-error',
  }

  const badgeClass = entityTypeColors[item.entity_type] || 'badge-ghost'

  return (
    <div
      className={`
        card bg-base-100 border border-base-300 hover:border-primary hover:shadow-md transition-all
      `}
    >
      <div className="card-body p-4">
        <div className="flex items-start justify-between mb-2">
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-base-content truncate">{item.entity_name}</h3>
            <p className="text-xs text-readout mt-1">
              Added {new Date(item.added_at).toLocaleDateString()}
            </p>
          </div>
          <button
            onClick={onRemove}
            className="btn btn-ghost btn-xs text-base-content/40 hover:text-error"
            data-tip="Remove from collection"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <span className={`badge badge-sm ${badgeClass}`}>
          {item.entity_type.replace('_', ' ')}
        </span>
      </div>
    </div>
  )
}
