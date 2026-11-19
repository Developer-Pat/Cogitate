interface WorkflowTableFiltersProps {
  searchQuery: string
  tags: string[]
  filterTags: string[]
  onSearch: (query: string) => void
  onFilterTagsChange: (tags: string[]) => void
}

export default function WorkflowTableFilters({
  searchQuery,
  tags,
  filterTags,
  onSearch,
  onFilterTagsChange
}: WorkflowTableFiltersProps) {
  const handleTagToggle = (tag: string) => {
    if (filterTags.includes(tag)) {
      onFilterTagsChange(filterTags.filter(t => t !== tag))
    } else {
      onFilterTagsChange([...filterTags, tag])
    }
  }

  const handleClearFilters = () => {
    onSearch('')
    onFilterTagsChange([])
  }

  const hasFilters = searchQuery || filterTags.length > 0

  return (
    <div className="p-4 border-b border-base-300 bg-base-100">
      <div className="flex flex-wrap gap-4 items-center">
        {/* Search Input */}
        <div className="flex-1 min-w-64">
          <div className="relative">
            <input
              type="text"
              placeholder="Search workflow lists by name or description..."
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

        {/* Tag Filter Dropdown */}
        {tags.length > 0 && (
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
                  d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"
                />
              </svg>
              Tags
              {filterTags.length > 0 && (
                <span className="badge badge-primary badge-outline badge-xs">
                  {filterTags.length}
                </span>
              )}
            </label>
            <ul
              tabIndex={0}
              className="dropdown-content z-[1] menu p-2 shadow bg-base-100 rounded-box w-52"
            >
              {tags.map(tag => (
                <li key={tag}>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={filterTags.includes(tag)}
                      onChange={() => handleTagToggle(tag)}
                      className="checkbox checkbox-sm checkbox-primary"
                    />
                    {tag}
                  </label>
                </li>
              ))}
            </ul>
          </div>
        )}

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
