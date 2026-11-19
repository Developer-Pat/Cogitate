// import React from 'react'

interface AgentTableFiltersProps {
  searchQuery: string
  providers: string[]
  providerFilter: string[]
  statusFilter: 'all' | 'active' | 'inactive'
  onSearch: (query: string) => void
  onProviderFilter: (providers: string[]) => void
  onStatusFilter: (status: 'all' | 'active' | 'inactive') => void
}

export default function AgentTableFilters({
  searchQuery,
  providers,
  providerFilter,
  statusFilter,
  onSearch,
  onProviderFilter,
  onStatusFilter
}: AgentTableFiltersProps) {
  const handleProviderToggle = (provider: string) => {
    if (providerFilter.includes(provider)) {
      onProviderFilter(providerFilter.filter(p => p !== provider))
    } else {
      onProviderFilter([...providerFilter, provider])
    }
  }

  const handleClearFilters = () => {
    onSearch('')
    onProviderFilter([])
    onStatusFilter('all')
  }

  const hasFilters = searchQuery || providerFilter.length > 0 || statusFilter !== 'all'

  return (
    <div className="p-4 border-b border-base-300 bg-base-100">
      <div className="flex flex-wrap gap-4 items-center">
        {/* Search Input */}
        <div className="flex-1 min-w-64">
          <div className="relative">
            <input
              type="text"
              placeholder="Search agents by name or description..."
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

        {/* Provider Filter Dropdown */}
        {providers.length > 0 && (
          <div className="dropdown">
            <label tabIndex={0} className="btn btn-ghost btn-sm gap-2">
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
                />
              </svg>
              Provider
              {providerFilter.length > 0 && (
                <span className="badge badge-primary badge-xs">
                  {providerFilter.length}
                </span>
              )}
            </label>
            <ul
              tabIndex={0}
              className="dropdown-content z-[1] menu p-2 shadow bg-base-100 rounded-box w-52"
            >
              {providers.map(provider => (
                <li key={provider}>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={providerFilter.includes(provider)}
                      onChange={() => handleProviderToggle(provider)}
                      className="checkbox checkbox-sm checkbox-primary"
                    />
                    {provider}
                  </label>
                </li>
              ))}
            </ul>
          </div>
        )}

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
            className="btn btn-ghost btn-sm text-error"
            onClick={handleClearFilters}
          >
            Clear filters
          </button>
        )}
      </div>
    </div>
  )
}
