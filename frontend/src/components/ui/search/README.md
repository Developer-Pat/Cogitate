# Advanced Search & Filtering Components

A comprehensive set of React components and hooks for implementing advanced search and filtering capabilities across the Cogitate application.

## Overview

This package provides:

- **Global Search**: Unified search across all system components
- **Advanced Filtering**: Complex filtering with AND/OR logic
- **Search Suggestions**: Real-time autocomplete with keyboard navigation
- **Search History**: Persistent search history with filters
- **Performance Optimized**: Debounced search, caching, and efficient filtering

## Components

### GlobalSearch

The main search component that combines all search functionality.

```tsx
import { GlobalSearch } from './components/ui/search';

function MyComponent() {
  const handleSearch = (query: string, filters?: SearchFilters) => {
    console.log('Search:', query, filters);
  };

  const handleResultSelect = (result: SearchResult) => {
    console.log('Selected:', result);
  };

  return (
    <GlobalSearch
      placeholder="Search across the system..."
      onSearch={handleSearch}
      onResultSelect={handleResultSelect}
      maxSuggestions={8}
      showHistory={true}
      showFilters={true}
      compact={false}
      autoFocus={true}
    />
  );
}
```

**Props:**
- `placeholder` (string): Search input placeholder text
- `onSearch` (function): Called when search is executed
- `onResultSelect` (function): Called when a result is selected
- `maxSuggestions` (number): Maximum number of suggestions to show
- `showHistory` (boolean): Show search history dropdown
- `showFilters` (boolean): Show advanced filters panel
- `compact` (boolean): Use compact styling
- `autoFocus` (boolean): Auto-focus the search input

### SearchSuggestions

Displays search suggestions with highlighting and keyboard navigation.

```tsx
import { SearchSuggestions } from './components/ui/search';

function MyComponent() {
  const suggestions = [/* ... */];
  
  return (
    <SearchSuggestions
      suggestions={suggestions}
      query="search query"
      isLoading={false}
      onSuggestionSelect={(suggestion) => console.log(suggestion)}
      onClear={() => console.log('clear')}
      maxVisible={10}
    />
  );
}
```

### SearchHistory

Displays recent searches with metadata.

```tsx
import { SearchHistory } from './components/ui/search';

function MyComponent() {
  const history = [/* ... */];
  
  return (
    <SearchHistory
      history={history}
      onHistorySelect={(item) => console.log(item)}
      onClearHistory={() => console.log('clear history')}
      maxVisible={5}
    />
  );
}
```

### AdvancedFilters

Advanced filtering panel with multiple filter types.

```tsx
import { AdvancedFilters } from './components/ui/search';

function MyComponent() {
  const [filters, setFilters] = useState({});
  
  return (
    <AdvancedFilters
      filters={filters}
      onFiltersChange={setFilters}
      availableCategories={['agent', 'workflow', 'provider']}
      compact={false}
    />
  );
}
```

## Hooks

### useGlobalSearch

Hook for managing global search state and operations.

```tsx
import { useGlobalSearch } from '../hooks/useGlobalSearch';

function MyComponent() {
  const {
    query,
    results,
    suggestions,
    isLoading,
    error,
    search,
    clearSearch,
    selectSuggestion,
    metrics,
  } = useGlobalSearch();

  return (
    <div>
      {/* Use search state and functions */}
    </div>
  );
}
```

### useSearchHistory

Hook for managing search history with localStorage persistence.

```tsx
import { useSearchHistory } from '../hooks/useSearchHistory';

function MyComponent() {
  const {
    history,
    addToHistory,
    clearHistory,
    removeFromHistory,
    getRecentSearches,
  } = useSearchHistory();

  return (
    <div>
      {/* Use history state and functions */}
    </div>
  );
}
```

### useFiltering

Hook for advanced filtering with AND/OR logic.

```tsx
import { useFiltering } from '../hooks/useFiltering';

function MyComponent() {
  const {
    filters,
    filterGroups,
    activeFilterCount,
    updateFilter,
    addFilterGroup,
    removeFilterGroup,
    clearFilters,
    applyFilters,
  } = useFiltering();

  const filteredData = applyFilters(originalData);

  return (
    <div>
      {/* Use filtering state and functions */}
    </div>
  );
}
```

## Types

### SearchResult

```tsx
interface SearchResult {
  id: string;
  type: SearchResultType; // 'agent' | 'workflow' | 'provider' | etc.
  title: string;
  description: string;
  category: string;
  relevance: number; // 0-1
  metadata: Record<string, any>;
  highlight?: {
    title?: string[];
    description?: string[];
    content?: string[];
  };
  timestamp?: string;
}
```

### SearchFilters

```tsx
interface SearchFilters {
  categories?: SearchResultType[];
  dateRange?: {
    start: string;
    end: string;
  };
  status?: string[];
  tags?: string[];
  providers?: string[];
  capabilities?: string[];
  workflowTypes?: string[];
  logLevels?: string[];
  customFilters?: Record<string, any>;
}
```

### FilterGroup

```tsx
interface FilterGroup {
  id: string;
  name: string;
  operator: 'AND' | 'OR';
  filters: FilterCondition[];
  groups?: FilterGroup[];
}

interface FilterCondition {
  id: string;
  field: string;
  operator: FilterOperator; // 'equals' | 'contains' | 'greaterThan' | etc.
  value: any;
  type: FilterType; // 'text' | 'number' | 'date' | etc.
}
```

## Utility Functions

### searchUtils

```tsx
import { searchUtils } from '../utils/searchUtils';

// Check if result matches query
const matches = searchUtils.matchesQuery(result, query);

// Calculate relevance score
const relevance = searchUtils.calculateRelevance(result, query);

// Apply filters to results
const filtered = searchUtils.applyFilters(results, filters);

// Sort results
const sorted = searchUtils.sortResults(results, 'relevance');

// Generate suggestions
const suggestions = searchUtils.generateSuggestions(query, history);

// Debounce function
const debouncedSearch = searchUtils.debounce(searchFunction, 300);
```

## Integration Examples

### Basic Integration

```tsx
import { GlobalSearch, useGlobalSearch, useSearchHistory } from './search';

function SearchPage() {
  const { results, search, isLoading } = useGlobalSearch();
  const { addToHistory } = useSearchHistory();

  const handleSearch = (query: string, filters?: SearchFilters) => {
    search(query, filters);
    addToHistory(query, results.length, filters);
  };

  return (
    <div>
      <GlobalSearch onSearch={handleSearch} />
      
      {isLoading && <div>Loading...</div>}
      
      <div className="results">
        {results.map(result => (
          <SearchResultCard key={result.id} result={result} />
        ))}
      </div>
    </div>
  );
}
```

### Advanced Filtering Integration

```tsx
import { useFiltering } from '../hooks/useFiltering';

function DataTable({ data }) {
  const { filters, applyFilters, updateFilter } = useFiltering();

  const filteredData = applyFilters(data);

  return (
    <div>
      <AdvancedFilters
        filters={filters}
        onFiltersChange={updateFilter}
      />
      
      <table>
        {/* Render filtered data */}
      </table>
    </div>
  );
}
```

### Custom Search Implementation

```tsx
import { searchUtils } from '../utils/searchUtils';

function CustomSearch({ data }) {
  const [query, setQuery] = useState('');
  const [filters, setFilters] = useState({});
  
  const results = useMemo(() => {
    let filtered = data;
    
    // Apply search query
    if (query) {
      filtered = filtered.filter(item => 
        searchUtils.matchesQuery(item, query)
      );
    }
    
    // Apply filters
    filtered = searchUtils.applyFilters(filtered, filters);
    
    // Sort by relevance
    return searchUtils.sortResults(filtered, 'relevance');
  }, [data, query, filters]);

  return (
    <div>
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search..."
      />
      
      <AdvancedFilters
        filters={filters}
        onFiltersChange={setFilters}
      />
      
      <div className="results">
        {results.map(item => (
          <div key={item.id}>{item.title}</div>
        ))}
      </div>
    </div>
  );
}
```

## Performance Features

- **Debounced Search**: 300ms debounce by default
- **Search Indexing**: Utility functions for creating search indices
- **Efficient Filtering**: Optimized filter application
- **Local Storage**: Persistent search history
- **Keyboard Navigation**: Full keyboard support for accessibility
- **Responsive Design**: Works on all screen sizes

## Accessibility

- Full keyboard navigation support
- ARIA labels and roles
- Screen reader compatible
- Focus management
- High contrast support

## Browser Support

- Chrome 80+
- Firefox 75+
- Safari 13+
- Edge 80+

## License

MIT