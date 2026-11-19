/**
 * Provider Models Browser Page
 *
 * Dedicated page for browsing and selecting provider models.
 * Supports search, filtering, and pagination.
 */

import React, { useState, useEffect, useCallback } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ErrorBoundary } from '../components/ErrorBoundary'
import { usePageTitle } from '../hooks/usePageTitle'

import { modelBrowserService, type ModelBrowserFilters, type ModelInfo } from '../services/domains/providers/modelBrowserService'
import { frontendLoggingService } from '../services/frontendLoggingService'
import ModelFilters from '../components/features/providers/ModelBrowser/ModelFilters'
import ModelTable from '../components/features/providers/ModelBrowser/ModelTable'
import { useDebounce } from '../hooks/useDebounce'
import { HelpButton } from '../components/help';

/**
 * Provider Models Browser Page Component
 */
const ProviderModelsBrowser: React.FC = () => {
  usePageTitle('Browse Models', 'Browse and select provider models')
  
  const navigate = useNavigate()
  const { providerId } = useParams<{ providerId: string }>()
  const [searchParams, setSearchParams] = useSearchParams()

  // State
  const [models, setModels] = useState<ModelInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(0)
  const [fromCache, setFromCache] = useState(false)
  const [providerName, setProviderName] = useState('')

  // Filters from URL params
  const [filters, setFilters] = useState<ModelBrowserFilters>({
    page: parseInt(searchParams.get('page') || '1'),
    page_size: parseInt(searchParams.get('page_size') || '50'),
    search: searchParams.get('search') || undefined,
    free_only: searchParams.get('free_only') === 'true',
    sort_by: searchParams.get('sort_by') || 'name',
    sort_order: (searchParams.get('sort_order') || 'asc') as 'asc' | 'desc',
  })

  const debouncedSearch = useDebounce(filters.search || '', 300)

  /**
   * Load models based on filters
   */
  const loadModels = useCallback(async () => {
    if (!providerId) {
      setError('Provider ID is required')
      setLoading(false)
      return
    }

    setLoading(true)
    setError(null)

    try {
      const numericProviderId = parseInt(providerId)

      frontendLoggingService.debug('ProviderModelsBrowser', 'Loading models', {
        providerId: numericProviderId,
        filters,
        debouncedSearch,
      })

      const response = await modelBrowserService.browseModels(numericProviderId, {
        ...filters,
        search: debouncedSearch || undefined,
      })

      if (response.data) {
        setModels(response.data.models)
        setTotal(response.data.total)
        setTotalPages(response.data.total_pages)
        setFromCache(response.data.from_cache)
        setProviderName(response.data.provider_name)

        frontendLoggingService.info('ProviderModelsBrowser', 'Models loaded', {
          count: response.data.models.length,
          total: response.data.total,
          fromCache: response.data.from_cache,
          search: debouncedSearch,
        })
      } else if (response.error) {
        setError(response.error.message || 'Failed to load models')
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load models'
      setError(message)
      frontendLoggingService.error('ProviderModelsBrowser', 'Error loading models', err)
    } finally {
      setLoading(false)
    }
  }, [providerId, filters, debouncedSearch])

  /**
   * Load models on mount and when filters change
   */
  useEffect(() => {
    loadModels()
  }, [loadModels])

  /**
   * Handle filter change
   */
  const handleFilterChange = (newFilters: Partial<ModelBrowserFilters>) => {
    const updatedFilters = { ...filters, ...newFilters }
    
    // Reset to page 1 when search or filters change (unless explicitly changing page)
    if (newFilters.search !== undefined || newFilters.free_only !== undefined) {
      updatedFilters.page = 1
    }

    setFilters(updatedFilters)

    // Update URL params
    const params = new URLSearchParams()
    if (updatedFilters.page) params.set('page', updatedFilters.page.toString())
    if (updatedFilters.page_size) params.set('page_size', updatedFilters.page_size.toString())
    if (updatedFilters.search) params.set('search', updatedFilters.search)
    if (updatedFilters.free_only) params.set('free_only', 'true')
    if (updatedFilters.sort_by) params.set('sort_by', updatedFilters.sort_by)
    if (updatedFilters.sort_order) params.set('sort_order', updatedFilters.sort_order)

    setSearchParams(params)
  }

  /**
   * Handle page change
   */
  const handlePageChange = (page: number) => {
    handleFilterChange({ page })
  }

  /**
   * Handle page size change
   */
  const handlePageSizeChange = (pageSize: number) => {
    handleFilterChange({ page_size: pageSize, page: 1 })
  }

  /**
   * Handle model selection
   */
  const handleSelectModel = (model: ModelInfo) => {
    frontendLoggingService.info('ProviderModelsBrowser', 'Model selected', {
      modelId: model.id,
      modelName: model.name,
    })

    // Store selection in sessionStorage
    const selection = {
      modelId: model.id,
      modelName: model.name,
      providerId,
      providerName,
      timestamp: Date.now(),
    }
    sessionStorage.setItem('selectedModel', JSON.stringify(selection))

    // Navigate back to agent profiles (correct route)
    navigate('/agent-profiles', {
      state: { modelSelected: true },
    })
  }

  /**
   * Handle back navigation
   */
  const handleBack = () => {
    navigate('/agents/profiles')
  }

  /**
   * Handle refresh
   */
  const handleRefresh = () => {
    loadModels()
  }

  return (
    <ErrorBoundary>
      <div className="min-h-screen bg-base-100">
        {/* Header */}
        <div className="bg-base-200 border-b border-base-300">
          <div className="max-w-7xl mx-auto px-4 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-4">
                <button
                  onClick={handleBack}
                  className="btn btn-ghost btn-sm"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                  </svg>
                  Back
                </button>
                <div>
                  <h1 className="text-2xl font-bold text-base-content">
                    Browse Models - {providerName || 'Provider'}
                  </h1>
                  <p className="text-sm text-readout">
                    {total.toLocaleString()} models available
                    {fromCache && (
                      <span className="ml-2 text-xs text-info">
                        • From cache
                      </span>
                    )}
                  </p>
                <HelpButton context="providers" tooltipPosition="bottom" />
                </div>
              </div>

              <button
                onClick={handleRefresh}
                disabled={loading}
                className="btn btn-sm btn-outline"
              >
                <svg
                  className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                  />
                </svg>
                Refresh
              </button>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="max-w-7xl mx-auto px-4 py-6">
          {/* Filters */}
          <div className="mb-6">
            <ModelFilters
              filters={filters}
              onFilterChange={handleFilterChange}
              providerId={providerId ? parseInt(providerId) : undefined}
            />
          </div>

          {/* Error Display */}
          {error && (
            <div className="mb-6 alert alert-error">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
              <span>{error}</span>
            </div>
          )}

          {/* Models Table */}
          <ModelTable
            models={models}
            loading={loading}
            error={error}
            currentPage={filters.page || 1}
            totalPages={totalPages}
            pageSize={filters.page_size || 50}
            totalItems={total}
            onPageChange={handlePageChange}
            onPageSizeChange={handlePageSizeChange}
            onSelectModel={handleSelectModel}
          />
        </div>
      </div>
    </ErrorBoundary>
  )
}

export default ProviderModelsBrowser
