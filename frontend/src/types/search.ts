/**
 * Advanced Search and Filtering Types for Cogitate Frontend
 */

// Search result types
export type SearchResultType = 
  | 'agent' 
  | 'workflow' 
  | 'provider' 
  | 'session' 
  | 'log' 
  | 'configuration' 
  | 'system';

export interface SearchResult {
  id: string;
  type: SearchResultType;
  title: string;
  description: string;
  category: string;
  relevance: number;
  metadata: Record<string, unknown>;
  highlight?: {
    title?: string[];
    description?: string[];
    content?: string[];
  };
  url?: string;
  timestamp?: string;
}

export interface SearchSuggestion {
  id: string;
  text: string;
  type: SearchResultType;
  category: string;
  relevance: number;
  metadata?: Record<string, unknown>;
}

// Global search state
export interface GlobalSearchState {
  query: string;
  results: SearchResult[];
  suggestions: SearchSuggestion[];
  isLoading: boolean;
  error: string | null;
  hasSearched: boolean;
  selectedCategory?: SearchResultType;
  filters: SearchFilters;
}

// Advanced filter types
export interface SearchFilters {
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
  customFilters?: Record<string, unknown>;
}

export interface FilterGroup {
  id: string;
  name: string;
  operator: 'AND' | 'OR';
  filters: FilterCondition[];
  groups?: FilterGroup[];
}

export interface FilterCondition {
  id: string;
  field: string;
  operator: FilterOperator;
  value: unknown;
  type: FilterType;
}

export type FilterOperator = 
  | 'equals' 
  | 'contains' 
  | 'startsWith' 
  | 'endsWith' 
  | 'greaterThan' 
  | 'lessThan' 
  | 'between' 
  | 'in' 
  | 'notIn';

export type FilterType = 
  | 'text' 
  | 'number' 
  | 'date' 
  | 'select' 
  | 'multi-select' 
  | 'boolean';

// Search history
export interface SearchHistoryItem {
  id: string;
  query: string;
  timestamp: string;
  resultCount: number;
  filters?: SearchFilters;
  categories?: SearchResultType[];
}

// Search configuration
export interface SearchConfig {
  debounceMs: number;
  maxResults: number;
  maxSuggestions: number;
  maxHistoryItems: number;
  enableHighlighting: boolean;
  enableFuzzySearch: boolean;
  searchableFields: Record<SearchResultType, string[]>;
}

// Search performance metrics
export interface SearchMetrics {
  queryTime: number;
  resultCount: number;
  cacheHits: number;
  cacheMisses: number;
  indexingTime?: number;
}

// Search index types
export interface SearchIndexEntry {
  id: string;
  type: SearchResultType;
  title: string;
  description: string;
  content: string;
  metadata: Record<string, unknown>;
  tags: string[];
  timestamp: string;
  boost: number;
}

export interface SearchIndex {
  entries: SearchIndexEntry[];
  lastUpdated: string;
  size: number;
}

// Component props
export interface GlobalSearchProps {
  placeholder?: string;
  className?: string;
  onSearch?: (query: string, filters?: SearchFilters) => void;
  onResultSelect?: (result: SearchResult) => void;
  maxSuggestions?: number;
  autoFocus?: boolean;
  compact?: boolean;
}

export interface SearchSuggestionsProps {
  suggestions: SearchSuggestion[];
  query: string;
  isLoading: boolean;
  onSuggestionSelect: (suggestion: SearchSuggestion) => void;
  onClear: () => void;
  maxVisible?: number;
  className?: string;
}

export interface SearchHistoryProps {
  history: SearchHistoryItem[];
  onHistorySelect: (item: { query: string; filters?: SearchFilters }) => void;
  onClearHistory: () => void;
  maxVisible?: number;
  className?: string;
}

export interface AdvancedFiltersProps {
  filters: SearchFilters;
  onFiltersChange: (filters: SearchFilters) => void;
  availableCategories?: SearchResultType[];
  className?: string;
  compact?: boolean;
}

// Hook return types
export interface UseGlobalSearchReturn {
  query: string;
  results: SearchResult[];
  suggestions: SearchSuggestion[];
  isLoading: boolean;
  error: string | null;
  search: (query: string, filters?: SearchFilters) => void;
  clearSearch: () => void;
  selectSuggestion: (suggestion: SearchSuggestion) => void;
  metrics: SearchMetrics;
}

export interface UseFilteringReturn {
  filters: SearchFilters;
  filterGroups: FilterGroup[];
  activeFilterCount: number;
  updateFilter: (key: string, value: unknown) => void;
  addFilterGroup: (group: FilterGroup) => void;
  removeFilterGroup: (groupId: string) => void;
  clearFilters: () => void;
  applyFilters: (data: unknown[]) => unknown[];
}

export interface UseSearchHistoryReturn {
  history: SearchHistoryItem[];
  addToHistory: (query: string, resultCount: number, filters?: SearchFilters) => void;
  clearHistory: () => void;
  removeFromHistory: (id: string) => void;
  getRecentSearches: (limit?: number) => SearchHistoryItem[];
}

// Utility types for search operations
export interface SearchMatch {
  field: string;
  value: string;
  positions: number[];
  score: number;
}

export interface SearchScore {
  baseScore: number;
  fieldBoosts: Record<string, number>;
  relevance: number;
  total: number;
}

// Default configurations
export const DEFAULT_SEARCH_CONFIG: SearchConfig = {
  debounceMs: 300,
  maxResults: 50,
  maxSuggestions: 10,
  maxHistoryItems: 20,
  enableHighlighting: true,
  enableFuzzySearch: true,
  searchableFields: {
    agent: ['name', 'type', 'capabilities', 'description'],
    workflow: ['name', 'description', 'steps.name', 'triggers.type'],
    provider: ['name', 'type', 'status', 'configuration'],
    session: ['id', 'status', 'context'],
    log: ['message', 'source', 'level', 'context'],
    configuration: ['name', 'value', 'description'],
    system: ['name', 'status', 'version', 'description']
  }
};