import { useState, useEffect, useCallback } from 'react'
import { collectionsService } from '@/services/domain/CollectionsService'
import { agentKitService } from '@/services/domain/AgentKitService'
import { AddToCollectionModal } from '../features/collections/AddToCollectionModal'
import { useNotificationStore } from '@/stores/notificationStore'
import type { Collection } from '@/types/collections'
import type { KitSummary } from '@/services/domain/AgentKitService'

interface CollectionsTabProps {
  profileId: string
  profileName: string
}

export default function CollectionsTab({ profileId, profileName }: CollectionsTabProps) {
  const [collections, setCollections] = useState<Collection[]>([])
  const [loading, setLoading] = useState(true)
  const [showAddModal, setShowAddModal] = useState(false)
  // THE OWNED TOOLKITS (2026-09-04, the _35 P4): the agent_kits
  // join direction — the kits this agent OWNS (its tool surface)
  const [kits, setKits] = useState<KitSummary[]>([])
  const [allToolCollections, setAllToolCollections] = useState<Collection[]>([])
  const [kitsLoading, setKitsLoading] = useState(true)
  const [attachKitId, setAttachKitId] = useState('')
  const [busyKit, setBusyKit] = useState<string | null>(null)
  const addNotification = useNotificationStore((state) => state.addNotification)

  useEffect(() => {
    loadCollections()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profileId])

  const loadToolkits = useCallback(async () => {
    try {
      setKitsLoading(true)
      const owned = await agentKitService.getAgentKits(Number(profileId))
      setKits(owned)
      // the attach picker: tool collections the agent does NOT own yet
      const all = await collectionsService.listCollections({ entity_type: 'tool' })
      setAllToolCollections(all.collections.filter(c => !owned.some(k => k.id === c.id)))
      if (!attachKitId && all.collections.length > 0) {
        setAttachKitId(all.collections.filter(c => !owned.some(k => k.id === c.id))[0]?.id ?? '')
      }
    } catch {
      addNotification({ type: 'error', title: 'Error', message: 'Failed to load toolkits' })
    } finally {
      setKitsLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profileId])

  useEffect(() => {
    loadToolkits()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profileId])

  const loadCollections = async () => {
    try {
      setLoading(true)
      const result = await collectionsService.findCollectionsContainingEntity('agent', profileId)
      setCollections(result.collections)
    } catch (error) {
      console.error('Failed to load collections:', error)
      addNotification({
        type: 'error',
        title: 'Error',
        message: 'Failed to load collections'
      })
    } finally {
      setLoading(false)
    }
  }

  const handleRemoveFromCollection = async (collectionId: string, collectionName: string) => {
    const confirmed = confirm(`Remove "${profileName}" from "${collectionName}"?`)
    if (!confirmed) return

    try {
      await collectionsService.removeItemFromCollection(collectionId, profileId)
      addNotification({
        type: 'success',
        title: 'Removed',
        message: `Removed from "${collectionName}"`
      })
      loadCollections()
    } catch (error) {
      console.error('Failed to remove from collection:', error)
      addNotification({
        type: 'error',
        title: 'Error',
        message: 'Failed to remove from collection'
      })
    }
  }

  const handleAttachKit = async () => {
    if (!attachKitId) return
    try {
      setBusyKit(attachKitId)
      await agentKitService.attachKit(Number(profileId), attachKitId)
      addNotification({
        type: 'success',
        title: 'Attached',
        message: 'Toolkit attached — the agent\'s surface is now the union of all its kits'
      })
      await loadToolkits()
    } catch (error) {
      console.error('Failed to attach toolkit:', error)
      addNotification({ type: 'error', title: 'Error', message: 'Failed to attach toolkit' })
    } finally {
      setBusyKit(null)
    }
  }

  const handleDetachKit = async (kit: KitSummary) => {
    const confirmed = confirm(`Detach "${kit.name}" from "${profileName}"?\n\nThe agent loses the kit's tools from its surface.`)
    if (!confirmed) return
    try {
      setBusyKit(kit.id)
      await agentKitService.detachKit(Number(profileId), kit.id)
      addNotification({ type: 'success', title: 'Detached', message: `Detached "${kit.name}"` })
      await loadToolkits()
    } catch (error) {
      console.error('Failed to detach toolkit:', error)
      addNotification({ type: 'error', title: 'Error', message: 'Failed to detach toolkit' })
    } finally {
      setBusyKit(null)
    }
  }

  const handleAddedToCollections = () => {
    addNotification({
      type: 'success',
      title: 'Added',
      message: 'Added to collection(s)'
    })
    setShowAddModal(false)
    loadCollections()
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <span className="loading loading-spinner loading-md text-primary"></span>
        <span className="ml-3 text-readout">Loading collections...</span>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* THE OWNED TOOLKITS (2026-09-04, the _35 P4): the kits the
          agent OWNS — its tool surface (the union policy). */}
      <div className="card bg-base-200 border border-base-300">
        <div className="card-body p-4">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="font-bold flex items-center gap-2">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
                Toolkits
              </h4>
              <p className="text-sm text-readout">
                The toolkits this agent OWNS — its tool surface is the union of them
              </p>
            </div>
          </div>

          {kitsLoading ? (
            <div className="flex items-center gap-3 py-4">
              <span className="loading loading-spinner loading-sm text-primary"></span>
              <span className="text-sm text-readout">Loading toolkits...</span>
            </div>
          ) : kits.length === 0 ? (
            <p className="text-sm text-readout py-3">
              No toolkits owned — the agent keeps the default tool surface
            </p>
          ) : (
            <div className="flex flex-wrap gap-2 mt-3">
              {kits.map(kit => (
                <div
                  key={kit.id}
                  className="badge badge-lg gap-2 pl-3 pr-1 py-3 border border-primary/30 bg-base-100"
                >
                  <span className="text-base">{kit.icon || '📦'}</span>
                  <span className="font-medium">{kit.name}</span>
                  <button
                    className="btn btn-ghost btn-xs btn-circle hover:bg-error/10 hover:text-error"
                    onClick={() => handleDetachKit(kit)}
                    disabled={busyKit === kit.id}
                    data-tip="Detach toolkit"
                  >
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* The attach control */}
          {!kitsLoading && allToolCollections.length > 0 && (
            <div className="flex items-center gap-2 mt-3">
              <select
                className="select select-sm select-bordered max-w-xs"
                value={attachKitId}
                onChange={(e) => setAttachKitId(e.target.value)}
              >
                {allToolCollections.map(c => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
              <button
                className="btn btn-primary btn-sm rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
                onClick={handleAttachKit}
                disabled={!attachKitId || busyKit !== null}
              >
                Attach toolkit
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold">Collections</h3>
          <p className="text-sm text-readout">
            Manage which collections this agent belongs to
          </p>
        </div>
        <button
          className="btn btn-primary btn-sm rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
          onClick={() => setShowAddModal(true)}
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Add to Collection
        </button>
      </div>

      {/* Collections List */}
      {collections.length === 0 ? (
        <div className="text-center py-12 bg-base-200 rounded-lg">
          <div className="text-4xl mb-3">📦</div>
          <p className="text-readout mb-4">This agent is not in any collections yet</p>
          <button
            className="btn btn-outline btn-sm rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
            onClick={() => setShowAddModal(true)}
          >
            Add to Collection
          </button>
        </div>
      ) : (
        <div className="grid gap-3">
          {collections.map(collection => (
            <div
              key={collection.id}
              className="card bg-base-200 border border-base-300"
            >
              <div className="card-body p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="text-2xl">{collection.icon}</div>
                    <div>
                      <h4 className="font-bold">{collection.name}</h4>
                      {collection.description && (
                        <p className="text-sm text-readout">{collection.description}</p>
                      )}
                      <div className="flex items-center gap-2 mt-1">
                        <span className="badge badge-ghost badge-xs">
                          {collection.item_count} {collection.item_count === 1 ? 'item' : 'items'}
                        </span>
                        <span className="text-xs text-readout">
                          Added {new Date(collection.created_at).toLocaleDateString()}
                        </span>
                      </div>
                    </div>
                  </div>
                  <button
                    className="btn btn-ghost btn-xs text-error rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
                    onClick={() => handleRemoveFromCollection(collection.id, collection.name)}
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                    Remove
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add to Collection Modal */}
      {showAddModal && (
        <AddToCollectionModal
          entityId={profileId}
          entityName={profileName}
          entityType="agent"
          onClose={() => setShowAddModal(false)}
          onAdded={handleAddedToCollections}
        />
      )}
    </div>
  )
}
