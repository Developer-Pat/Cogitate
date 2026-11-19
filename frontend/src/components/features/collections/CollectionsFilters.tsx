/**
 * Collections Filters Component
 * 
 * Filter bar with entity type dropdown, search, and sort options.
 */

import React from 'react'
import type { EntityType } from '@/mocks/collectionsData'

type SortOption = 'name' | 'itemCount' | 'createdAt' | 'updatedAt'

interface CollectionsFiltersProps {
  filterType: EntityType | 'all' | 'none'
  onFilterTypeChange: (type: EntityType | 'all' | 'none') => void
  searchQuery: string
  onSearchQueryChange: (query: string) => void
  sortOption: SortOption
  onSortOptionChange: (option: SortOption) => void
}

const ENTITY_TYPE_OPTIONS: { value: EntityType | 'all' | 'none'; label: string }[] = [
  { value: 'none', label: 'None (Select a type)' },
  { value: 'all', label: 'All Types' },
  { value: 'tool', label: 'Tools' },
  { value: 'provider', label: 'Providers' },
  { value: 'macro_set', label: 'Macro Sets' },
  { value: 'template', label: 'Templates' },
]

const SORT_OPTIONS: { value: SortOption; label: string }[] = [
  { value: 'name', label: 'Name' },
  { value: 'itemCount', label: 'Item Count' },
  { value: 'createdAt', label: 'Newest First' },
  { value: 'updatedAt', label: 'Recently Updated' },
]

export const CollectionsFilters: React.FC<CollectionsFiltersProps> = ({
  filterType,
  onFilterTypeChange,
  searchQuery,
  onSearchQueryChange,
  sortOption,
  onSortOptionChange,
}) => {
  return (
    <div className="flex items-center gap-4 mt-4">
      {/* Type Filter */}
      <div className="flex items-center gap-2">
        <label className="text-sm font-medium text-base-content">Filter:</label>
        <select
          value={filterType}
          onChange={(e) => onFilterTypeChange(e.target.value as EntityType | 'all')}
          className="select select-bordered select-sm"
          data-tip="Filter by entity type"
        >
          {ENTITY_TYPE_OPTIONS.map(option => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
      
      {/* Search */}
      <div className="flex-1 max-w-md">
        <div className="join w-full">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchQueryChange(e.target.value)}
            placeholder="Search collections..."
            className="input input-bordered join-item w-full text-sm"
            data-tip="Search by name or description"
          />
          {searchQuery && (
            <button
              onClick={() => onSearchQueryChange('')}
              className="btn btn-square btn-sm join-item"
              data-tip="Clear search"
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
          onChange={(e) => onSortOptionChange(e.target.value as SortOption)}
          className="select select-bordered select-sm"
          data-tip="Sort collections"
        >
          {SORT_OPTIONS.map(option => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  )
}
