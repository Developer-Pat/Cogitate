/**
 * Collectives Management Page
 *
 * Lists all collectives (agent groupings) with CRUD operations.
 * Clicking a collective navigates to the Collective Detail page.
 */

import { useState, useMemo, useEffect, useCallback } from 'react'
import { useTeamSync } from '../hooks/useTeamSync'
import { useNavigate } from 'react-router-dom'
import { usePageTitle } from '../hooks/usePageTitle'
import type { Collection, CollectionCreate, CollectionUpdate } from '../types/collections'
import { CollectionsHeader } from '@/components/features/collections/CollectionsHeader'
import { TeamsTable } from '@/components/Teams/TeamsTable'
import { EmptyState } from '@/components/features/collections/EmptyState'
import { CreateCollectionModal } from '@/components/features/collections/CreateCollectionModal'
import { EditCollectionModal } from '@/components/features/collections/EditCollectionModal'
import { DeleteConfirmationModal } from '@/components/features/collections/DeleteConfirmationModal'
import { collectionsService } from '../services/domain/CollectionsService'

type SortOption = 'name' | 'itemCount' | 'createdAt' | 'updatedAt'

export default function TeamsManagement() {
  usePageTitle('Collectives', 'Organize agents into collectives')

  const navigate = useNavigate()

  // State
  const [collections, setCollections] = useState<Collection[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [sortOption, setSortOption] = useState<SortOption>('updatedAt')
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingCollection, setEditingCollection] = useState<Collection | null>(null)
  const [deletingCollection, setDeletingCollection] = useState<Collection | null>(null)

  // Load teams from backend (entity_type='agent')
  const loadCollections = useCallback(async () => {
    try {
      setIsLoading(true)
      setError(null)
      const response = await collectionsService.listCollections({ entity_type: 'agent' })
      setCollections(response.collections)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load collectives')
      setCollections([])
    } finally {
      setIsLoading(false)
    }
  }, [])

  // Initial load
  useEffect(() => {
    loadCollections()
  }, [loadCollections])

  // THE CROSS-WINDOW TEAM SYNC (2026-08-25, the roadmap Phase 4):
  // the mutations elsewhere reload this page.
  useTeamSync(() => {
    void loadCollections()
  })

  // Filter and sort
  const filteredCollections = useMemo(() => {
    let result = [...collections]

    // Apply search
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase()
      result = result.filter(c =>
        c.name.toLowerCase().includes(query) ||
        c.description?.toLowerCase().includes(query)
      )
    }

    // Sort
    result.sort((a, b) => {
      switch (sortOption) {
        case 'name':
          return a.name.localeCompare(b.name)
        case 'itemCount':
          return b.item_count - a.item_count
        case 'createdAt':
          return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        case 'updatedAt':
          return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
        default:
          return 0
      }
    })

    return result
  }, [searchQuery, sortOption, collections])

  // Handlers
  const handleOpenCollection = (collectionId: string) => {
    navigate(`/teams/${collectionId}`)
  }

  const handleCreateCollection = async (
    name: string,
    description: string,
    _entityType: string,
    color: string,
    icon: string
  ) => {
    try {
      const collectionData: CollectionCreate = {
        name,
        description: description || undefined,
        entity_type: 'agent',
        color,
        icon,
      }
      await collectionsService.createCollection(collectionData)
      await loadCollections()
      setShowCreateModal(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create collective')
    }
  }

  const handleEditCollection = (collection: Collection) => {
    setEditingCollection(collection)
  }

  const handleSaveEditCollection = async (id: string, updates: CollectionUpdate) => {
    try {
      await collectionsService.updateCollection(id, updates)
      await loadCollections()
      setEditingCollection(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update collective')
    }
  }

  const handleDeleteCollection = (collection: Collection) => {
    setDeletingCollection(collection)
  }

  const handleConfirmDelete = async (id: string) => {
    try {
      await collectionsService.deleteCollection(id)
      await loadCollections()
      setDeletingCollection(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete collective')
    }
  }

  if (isLoading) {
    return (
      <div className="p-6 max-w-7xl mx-auto">
        <div className="flex items-center justify-center min-h-[400px]">
          <span className="loading loading-lg"></span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6 max-w-7xl mx-auto">
        <div className="alert alert-error">
          <span>{error}</span>
          <button className="btn btn-sm btn-outline" onClick={loadCollections}>Retry</button>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <CollectionsHeader
        onCreate={() => setShowCreateModal(true)}
        viewMode="list"
        onViewModeChange={() => {}}
        title="Collectives"
        subtitle="Groups of agents by a common attribute"
        createButtonText="New Collective"
      />

      {/* Filters - no type filter needed, only shows teams */}
      <div className="flex items-center gap-4 mt-4">
        {/* Search */}
        <div className="flex-1 max-w-md">
          <div className="join w-full">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search collectives..."
              className="input input-bordered join-item w-full text-sm"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="btn btn-square btn-sm join-item"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>
        </div>

        {/* Sort */}
        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-base-content">Sort:</label>
          <select
            value={sortOption}
            onChange={(e) => setSortOption(e.target.value as SortOption)}
            className="select select-bordered select-sm"
          >
            <option value="name">Name</option>
            <option value="itemCount">Member Count</option>
            <option value="createdAt">Newest First</option>
            <option value="updatedAt">Recently Updated</option>
          </select>
        </div>
      </div>

      {/* Main Content */}
      <div className="mt-6 space-y-8">
        {/* Filter Summary */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-sm text-readout">Showing:</span>
            <div className="flex gap-2">
              {searchQuery && (
                <span className="badge badge-secondary gap-1">
                  Search: "{searchQuery}"
                  <button
                    onClick={() => setSearchQuery('')}
                    className="ml-1 hover:text-base-content"
                  >
                    ×
                  </button>
                </span>
              )}
              {filteredCollections.length === 0 && searchQuery && (
                <span className="badge badge-ghost">No results</span>
              )}
            </div>
          </div>
        </div>

        {/* All Teams or Empty State */}
        {filteredCollections.length === 0 ? (
          <EmptyState
            filterType="team"
            searchQuery={searchQuery}
            onCreate={() => setShowCreateModal(true)}
          />
        ) : (
          <TeamsTable
            teams={filteredCollections}
            onOpen={handleOpenCollection}
            onEdit={handleEditCollection}
            onDelete={handleDeleteCollection}
          />
        )}
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <CreateCollectionModal
          onClose={() => setShowCreateModal(false)}
          onCreate={handleCreateCollection}
          entityType="agent"
        />
      )}

      {/* Edit Modal */}
      {editingCollection && (
        <EditCollectionModal
          collection={editingCollection}
          onClose={() => setEditingCollection(null)}
          onSave={handleSaveEditCollection}
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
