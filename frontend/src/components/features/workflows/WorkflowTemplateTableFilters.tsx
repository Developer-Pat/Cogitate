interface Props {
  searchQuery: string
  categories: string[]
  types: string[]
  tags: string[]
  filterTags: string[]
  filterCategory: string
  filterType: string
  onSearch: (query: string) => void
  onCategoryFilter: (category: string) => void
  onTypeFilter: (type: string) => void
  onFilterTagsChange: (tags: string[]) => void
  onClear: () => void
  hasActiveFilters: boolean
}

export default function WorkflowTemplateTableFilters({
  searchQuery,
  categories,
  types,
  tags,
  filterTags,
  filterCategory,
  filterType,
  onSearch,
  onCategoryFilter,
  onTypeFilter,
  onFilterTagsChange,
  onClear,
  hasActiveFilters
}: Props) {
  return (
    <div className="p-3 border-b border-base-300 space-y-2">
      {/* Search row */}
      <div className="flex gap-2 items-center">
        <input
          type="text"
          placeholder="Search by name, description, or tag..."
          value={searchQuery}
          onChange={e => onSearch(e.target.value)}
          className="input input-bordered input-sm flex-1"
        />
        {hasActiveFilters && (
          <span className="tooltip tooltip-top" data-tip="Clear all filters">
            <button className="btn btn-sm btn-error btn-outline" onClick={onClear}>
              ✕ Clear
            </button>
          </span>
        )}
      </div>

      {/* Filter row */}
      <div className="flex gap-2 flex-wrap items-center">
        <span className="text-xs opacity-60">Filters:</span>

        {/* Category dropdown */}
        <select
          value={filterCategory}
          onChange={e => onCategoryFilter(e.target.value)}
          className="select select-bordered select-xs"
        >
          <option value="">All Categories</option>
          {categories.map(cat => (
            <option key={cat} value={cat}>{cat}</option>
          ))}
        </select>

        {/* Type dropdown */}
        <select
          value={filterType}
          onChange={e => onTypeFilter(e.target.value)}
          className="select select-bordered select-xs"
        >
          <option value="">All Types</option>
          {types.map(t => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>

        {/* Tag chips */}
        {tags.length > 0 && (
          <select
            value=""
            onChange={e => {
              if (e.target.value && !filterTags.includes(e.target.value)) {
                onFilterTagsChange([...filterTags, e.target.value])
              }
            }}
            className="select select-bordered select-xs"
          >
            <option value="">+ Tag</option>
            {tags.filter(t => !filterTags.includes(t)).map(tag => (
              <option key={tag} value={tag}>{tag}</option>
            ))}
          </select>
        )}

        {/* Active tag filters */}
        {filterTags.map(tag => (
          <span key={tag} className="badge badge-sm badge-primary badge-outline gap-1">
            {tag}
            <button
              className="cursor-pointer"
              onClick={() => onFilterTagsChange(filterTags.filter(t => t !== tag))}
            >
              ✕
            </button>
          </span>
        ))}
      </div>
    </div>
  )
}
