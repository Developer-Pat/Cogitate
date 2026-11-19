import { useState, useMemo, useEffect } from 'react'
import { frontendLoggingService } from '../services/frontendLoggingService'
import type { LogEntry } from '../types'

const FILTERS_STORAGE_KEY = 'cogitate_logs_filters'

export interface LogsFilters {
  selectedLevel: string
  searchTerm: string
  sourceType: 'all' | 'frontend' | 'backend'
}

export interface UseLogsFiltersReturn {
  filters: LogsFilters
  filteredLogs: LogEntry[]
  setSelectedLevel: (level: string) => void
  setSearchTerm: (term: string) => void
  setSourceType: (type: 'all' | 'frontend' | 'backend') => void
}

function loadFiltersFromStorage(): LogsFilters | null {
  try {
    const stored = sessionStorage.getItem(FILTERS_STORAGE_KEY)
    if (stored) {
      return JSON.parse(stored)
    }
  } catch (err) {
    frontendLoggingService.warning('useLogsFilters', 'Failed to load from sessionStorage', err as unknown as Record<string, unknown>)
  }
  return null
}

function saveFiltersToStorage(filters: LogsFilters) {
  try {
    sessionStorage.setItem(FILTERS_STORAGE_KEY, JSON.stringify(filters))
  } catch (err) {
    frontendLoggingService.warning('useLogsFilters', 'Failed to save to sessionStorage', err as unknown as Record<string, unknown>)
  }
}

export function useLogsFilters(
  logs: LogEntry[]
): UseLogsFiltersReturn {
  // Load initial state from sessionStorage
  const storedFilters = loadFiltersFromStorage()
  
  const [filters, setFilters] = useState<LogsFilters>({
    selectedLevel: storedFilters?.selectedLevel || 'all',
    searchTerm: storedFilters?.searchTerm || '',
    sourceType: storedFilters?.sourceType || 'all'  // NEW
  })

  // Persist filters to sessionStorage whenever they change
  useEffect(() => {
    saveFiltersToStorage(filters)
  }, [filters])

  const setSelectedLevel = (level: string) => {
    setFilters(prev => ({ ...prev, selectedLevel: level }))
  }

  const setSearchTerm = (term: string) => {
    setFilters(prev => ({ ...prev, searchTerm: term }))
  }

  const setSourceType = (type: 'all' | 'frontend' | 'backend') => {
    setFilters(prev => ({ ...prev, sourceType: type }))
  }

  const filteredLogs = useMemo(() => {
    return logs.filter(log => {
      // Level filter
      const matchesLevel = filters.selectedLevel === 'all' || log.level === filters.selectedLevel

      // Search filter
      const matchesSearch = log.message.toLowerCase().includes(filters.searchTerm.toLowerCase()) ||
                           log.source.toLowerCase().includes(filters.searchTerm.toLowerCase())

      // Source type filter (frontend/backend)
      // Frontend logs have user_agent (browser), backend logs have null/undefined user_agent
      const isFrontend = log.log_type === 'frontend' ||
                         log.source?.toLowerCase().includes('navigation') ||
                         log.source?.toLowerCase().includes('performance') ||
                         log.source?.toLowerCase().includes('error') ||
                         !!log.user_agent  // Check for truthy value (not just defined)
      const matchesSourceType = filters.sourceType === 'all' ||
                                (filters.sourceType === 'frontend' && isFrontend) ||
                                (filters.sourceType === 'backend' && !isFrontend)

      return matchesLevel && matchesSearch && matchesSourceType
    })
  }, [logs, filters])

  return {
    filters,
    filteredLogs,
    setSelectedLevel,
    setSearchTerm,
    setSourceType  // NEW
  }
}