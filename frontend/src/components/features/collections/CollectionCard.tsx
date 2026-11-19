/**
 * Collection Card Component
 *
 * Displays a single collection in grid or list view.
 */

import React from 'react'
import type { Collection } from '@/types/collections'
import type { AgentOwnerSummary } from '@/services/domain/AgentKitService'

interface CollectionCardProps {
  collection: Collection
  viewMode: 'grid' | 'list'
  onOpen: () => void
  onEdit: () => void
  onDelete: () => void
  /** The owning agents (toolkit view only — the agent_kits join). */
  owners?: AgentOwnerSummary[]
}

const ENTITY_TYPE_LABELS: Record<string, string> = {
  agent: 'Agents',
  tool: 'Tools',
  provider: 'Providers',
  macro_set: 'Macro Sets',
  template: 'Templates',
}

export const CollectionCard: React.FC<CollectionCardProps> = ({
  collection,
  viewMode,
  onOpen,
  onEdit,
  onDelete,
  owners,
}) => {
  const label = ENTITY_TYPE_LABELS[collection.entity_type] || collection.entity_type
  const ownersText = owners && owners.length > 0 ? owners.map(o => o.name).join(', ') : null

  if (viewMode === 'list') {
    return (
      <div className="card bg-base-100 border border-base-300 hover:border-primary hover:shadow-md transition-all">
        <div className="card-body p-4 flex-row items-center gap-4">
          <div className="text-3xl">{collection.icon}</div>
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-lg truncate text-base-content">{collection.name}</h3>
            <div className="flex items-center gap-2 mt-1">
              <span className="badge badge-sm badge-outline">{label}</span>
              <span className="text-sm text-readout">{collection.item_count} items</span>
            </div>
            {collection.description && (
              <p className="text-sm text-readout truncate mt-1">{collection.description}</p>
            )}
            {ownersText && (
              <p className="text-xs text-readout mt-1">
                Owned by <span className="text-primary">{ownersText}</span>
              </p>
            )}
          </div>
          <div className="flex gap-2">
            <button
              onClick={onOpen}
              className="btn btn-primary btn-outline btn-sm"
              data-tip="Open collection"
            >
              Open
            </button>
            <button
              onClick={onEdit}
              className="btn btn-ghost btn-sm"
              data-tip="Edit collection"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
            </button>
            <button
              onClick={onDelete}
              className="btn btn-error btn-outline btn-sm"
              data-tip="Delete collection"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    )
  }
  
  // Grid view
  return (
    <div
      onClick={onOpen}
      className="card bg-base-100 border border-base-300 hover:border-primary hover:shadow-lg transition-all cursor-pointer"
    >
      <div className="card-body p-4">
        <div className="text-4xl mb-2">{collection.icon}</div>
        <h3 className="font-semibold text-lg mb-1 truncate text-base-content">{collection.name}</h3>
        <div className="flex items-center gap-2 mb-2">
          <span className="badge badge-sm badge-outline">{label}</span>
          <span className="text-sm text-readout">{collection.item_count} items</span>
        </div>
        {collection.description && (
          <p className="text-sm text-readout line-clamp-2 mb-3 min-h-[2.5rem]">
            {collection.description}
          </p>
        )}
        {ownersText && (
          <p className="text-xs text-readout mb-2 -mt-2 truncate">
            Owned by <span className="text-primary">{ownersText}</span>
          </p>
        )}
        <div className="text-xs text-readout">
          Updated {new Date(collection.updated_at).toLocaleDateString()}
        </div>
        <div className="card-actions justify-end mt-2 pt-3 border-t border-base-300">
          <button
            onClick={(e) => {
              e.stopPropagation()
              onOpen()
            }}
            className="btn btn-primary btn-outline btn-sm flex-1"
            data-tip="Open collection"
          >
            Open
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation()
              onEdit()
            }}
            className="btn btn-ghost btn-sm"
            data-tip="Edit collection"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation()
              onDelete()
            }}
            className="btn btn-error btn-outline btn-sm"
            data-tip="Delete collection"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
}
