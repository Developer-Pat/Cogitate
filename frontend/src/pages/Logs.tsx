import { useState, useEffect } from 'react'
import { useQueryClient, useMutation } from '@tanstack/react-query'
import { useLogs, useLogStats } from '../hooks'
import { useLogsFilters } from '../hooks/useLogsFilters'
import { useDebounce } from '../hooks/useDebounce'
import { usePageTitle } from '../hooks/usePageTitle'
import { ErrorBoundary } from '../components/ErrorBoundary'
import { PageBanner } from '../components/ui/PageBanner'
import { PageContainer } from '../components/ui/PageContainer'
import { HelpButton } from '../components/help'
import { ExaPromptFlyout } from '../components/features/agentInteraction/ExaPromptFlyout'
import LogFilters from '../components/logs/LogFilters'
import LogsTable from '../components/logs/LogsTable'
import LogDetailsModal from '../components/logs/LogDetailsModal'
import { frontendLoggingService, apiClient } from '../services'
import { useNotificationStore } from '../stores/notificationStore'
import type { LogEntry } from '../types'

export default function Logs() {
  usePageTitle('Logs', 'View and analyze system logs')

  const [selectedLog, setSelectedLog] = useState<LogEntry | null>(null)
  const [filtersOpen, setFiltersOpen] = useState(false)

  // Search state
  const [searchTerm, setSearchTerm] = useState('')
  const debouncedSearchTerm = useDebounce(searchTerm, 300)

  // Time range filters
  const [fromTime, setFromTime] = useState('')
  const [toTime, setToTime] = useState('')
  const [timePreset, setTimePreset] = useState<string>('all')
  const [showAdvancedTime, setShowAdvancedTime] = useState(false)
  
  // Handle preset changes
  const handleTimePresetChange = (preset: string) => {
    setTimePreset(preset)
    const now = new Date()
    let from = ''
    
    switch (preset) {
      case '1h':
        from = new Date(now.getTime() - 60 * 60 * 1000).toISOString().slice(0, 16)
        break
      case '6h':
        from = new Date(now.getTime() - 6 * 60 * 60 * 1000).toISOString().slice(0, 16)
        break
      case '12h':
        from = new Date(now.getTime() - 12 * 60 * 60 * 1000).toISOString().slice(0, 16)
        break
      case '24h':
        from = new Date(now.getTime() - 24 * 60 * 60 * 1000).toISOString().slice(0, 16)
        break
      case '7d':
        from = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString().slice(0, 16)
        break
      default:
        from = ''
    }
    
    const to = now.toISOString().slice(0, 16)
    setFromTime(from)
    setToTime(to)
  }

  // Source filter (specific source like ProfileService, Performance, etc.)
  const [selectedSource, setSelectedSource] = useState<string>('all')
  
  // Client-side pagination for filtered logs
  const [pageSize, setPageSize] = useState<number>(50)
  const [currentPage, setCurrentPage] = useState(1)

  // Data hooks - fetch up to 1000 logs for client-side filtering
  const {
    data: logsData,
    isLoading: logsLoading,
    error: logsError,
    refetch: refetchLogs
  } = useLogs({
    page: 1, // Always fetch from page 1
    page_size: 1000, // Get up to 1000 logs for client-side filtering
    limit: 1000,
    search: debouncedSearchTerm || undefined,
    from: fromTime || undefined,
    to: toTime || undefined,
    source: selectedSource !== 'all' ? selectedSource : undefined
  }) as {
    data: { data: LogEntry[]; pagination?: { total?: number }; has_more?: boolean } | null;
    isLoading: boolean;
    error: Error | null;
    refetch: () => void;
  };

  // Get stats for status indicator
  const { data: statsData } = useLogStats()

  // Mutations for actions
  const queryClient = useQueryClient()

  const clearFrontendLogsMutation = useMutation({
    mutationFn: async () => {
      // Use the new file-based endpoint to clear frontend logs
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 5000)

      try {
        const result = await apiClient.delete<{ deleted: string[]; errors: string[]; status: string }>(
          '/api/v1/logs/file/clear?frontend=true',
          { signal: controller.signal }
        )
        clearTimeout(timeoutId)
        if (result.data?.status !== 'success') {
          throw new Error('Failed to clear frontend logs')
        }
        return result.data
      } catch (error) {
        clearTimeout(timeoutId)
        throw error
      }
    },
    onSuccess: async () => {
      frontendLoggingService.info('LogsActions', '🗑️ Frontend logs cleared!')
      // Invalidate and refetch immediately
      await queryClient.invalidateQueries({
        queryKey: ['logs']
      })
      await queryClient.invalidateQueries({
        queryKey: ['log-stats']
      })
      // Force a refetch
      refetchLogs()
    },
    onError: (error: Error) => {
      frontendLoggingService.error('LogsActions', `❌ Failed to clear frontend logs: ${error.message}`)
    }
  })

  const clearAllLogsMutation = useMutation({
    mutationFn: async () => {
      // Clear ALL log files (frontend + backend)
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 5000)

      try {
        // Use file-based endpoint to clear BOTH frontend and backend logs
        const result = await apiClient.delete<{ deleted: string[]; errors: string[]; status: string }>(
          '/api/v1/logs/file/clear?frontend=true&backend=true',
          { signal: controller.signal }
        )
        clearTimeout(timeoutId)
        if (result.data?.status !== 'success') {
          throw new Error('Failed to clear all logs')
        }
        return result.data
      } catch (error) {
        clearTimeout(timeoutId)
        throw error
      }
    },
    onSuccess: async (result: { deleted: string[] }) => {
      frontendLoggingService.info('LogsActions', `🗑️ Cleared ALL logs: ${result.deleted.join(', ')}`)
      // Invalidate and refetch immediately
      await queryClient.invalidateQueries({
        queryKey: ['logs']
      })
      await queryClient.invalidateQueries({
        queryKey: ['log-stats']
      })
      // Force a refetch
      refetchLogs()
    },
    onError: (error: Error) => {
      frontendLoggingService.error('LogsActions', `❌ Failed to clear logs: ${error.message}`)
    }
  })

  const clearArchivesMutation = useMutation({
    mutationFn: async () => {
      // Clear archived log files only
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 5000)

      try {
        const result = await apiClient.delete<{ deleted: string[]; errors: string[]; status: string }>(
          '/api/v1/logs/file/clear?archives=true',
          { signal: controller.signal }
        )
        clearTimeout(timeoutId)
        if (result.data?.status !== 'success') {
          throw new Error('Failed to clear archives')
        }
        return result.data
      } catch (error) {
        clearTimeout(timeoutId)
        throw error
      }
    },
    onSuccess: async (result: { deleted: string[] }) => {
      frontendLoggingService.info('LogsActions', `🗑️ Cleared ${result.deleted.length} archive files`)
      // Invalidate and refetch immediately
      await queryClient.invalidateQueries({
        queryKey: ['log-stats']
      })
    },
    onError: (error: Error) => {
      frontendLoggingService.error('LogsActions', `❌ Failed to clear archives: ${error.message}`)
    }
  })

  const clearBackendLogsMutation = useMutation({
    mutationFn: async () => {
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 5000)

      try {
        const result = await apiClient.delete<{ deleted: string[]; errors: string[]; status: string }>(
          '/api/v1/logs/file/clear?backend=true',
          { signal: controller.signal }
        )
        clearTimeout(timeoutId)
        if (result.data?.status !== 'success') {
          throw new Error('Failed to clear backend logs')
        }
        return result.data
      } catch (error) {
        clearTimeout(timeoutId)
        throw error
      }
    },
    onSuccess: async () => {
      frontendLoggingService.info('LogsActions', '🗑️ Backend logs cleared!')
      await queryClient.invalidateQueries({ queryKey: ['logs'] })
      await queryClient.invalidateQueries({ queryKey: ['log-stats'] })
      refetchLogs()
    },
    onError: (error: Error) => {
      frontendLoggingService.error('LogsActions', `❌ Failed to clear backend logs: ${error.message}`)
    }
  })

  const addNotification = useNotificationStore((state) => state.addNotification)

  // The test generates a full level spread (DEBUG..CRITICAL) — every
  // filter sees SOME of it, so the notice is always a plain success
  // telling the user what landed + where to look.
  const notifyTestGenerated = (what: string) => {
    addNotification({
      type: 'success',
      title: 'Test logs generated',
      message: `${what} — DEBUG through CRITICAL. Check the top of the table (switch the level filter to All to see the full spread).`,
      duration: 6000,
    })
  }

  const testLogMutations = {
    all: useMutation({ mutationFn: async () => { const r = await apiClient.post('/api/v1/logs/test', {}); if (r.error) throw new Error('Failed'); return r.data; }, onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['log-stats'] }); queryClient.invalidateQueries({ queryKey: ['logs'] }); refetchLogs(); notifyTestGenerated('10 test entries written (5 each to frontend.log + app.log)'); } }),
    frontend: useMutation({ mutationFn: async () => { const r = await apiClient.post('/api/v1/logs/test/frontend', {}); if (r.error) throw new Error('Failed'); return r.data; }, onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['log-stats'] }); queryClient.invalidateQueries({ queryKey: ['logs'] }); refetchLogs(); notifyTestGenerated('5 test entries written to frontend.log'); } }),
    backend: useMutation({ mutationFn: async () => { const r = await apiClient.post('/api/v1/logs/test/backend', {}); if (r.error) throw new Error('Failed'); return r.data; }, onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['log-stats'] }); queryClient.invalidateQueries({ queryKey: ['logs'] }); refetchLogs(); notifyTestGenerated('5 test entries written to app.log'); } }),
  };

  // Filter management
  // logsData structure: PaginatedResponse { data: LogEntry[], pagination, has_more }
  const logsArray = logsData?.data || []

  
  // Extract unique sources from logs for the dropdown
  const availableSources = Array.from(
    new Set(logsArray.map(log => log.source).filter(Boolean))
  ).sort()
  
  // Apply filters client-side
  const {
    filters,
    filteredLogs,
    setSelectedLevel,
    setSourceType
  } = useLogsFilters(logsArray)

  // The Filters expander's badge count (2026-09-06): any non-default
  // filter state = an active filter.
  const activeFilterCount =
    (filters.selectedLevel !== 'all' ? 1 : 0) +
    (searchTerm ? 1 : 0) +
    (filters.sourceType !== 'all' ? 1 : 0) +
    (selectedSource !== 'all' ? 1 : 0) +
    (timePreset !== 'all' ? 1 : 0) +
    (fromTime || toTime ? 1 : 0)
  
  // Reset to page 1 when filters change
  useEffect(() => {
    setCurrentPage(1)
  }, [debouncedSearchTerm, selectedSource, filters.sourceType, timePreset])
  
  // Apply client-side pagination to filtered logs
  const totalPages = Math.ceil(filteredLogs.length / pageSize) || 1
  const safeCurrentPage = Math.min(currentPage, totalPages)
  const startIndex = (safeCurrentPage - 1) * pageSize
  const endIndex = startIndex + pageSize
  const paginatedLogs = filteredLogs.slice(startIndex, endIndex)
  
  const hasPrevPage = safeCurrentPage > 1
  const hasNextPage = safeCurrentPage < totalPages
  
  // Pagination handlers
  const handlePrevPage = () => {
    if (hasPrevPage) {
      setCurrentPage(prev => prev - 1)
    }
  }

  const handleNextPage = () => {
    if (hasNextPage) {
      setCurrentPage(prev => prev + 1)
    }
  }

  const handlePageChange = (page: number) => {
    if (page >= 1 && page <= totalPages) {
      setCurrentPage(page)
    }
  }

  const handleLogSelect = (log: LogEntry) => {
    setSelectedLog(log)
  }

  const handleModalClose = () => {
    setSelectedLog(null)
  }

  // Determine log source status
  // Note: With file-based logging, stats show file sizes in MB, not counts
  const backendLogsSize = (statsData as Record<string, unknown>)?.backendLogs as number || 0
  const frontendLogsSize = (statsData as Record<string, unknown>)?.frontendLogs as number || 0
  const totalSize = (statsData as Record<string, unknown>)?.total as number || 0
  
  // Calculate active logs (excluding archives)
  const activeSize = backendLogsSize + frontendLogsSize
  const archiveSize = totalSize - activeSize
  
  const isBackendConnected = statsData !== undefined && statsData !== null
  const isFrontendActive = frontendLogsSize > 0

  return (
    <ErrorBoundary>
      <PageContainer>
        {/* Page Header */}
        <div className="flex items-center justify-between mb-4">
          {/* hideCommand: the Exa pill rides THIS page's button group instead
              of the banner's own right edge. The widget is app-wide chrome and
              PageBanner seats it at the banner's right edge — but the banner
              shrinks to its content, so inside a justify-between row the pill
              lands beside the TITLE (page-left), and its 440px panel opens
              leftward from there, straight under the nav panel. In the button
              group it sits with its neighbours and the panel opens into the
              page. */}
          <PageBanner
            title="Logs"
            tooltip="Monitor and analyze system events and messages"
            hideCommand
          />
          <div className="flex items-center gap-2">
            <ExaPromptFlyout />
            {/* Refresh (2026-09-06, the user's 'better place'): on the
                page-header line, left of the Help button — visible
                without opening the filters. */}
            <span className="tooltip tooltip-bottom" data-tip={logsLoading ? 'Loading...' : 'Refresh logs'}>
              <button
                type="button"
                className={`btn btn-sm ${logsLoading ? 'btn-ghost loading' : 'btn-primary'}`}
                onClick={refetchLogs}
                disabled={logsLoading}
              >
                {logsLoading ? '' : 'Refresh'}
              </button>
            </span>
            <HelpButton context="logs" tooltipPosition="bottom" />
          </div>
        </div>

        {/* Status Indicators - Compact Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-4">
          {/* Backend Status (app.log) */}
          <div className="card bg-base-100 shadow-sm shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)] border-l-4 border-secondary">
            <div className="card-body p-3">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-xs font-semibold text-readout uppercase">Backend</h4>
                  <p className="text-xl font-bold text-secondary">{backendLogsSize.toFixed(4)} MB</p>
                </div>
                <div className={`indicator ${isBackendConnected ? 'text-success' : 'text-warning'}`}>
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v6a2 2 0 002 2h14a2 2 0 002-2v-6a2 2 0 00-2-2m-2-4h.01M17 16h.01" />
                  </svg>
                </div>
              </div>
            </div>
          </div>

          {/* Frontend Status (frontend.log) */}
          <div className="card bg-base-100 shadow-sm shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)] border-l-4 border-primary">
            <div className="card-body p-3">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-xs font-semibold text-readout uppercase">Frontend</h4>
                  <p className="text-xl font-bold text-primary">{frontendLogsSize.toFixed(4)} MB</p>
                </div>
                <div className={`indicator ${isFrontendActive ? 'text-success' : 'text-warning'}`}>
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                  </svg>
                </div>
              </div>
            </div>
          </div>

          {/* Archives */}
          <div className="card bg-base-100 shadow-sm shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)] border-l-4 border-neutral">
            <div className="card-body p-3">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-xs font-semibold text-readout uppercase">Archives</h4>
                  <p className="text-xl font-bold text-neutral-content">{archiveSize.toFixed(4)} MB</p>
                </div>
                <div className="indicator text-neutral-content">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
                  </svg>
                </div>
              </div>
            </div>
          </div>

          {/* Total Size */}
          <div className="card bg-base-100 shadow-sm shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)] border-l-4 border-accent">
            <div className="card-body p-3">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-xs font-semibold text-readout uppercase">Total</h4>
                  <p className="text-xl font-bold text-accent">{totalSize.toFixed(4)} MB</p>
                </div>
                <div className="text-readout">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex gap-2 mb-4 flex-wrap">
          <div className="tooltip tooltip-top" data-tip="Clear frontend.log">
            <button
              className="btn btn-sm rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)] btn-warning btn-outline"
              onClick={() => clearFrontendLogsMutation.mutate()}
              disabled={clearFrontendLogsMutation.isPending}
            >
              {clearFrontendLogsMutation.isPending && (
                <span className="loading loading-spinner loading-xs"></span>
              )}
              Clear Frontend Logs
            </button>
          </div>

          <div className="tooltip tooltip-top" data-tip="Clear app.log">
            <button
              className="btn btn-sm rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)] btn-warning btn-outline"
              onClick={() => clearBackendLogsMutation.mutate()}
              disabled={clearBackendLogsMutation.isPending}
            >
              {clearBackendLogsMutation.isPending && (
                <span className="loading loading-spinner loading-xs"></span>
              )}
              Clear Backend Logs
            </button>
          </div>

          <div className="tooltip tooltip-top" data-tip="Clear ALL log files (frontend, backend, archives)">
            <button
              className="btn btn-sm rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)] btn-error"
              onClick={() => clearAllLogsMutation.mutate()}
              disabled={clearAllLogsMutation.isPending}
            >
              {clearAllLogsMutation.isPending && (
                <span className="loading loading-spinner loading-xs"></span>
              )}
              Clear ALL Logs
            </button>
          </div>

          <div className="tooltip tooltip-top" data-tip="Clear archived log files (compressed old logs)">
            <button
              className="btn btn-sm rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)] btn-warning btn-outline"
              onClick={() => clearArchivesMutation.mutate()}
              disabled={clearArchivesMutation.isPending || archiveSize === 0}
            >
              {clearArchivesMutation.isPending && (
                <span className="loading loading-spinner loading-xs"></span>
              )}
              Clear Archives
            </button>
          </div>

          {/* Generate Test Logs flyout */}
          <div className="dropdown dropdown-end">
            <span className="tooltip tooltip-bottom" data-tip="Generate sample log entries (DEBUG through CRITICAL) to test the pipeline">
              <label tabIndex={0} className="btn btn-sm btn-info btn-outline">
                Test Logs
              </label>
            </span>
            <ul tabIndex={0} className="dropdown-content menu p-2 shadow bg-base-200 rounded-box w-40 z-50">
              <li><button className="btn btn-ghost btn-xs" onClick={() => testLogMutations.all.mutate()} disabled={testLogMutations.all.isPending}>All</button></li>
              <li><button className="btn btn-ghost btn-xs" onClick={() => testLogMutations.frontend.mutate()} disabled={testLogMutations.frontend.isPending}>Frontend</button></li>
              <li><button className="btn btn-ghost btn-xs" onClick={() => testLogMutations.backend.mutate()} disabled={testLogMutations.backend.isPending}>Backend</button></li>
            </ul>
          </div>
        </div>

        {/* Controls — the FILTERS EXPANDER (2026-09-06, the user's
            vertical-space ask): the filter card collapses behind a
            summary row carrying the Filters badge + the active-filter
            count. */}
        <div className="tooltip tooltip-bottom w-full" data-tip="Expand or collapse the log filters">
        <details
          className="collapse collapse-arrow bg-base-100 border border-base-200 rounded-[var(--card-radius)] mb-4"
          open={filtersOpen}
          onToggle={(e) => setFiltersOpen((e.target as HTMLDetailsElement).open)}
        >
          <summary
            className="collapse-title min-h-0 py-2.5 pr-4 text-sm font-medium"
          >
            <span className="flex items-center gap-2">
              <span className="badge badge-sm badge-primary badge-outline">Filters</span>
              {activeFilterCount > 0 && (
                <span className="badge badge-sm badge-ghost">{activeFilterCount} active</span>
              )}
            </span>
          </summary>
          <div className="collapse-content">
        <LogFilters
          selectedLevel={filters.selectedLevel}
          searchTerm={searchTerm}
          sourceType={filters.sourceType}
          isSearching={searchTerm !== '' && debouncedSearchTerm !== ''}
          // Time range props
          fromTime={fromTime}
          toTime={toTime}
          onFromTimeChange={setFromTime}
          onToTimeChange={setToTime}
          timePreset={timePreset}
          onTimePresetChange={handleTimePresetChange}
          showAdvancedTime={showAdvancedTime}
          onToggleAdvancedTime={() => setShowAdvancedTime(!showAdvancedTime)}
          // Source filter props
          selectedSource={selectedSource}
          onSourceChange={setSelectedSource}
          availableSources={availableSources}
          // Pagination props
          currentPage={safeCurrentPage}
          totalPages={totalPages}
          totalItems={filteredLogs.length}
          pageSize={pageSize}
          hasPrevPage={hasPrevPage}
          hasNextPage={hasNextPage}
          onPrevPage={handlePrevPage}
          onNextPage={handleNextPage}
          onPageChange={handlePageChange}
          onLevelChange={setSelectedLevel}
          onSearchChange={setSearchTerm}
          onSourceTypeChange={setSourceType}
          onPageSizeChange={setPageSize}
        />
          </div>
        </details>
        </div>

{/* Logs Table */}
        <LogsTable
          logs={paginatedLogs}
          logsLoading={logsLoading}
          logsError={logsError}
          onLogSelect={handleLogSelect}
        />

        {/* Log Details Modal */}
        <LogDetailsModal
          selectedLog={selectedLog}
          onClose={handleModalClose}
        />
      </PageContainer>
    </ErrorBoundary>
  )
}
