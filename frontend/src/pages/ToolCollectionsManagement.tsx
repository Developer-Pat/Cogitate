/**
 * Tool Collections Management Page
 *
 * Main hub for viewing and managing tool collections.
 * Integrated with backend API via CollectionsService.
 */

import { useState, useMemo, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePageTitle } from '../hooks/usePageTitle'
import { collectionsService } from '../services/domain/CollectionsService'
import { agentKitService } from '../services/domain/AgentKitService'
import type { Collection, CollectionCreate, CollectionUpdate } from '../types/collections'
import type { AgentOwnerSummary as AgentOwner } from '../services/domain/AgentKitService'
import { CollectionsHeader } from '@/components/features/collections/CollectionsHeader'
import { CollectionsFilters } from '@/components/features/collections/CollectionsFilters'
import { CollectionsSection } from '@/components/features/collections/CollectionsSection'
import { CollectionCard } from '@/components/features/collections/CollectionCard'
import { EmptyState } from '@/components/features/collections/EmptyState'
import { CreateCollectionModal } from '@/components/features/collections/CreateCollectionModal'
import { EditCollectionModal } from '@/components/features/collections/EditCollectionModal'
import { DeleteConfirmationModal } from '@/components/features/collections/DeleteConfirmationModal'

type ViewMode = 'grid' | 'list'
type SortOption = 'name' | 'itemCount' | 'createdAt' | 'updatedAt'

export default function ToolCollectionsManagement() {
  usePageTitle('Toolkits', 'Manage your toolkits — the tool collections an agent owns')

  const navigate = useNavigate()

  // State
  const [collections, setCollections] = useState<Collection[]>([])
  const [ownersMap, setOwnersMap] = useState<Map<string, AgentOwner[]>>(new Map())
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>('grid')
  const [searchQuery, setSearchQuery] = useState('')
  const [sortOption, setSortOption] = useState<SortOption>('updatedAt')
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingCollection, setEditingCollection] = useState<Collection | null>(null)
  const [deletingCollection, setDeletingCollection] = useState<Collection | null>(null)

  // Load tool collections from backend
  const loadCollections = useCallback(async () => {
    try {
      setIsLoading(true)
      setError(null)
      const response = await collectionsService.listCollections({ entity_type: 'tool' })
      // THE OWNING AGENTS (2026-09-04, the _35 P4): each toolkit's
      // owners via the agent_kits join — fetched once per load.
      const ownersMap = new Map<string, AgentOwner[]>()
      for (const kit of response.collections) {
        try {
          const owners = await agentKitService.getKitOwners(kit.id)
          ownersMap.set(kit.id, owners)
        } catch {
          // owners are decorative — a failure leaves the card without them
        }
      }
      setOwnersMap(ownersMap)
      setCollections(response.collections)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load tool collections')
      setCollections([])
    } finally {
      setIsLoading(false)
    }
  }, [])

  // Initial load
  useEffect(() => {
    loadCollections()
  }, [loadCollections])

  // Get recent collections (top 3 by updatedAt)
  const recentCollections = useMemo(() => {
    return [...collections]
      .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
      .slice(0, 3)
  }, [collections])

  // Filter and sort all collections
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

    // Exclude recent collections from "All" when not searching
    // (to avoid showing the same collections twice)
    if (!searchQuery && recentCollections.length > 0) {
      const recentIds = new Set(recentCollections.map(c => c.id))
      result = result.filter(c => !recentIds.has(c.id))
    }

    return result
  }, [searchQuery, sortOption, collections, recentCollections])

  // Handlers
  const handleOpenCollection = (collectionId: string) => {
    navigate(`/toolkits/${collectionId}`)
  }

  const handleCreateCollection = async (
    name: string,
    description: string,
    color: string,
    icon: string
  ) => {
    try {
      const collectionData: CollectionCreate = {
        name,
        description: description || undefined,
        entity_type: 'tool',
        color,
        icon,
      }
      await collectionsService.createCollection(collectionData)
      await loadCollections()
      setShowCreateModal(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create collection')
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
      setError(err instanceof Error ? err.message : 'Failed to update collection')
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
      setError(err instanceof Error ? err.message : 'Failed to delete collection')
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
        viewMode={viewMode}
        onViewModeChange={setViewMode}
      />

      {/* Filters */}
      <CollectionsFilters
        filterType="none"
        onFilterTypeChange={() => {}}
        searchQuery={searchQuery}
        onSearchQueryChange={setSearchQuery}
        sortOption={sortOption}
        onSortOptionChange={setSortOption}
      />

      {/* Main Content */}
      <div className="mt-6 space-y-8">
        {/* Filter Summary */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-sm text-readout">Showing:</span>
            <div className="flex gap-2">
              <span className="badge badge-primary badge-outline gap-1">
                Toolkits
              </span>
              {searchQuery && (
                <span className="badge badge-secondary badge-outline gap-1">
                  Search: "{searchQuery}"
                  <button
                    onClick={() => setSearchQuery('')}
                    className="ml-1 hover:text-base-content"
                    data-tip="Clear search"
                  >
                    ×
                  </button>
                </span>
              )}
              {filteredCollections.length === 0 && (
                <span className="badge badge-ghost">No results</span>
              )}
            </div>
          </div>
        </div>

        {/* Recent Collections */}
        {recentCollections.length > 0 && !searchQuery && (
          <CollectionsSection
            title="Recent Collections"
            count={recentCollections.length}
            viewMode={viewMode}
          >
            {recentCollections.map(collection => (
              <CollectionCard
                key={collection.id}
                collection={collection}
                viewMode={viewMode}
                owners={ownersMap.get(collection.id)}
                onOpen={() => handleOpenCollection(collection.id)}
                onEdit={() => handleEditCollection(collection)}
                onDelete={() => handleDeleteCollection(collection)}
              />
            ))}
          </CollectionsSection>
        )}

        {/* All Collections or Empty State */}
        {filteredCollections.length > 0 && (
          <CollectionsSection
            title={searchQuery ? `Search Results` : "All Toolkits"}
            count={filteredCollections.length}
            viewMode={viewMode}
          >
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {filteredCollections.map(collection => (
                <CollectionCard
                  key={collection.id}
                  collection={collection}
                  viewMode="grid"
                  owners={ownersMap.get(collection.id)}
                  onOpen={() => handleOpenCollection(collection.id)}
                  onEdit={() => handleEditCollection(collection)}
                  onDelete={() => handleDeleteCollection(collection)}
                />
              ))}
            </div>
          </CollectionsSection>
        )}

        {/* Empty State (only when no collections at all) */}
        {filteredCollections.length === 0 && collections.length === 0 && !searchQuery && (
          <EmptyState
            filterType="tool"
            searchQuery={searchQuery}
            onCreate={() => setShowCreateModal(true)}
          />
        )}
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <CreateCollectionModal
          onClose={() => setShowCreateModal(false)}
          onCreate={handleCreateCollection}
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
