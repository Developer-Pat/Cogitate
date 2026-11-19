/**
 * Model Browser Service
 *
 * Service for browsing and searching provider models.
 * Provides unified interface for model discovery across different providers.
 */

import { apiClient } from '@/services/apiClient'
import { frontendLoggingService } from '@/services/frontendLoggingService'
import type { ApiResponse } from '@/types'

/**
 * Model Browser Filters
 */
export interface ModelBrowserFilters {
  search?: string
  capabilities?: string[]
  min_context_length?: number
  max_context_length?: number
  free_only?: boolean
  max_price_prompt?: number
  max_price_completion?: number
  providers?: string[]
  page?: number
  page_size?: number
  sort_by?: string
  sort_order?: 'asc' | 'desc'
}

/**
 * Model Info Interface
 */
export interface ModelInfo {
  id: string
  name: string
  display_name?: string
  description?: string
  context_length?: number
  architecture?: string
  modality?: string
  function_calling?: boolean
  pricing_prompt?: number
  pricing_completion?: number
  /** The nested shape the API also sends (`{prompt, completion}`, per token). openrouter's rows
   *  carry ONLY this, so a reader that looks at the flat fields alone shows `N/A` for them. */
  pricing?: { prompt?: number | null; completion?: number | null }
  top_provider?: string
  capabilities?: string[]
  capability_badges?: ModelCapabilityBadge[]
  context_category?: 'standard' | 'long' | 'very_long' | 'ultra_long'
  curated?: {
    is_curated: boolean
    verified: boolean
  }
  _raw?: unknown
}

/**
 * Model Capability Badge
 */
export interface ModelCapabilityBadge {
  id: string
  label: string
  color: string
  icon: string
}

/**
 * Capability Info
 */
export interface CapabilityInfo {
  id: string
  name: string
  count?: number
}

/**
 * Model Browser Response
 */
export interface ModelBrowserResponse {
  models: ModelInfo[]
  total: number
  page: number
  page_size: number
  total_pages: number
  has_more: boolean
  filters_applied: ModelBrowserFilters
  from_cache: boolean
  provider_name: string
}

/**
 * Model Details Response
 */
export interface ModelDetailsResponse {
  model: ModelInfo
  provider_name: string
}

/**
 * Capabilities Response
 */
export interface CapabilitiesResponse {
  capabilities: CapabilityInfo[]
  total: number
  provider_name: string
}

/**
 * Model Browser Service Interface
 */
export interface IModelBrowserService {
  browseModels(providerId: number, filters?: ModelBrowserFilters): Promise<ApiResponse<ModelBrowserResponse>>
  getModelDetails(providerId: number, modelId: string): Promise<ApiResponse<ModelDetailsResponse>>
  getCapabilities(providerId: number): Promise<ApiResponse<CapabilitiesResponse>>
}

/**
 * Model Browser Service Implementation
 */
class ModelBrowserService implements IModelBrowserService {
  private readonly basePath = '/api/v1/providers'

  /**
   * Browse models with filtering and pagination
   */
  async browseModels(
    providerId: number,
    filters: ModelBrowserFilters = {}
  ): Promise<ApiResponse<ModelBrowserResponse>> {
    frontendLoggingService.debug('ModelBrowserService', 'Browsing models', {
      providerId,
      filters
    })

    // Build query parameters
    const params = new URLSearchParams()
    
    if (filters.search) params.append('search', filters.search)
    if (filters.capabilities) {
      filters.capabilities.forEach(cap => params.append('capabilities', cap))
    }
    if (filters.min_context_length) params.append('min_context', filters.min_context_length.toString())
    if (filters.max_context_length) params.append('max_context', filters.max_context_length.toString())
    if (filters.free_only) params.append('free_only', 'true')
    if (filters.max_price_prompt) params.append('max_price_prompt', filters.max_price_prompt.toString())
    if (filters.max_price_completion) params.append('max_price_completion', filters.max_price_completion.toString())
    if (filters.providers) {
      filters.providers.forEach(provider => params.append('providers', provider))
    }
    
    params.append('page', (filters.page || 1).toString())
    params.append('page_size', (filters.page_size || 50).toString())
    params.append('sort_by', filters.sort_by || 'name')
    params.append('sort_order', filters.sort_order || 'asc')

    const url = `${this.basePath}/${providerId}/models/browse?${params.toString()}`

    try {
      const response = await apiClient.get<ModelBrowserResponse>(url)
      
      frontendLoggingService.info('ModelBrowserService', 'Models browsed successfully', {
        providerId,
        modelCount: response.data?.models.length || 0,
        total: response.data?.total || 0,
        page: response.data?.page || 1
      })

      return response
    } catch (error) {
      frontendLoggingService.error('ModelBrowserService', 'Failed to browse models', error)
      return {
        status: 500,
        timestamp: new Date().toISOString(),
        error: {
          code: 'BROWSE_ERROR',
          message: error instanceof Error ? error.message : 'Failed to browse models'
        }
      }
    }
  }

  /**
   * Get detailed information about a specific model
   */
  async getModelDetails(
    providerId: number,
    modelId: string
  ): Promise<ApiResponse<ModelDetailsResponse>> {
    frontendLoggingService.debug('ModelBrowserService', 'Getting model details', {
      providerId,
      modelId
    })

    try {
      const url = `${this.basePath}/${providerId}/models/${encodeURIComponent(modelId)}`
      const response = await apiClient.get<ModelDetailsResponse>(url)

      frontendLoggingService.info('ModelBrowserService', 'Model details retrieved', {
        providerId,
        modelId,
        modelName: response.data?.model.name
      })

      return response
    } catch (error) {
      frontendLoggingService.error('ModelBrowserService', 'Failed to get model details', error)
      return {
        status: 500,
        timestamp: new Date().toISOString(),
        error: {
          code: 'DETAILS_ERROR',
          message: error instanceof Error ? error.message : 'Failed to get model details'
        }
      }
    }
  }

  /**
   * Get available capabilities for filtering
   */
  async getCapabilities(providerId: number): Promise<ApiResponse<CapabilitiesResponse>> {
    frontendLoggingService.debug('ModelBrowserService', 'Getting capabilities', {
      providerId
    })

    try {
      const url = `${this.basePath}/${providerId}/models/capabilities`
      const response = await apiClient.get<CapabilitiesResponse>(url)

      frontendLoggingService.info('ModelBrowserService', 'Capabilities retrieved', {
        providerId,
        capabilityCount: response.data?.total || 0
      })

      return response
    } catch (error) {
      frontendLoggingService.error('ModelBrowserService', 'Failed to get capabilities', error)
      return {
        status: 500,
        timestamp: new Date().toISOString(),
        error: {
          code: 'CAPABILITIES_ERROR',
          message: error instanceof Error ? error.message : 'Failed to get capabilities'
        }
      }
    }
  }
}

// Create and export singleton instance
export const modelBrowserService: IModelBrowserService = new ModelBrowserService()

export default modelBrowserService
