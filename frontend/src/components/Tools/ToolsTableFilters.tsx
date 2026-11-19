// import React from 'react'
import { TagBadge } from './TagBadge'
import { KNOWN_TAGS } from '@/types/toolTags'

interface ToolsTableFiltersProps {
  searchQuery: string
  types: string[]
  typeFilter: string[]
  statusFilter: 'all' | 'active' | 'inactive'
  tagFilter: string[]
  onSearch: (query: string) => void
  onTypeFilter: (types: string[]) => void
  onStatusFilter: (status: 'all' | 'active' | 'inactive') => void
  onTagFilter: (tags: string[]) => void
}

export default function ToolsTableFilters({
  searchQuery,
  types,
  typeFilter,
  statusFilter,
  tagFilter,
  onSearch,
  onTypeFilter,
  onStatusFilter,
  onTagFilter,
}: ToolsTableFiltersProps) {
  const handleTypeToggle = (type: string) => {
    if (typeFilter.includes(type)) {
      onTypeFilter(typeFilter.filter(t => t !== type))
    } else {
      onTypeFilter([...typeFilter, type])
    }
  }

  const handleTagToggle = (tag: string) => {
    if (tagFilter.includes(tag)) {
      onTagFilter(tagFilter.filter(t => t !== tag))
    } else {
      onTagFilter([...tagFilter, tag])
    }
  }

  const handleClearFilters = () => {
    onSearch('')
    onTypeFilter([])
    onTagFilter([])
    onStatusFilter('all')
  }

  const hasFilters = searchQuery || typeFilter.length > 0 || tagFilter.length > 0 || statusFilter !== 'all'

  return (
    <div className="p-4 border-b border-base-300 bg-base-100">
      <div className="flex flex-wrap gap-4 items-center">
        {/* Search Input */}
        <div className="flex-1 min-w-64">
          <div className="relative">
            <input
              type="text"
              placeholder="Search tools by name or description..."
              value={searchQuery}
              onChange={(e) => onSearch(e.target.value)}
              className="input input-bordered input-sm w-full pl-10 rounded-[var(--form-input-radius)] px-[var(--form-input-padding)] bg-[var(--form-input-bg)] border-[var(--form-input-border)] text-[var(--form-input-text)] focus:border-[var(--form-input-focus-border)] transition-all duration-[var(--button-transition)]"
            />
            <svg
              className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-readout"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
          </div>
        </div>

        {/* Type Filter Dropdown */}
        {types.length > 0 && (
          <div className="dropdown">
            <label tabIndex={0} className={`btn btn-sm ${typeFilter.length > 0 ? 'btn-active btn-selected' : 'btn-outline'}`}>
              Type
              {typeFilter.length > 0 && (
                <span className="badge badge-light badge-xs">
                  {typeFilter.length}
                </span>
              )}
            </label>
            <ul
              tabIndex={0}
              className="dropdown-content z-[1] menu p-2 shadow bg-base-100 rounded-box w-52"
            >
              {types.map(type => (
                <li key={type}>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={typeFilter.includes(type)}
                      onChange={() => handleTypeToggle(type)}
                      className="checkbox checkbox-sm checkbox-primary"
                    />
                    {type}
                  </label>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Tag Filter Dropdown */}
        <div className="dropdown">
          <label tabIndex={0} className={`btn btn-sm ${tagFilter.length > 0 ? 'btn-active btn-selected' : 'btn-outline'}`}>
            Tags
            {tagFilter.length > 0 && (
              <span className="badge badge-light badge-xs">
                {tagFilter.length}
              </span>
            )}
          </label>
          <ul
            tabIndex={0}
            className="dropdown-content z-[1] menu p-2 shadow bg-base-100 rounded-box w-64 max-h-96 overflow-y-auto"
          >
            <li className="menu-title">
              <span>Filter by Tags</span>
            </li>
            {KNOWN_TAGS.map(tag => (
              <li key={tag}>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={tagFilter.includes(tag)}
                    onChange={() => handleTagToggle(tag)}
                    className="checkbox checkbox-sm checkbox-primary"
                  />
                  <TagBadge tag={tag} size="sm" showTooltip={false} />
                </label>
              </li>
            ))}
          </ul>
        </div>

        {/* Status Filter */}
        <div className="btn-group">
          <button
            className={`btn btn-sm ${statusFilter === 'all' ? 'btn-active btn-selected' : 'btn-outline'}`}
            onClick={() => onStatusFilter('all')}
          >
            All
          </button>
          <button
            className={`btn btn-sm ${statusFilter === 'active' ? 'btn-active btn-selected' : 'btn-outline'}`}
            onClick={() => onStatusFilter('active')}
          >
            Active
          </button>
          <button
            className={`btn btn-sm ${statusFilter === 'inactive' ? 'btn-active btn-selected' : 'btn-outline'}`}
            onClick={() => onStatusFilter('inactive')}
          >
            Inactive
          </button>
        </div>

        {/* Clear Filters */}
        {hasFilters && (
          <button
            className="btn btn-error btn-outline btn-sm"
            onClick={handleClearFilters}
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Active Tag Filters Display */}
      {tagFilter.length > 0 && (
        <div className="flex gap-2 mt-3 flex-wrap">
          {tagFilter.map(tag => (
            <div key={tag} className="badge badge-secondary badge-outline gap-2">
              {tag}
              <div className="tooltip tooltip-top" data-tip="Remove tag filter">
                <button
                  onClick={() => handleTagToggle(tag)}
                  className="hover:text-error"
                  aria-label={`Remove ${tag} tag filter`}
                >
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
