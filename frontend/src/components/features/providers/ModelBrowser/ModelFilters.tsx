/**
 * Model Filters Component
 *
 * Provides search and filter controls for model browsing.
 */

import React, { useState, useEffect } from 'react'
import { modelBrowserService, type CapabilityInfo, type ModelBrowserFilters } from '@/services/domains/providers/modelBrowserService'
import { frontendLoggingService } from '@/services/frontendLoggingService'

interface ModelFiltersProps {
  filters: ModelBrowserFilters
  onFilterChange: (filters: Partial<ModelBrowserFilters>) => void
  providerId?: number
}

/**
 * Model Filters Component
 */
const ModelFilters: React.FC<ModelFiltersProps> = ({
  filters,
  onFilterChange,
  providerId,
}) => {
  const [searchTerm, setSearchTerm] = useState(filters.search || '')
  const [capabilities, setCapabilities] = useState<CapabilityInfo[]>([])
  const [loadingCapabilities, setLoadingCapabilities] = useState(false)

  /**
   * Load available capabilities
   */
  useEffect(() => {
    if (providerId) {
      loadCapabilities()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [providerId])

  const loadCapabilities = async () => {
    if (!providerId) return

    setLoadingCapabilities(true)
    try {
      const response = await modelBrowserService.getCapabilities(providerId)
      if (response.data) {
        setCapabilities(response.data.capabilities)
      }
    } catch (error) {
      frontendLoggingService.error('ModelFilters', 'Failed to load capabilities', error)
    } finally {
      setLoadingCapabilities(false)
    }
  }

  /**
   * Handle search input change
   */
  const handleSearchChange = (value: string) => {
    setSearchTerm(value)
    // Apply search immediately (parent handles debouncing)
    onFilterChange({ search: value || undefined })
  }

  /**
   * Handle search submit (on Enter)
   */
  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    // Already applied on change, but ensure it's set
    onFilterChange({ search: searchTerm || undefined })
  }

  /**
   * Handle capability toggle
   */
  const handleCapabilityToggle = (capabilityId: string) => {
    const currentCapabilities = filters.capabilities || []
    const newCapabilities = currentCapabilities.includes(capabilityId)
      ? currentCapabilities.filter(c => c !== capabilityId)
      : [...currentCapabilities, capabilityId]

    onFilterChange({
      capabilities: newCapabilities.length > 0 ? newCapabilities : undefined,
    })
  }

  /**
   * Handle free only toggle
   */
  const handleFreeOnlyToggle = () => {
    onFilterChange({ free_only: !filters.free_only })
  }

  /**
   * Handle sort change
   */
  const handleSortChange = (sortBy: string) => {
    // Toggle sort order if same field
    const newOrder = filters.sort_by === sortBy && filters.sort_order === 'asc' ? 'desc' : 'asc'
    onFilterChange({ sort_by: sortBy, sort_order: newOrder })
  }

  /**
   * Clear all filters
   */
  const handleClearFilters = () => {
    setSearchTerm('')
    onFilterChange({
      search: undefined,
      capabilities: undefined,
      free_only: false,
      sort_by: 'name',
      sort_order: 'asc',
    })
  }

  return (
    <div className="card bg-base-200 shadow-md rounded-lg p-4">
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        {/* Search */}
        <form onSubmit={handleSearchSubmit} className="flex-1">
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <svg className="h-5 w-5 text-readout" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => handleSearchChange(e.target.value)}
              placeholder="Search models by name, ID, or description..."
              className="input input-bordered w-full pl-10 pr-12"
            />
            {searchTerm && (
              <button
                type="button"
                onClick={() => {
                  setSearchTerm('')
                  onFilterChange({ search: undefined })
                }}
                className="absolute inset-y-0 right-0 pr-3 flex items-center text-base-content/50 hover:text-base-content"
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>
        </form>

        {/* Sort Dropdown */}
        <div className="flex items-center space-x-2">
          <span className="text-sm text-readout">Sort by:</span>
          <div className="dropdown">
            <label tabIndex={0} className="btn btn-sm btn-outline">
              {filters.sort_by === 'name' && 'Name'}
              {filters.sort_by === 'context_length' && 'Context Length'}
              {filters.sort_by === 'pricing_prompt' && 'Price'}
              {filters.sort_by === 'provider' && 'Provider'}
              {filters.sort_order === 'asc' ? ' ↑' : ' ↓'}
            </label>
            <ul tabIndex={0} className="dropdown-content z-[1] menu p-2 shadow bg-base-100 rounded-box w-52">
              <li>
                <a onClick={() => handleSortChange('name')}>
                  Name {filters.sort_by === 'name' && (filters.sort_order === 'asc' ? '↑' : '↓')}
                </a>
              </li>
              <li>
                <a onClick={() => handleSortChange('context_length')}>
                  Context Length {filters.sort_by === 'context_length' && (filters.sort_order === 'asc' ? '↑' : '↓')}
                </a>
              </li>
              <li>
                <a onClick={() => handleSortChange('pricing_prompt')}>
                  Price {filters.sort_by === 'pricing_prompt' && (filters.sort_order === 'asc' ? '↑' : '↓')}
                </a>
              </li>
              <li>
                <a onClick={() => handleSortChange('provider')}>
                  Provider {filters.sort_by === 'provider' && (filters.sort_order === 'asc' ? '↑' : '↓')}
                </a>
              </li>
            </ul>
          </div>
        </div>

        {/* Free Only Toggle */}
        <label className="label cursor-pointer space-x-2">
          <input
            type="checkbox"
            checked={filters.free_only || false}
            onChange={handleFreeOnlyToggle}
            className="checkbox checkbox-sm checkbox-primary"
          />
          <span className="label-text">Free models only</span>
        </label>

        {/* Clear Filters Button */}
        {(filters.search || filters.capabilities?.length || filters.free_only) && (
          <button
            onClick={handleClearFilters}
            className="btn btn-sm btn-error btn-outline"
          >
            Clear Filters
          </button>
        )}
      </div>

      {/* Capability Filters */}
      {capabilities.length > 0 && (
        <div className="mt-4 pt-4 border-t border-base-300">
          <div className="flex items-center space-x-2 mb-2">
            <span className="text-sm font-medium text-base-content">Capabilities:</span>
            {loadingCapabilities && (
              <span className="loading loading-spinner loading-xs"></span>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            {capabilities.map((cap) => {
              const isSelected = filters.capabilities?.includes(cap.id)
              return (
                <button
                  key={cap.id}
                  onClick={() => handleCapabilityToggle(cap.id)}
                  className={`
                    px-3 py-1 text-sm rounded-full border transition-colors
                    ${isSelected
                      ? 'bg-primary text-primary-content border-primary'
                      : 'bg-base-100 text-base-content border-base-300 hover:border-primary'
                    }
                  `}
                >
                  {cap.name}
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

export default ModelFilters
