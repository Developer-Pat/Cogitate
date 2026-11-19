/**
 * Empty State Component
 * 
 * Displayed when no collections match the current filters.
 */

import React from 'react'
import type { EntityType } from '@/mocks/collectionsData'

interface EmptyStateProps {
  filterType: EntityType | 'all' | 'team'
  searchQuery: string
  onCreate: () => void
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  filterType,
  searchQuery,
  onCreate,
}) => {
  if (searchQuery.trim()) {
    return (
      <div className="col-span-full text-center py-12">
        <div className="text-6xl mb-4 opacity-50">🔍</div>
        <p className="text-lg font-semibold text-base-content mb-2">No collections found</p>
        <p className="text-readout text-sm">
          Try adjusting your search or filters
        </p>
      </div>
    )
  }

  // Teams-specific empty state
  if (filterType === 'team') {
    return (
      <div className="col-span-full text-center py-12">
        <div className="text-6xl mb-4">👥</div>
        <h3 className="text-xl font-semibold text-base-content mb-2">
          No teams yet
        </h3>
        <p className="text-readout mb-6 max-w-md mx-auto">
          Create your first team to organize your agents and manage their tools together
        </p>
        <button
          onClick={onCreate}
          className="btn btn-primary gap-2"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Create Your First Team
        </button>
      </div>
    )
  }

  const typeLabel = filterType === 'all'
    ? 'any type'
    : filterType.replace('_', ' ')

  return (
    <div className="col-span-full text-center py-12">
      <div className="text-6xl mb-4">📁</div>
      <h3 className="text-xl font-semibold text-base-content mb-2">
        No collections yet
      </h3>
      <p className="text-readout mb-6 max-w-md mx-auto">
        {filterType === 'all'
          ? "Create your first collection to organize your tools, agents, and other resources"
          : `No ${typeLabel} collections yet. Create one to get started!`
        }
      </p>
      <button
        onClick={onCreate}
        className="btn btn-primary gap-2"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
        </svg>
        Create Your First Collection
      </button>
    </div>
  )
}
