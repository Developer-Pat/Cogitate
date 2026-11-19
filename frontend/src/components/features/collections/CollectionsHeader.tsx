/**
 * Collections Header Component
 * 
 * Page header with title, create button, and view toggle.
 */

import React from 'react'

interface CollectionsHeaderProps {
  onCreate: () => void
  viewMode: 'grid' | 'list'
  onViewModeChange: (mode: 'grid' | 'list') => void
  title?: string
  subtitle?: string
  createButtonText?: string
}

export const CollectionsHeader: React.FC<CollectionsHeaderProps> = ({
  onCreate,
  viewMode,
  onViewModeChange,
  title = 'Collections',
  subtitle = 'Manage all your collections in one place',
  createButtonText = 'New Collection',
}) => {
  return (
    <div className="flex items-center justify-between">
      <div>
        <h1 className="text-2xl font-bold text-base-content">{title}</h1>
        <p className="text-sm text-readout mt-1">
          {subtitle}
        </p>
      </div>

      <div className="flex items-center gap-3">
        {/* View Toggle */}
        <div className="btn-group flex border border-base-300 rounded-lg overflow-hidden">
          <button
            onClick={() => onViewModeChange('grid')}
            className={`btn btn-sm ${
              viewMode === 'grid' ? 'btn-active btn-selected' : 'btn-outline'
            }`}
            data-tip="Grid view"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
            </svg>
          </button>
          <button
            onClick={() => onViewModeChange('list')}
            className={`btn btn-sm ${
              viewMode === 'list' ? 'btn-active btn-selected' : 'btn-outline'
            }`}
            data-tip="List view"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
            </svg>
          </button>
        </div>

        {/* Create Button */}
        <button
          onClick={onCreate}
          className="btn btn-primary gap-2"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          <span>{createButtonText}</span>
        </button>
      </div>
    </div>
  )
}
