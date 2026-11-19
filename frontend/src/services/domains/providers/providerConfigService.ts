/**
 * Provider Config Service - Phase 4
 *
 * Service for managing provider configurations.
 * Connects to backend API endpoints for CRUD operations.
 */

import { apiClient } from '@/services/apiClient';
import type {
  IProviderConfigService,
  ProviderConfig,
  ProviderConfigListResponse,
  ProviderConfigCreate,
  ProviderConfigUpdate,
  ApiKeyStatusResponse,
  ProviderTestResponse,
} from '@/types/providers';

/**
 * Provider Config Service Implementation
 */
class ProviderConfigService implements IProviderConfigService {
  private readonly basePath = '/api/v1/providers/config';

  /**
   * Get all provider configurations
   */
  async getProviders(includeInactive: boolean = false): Promise<ProviderConfigListResponse> {
    const url = `${this.basePath}${includeInactive ? '?include_inactive=true' : ''}`;
    const response = await apiClient.get<ProviderConfigListResponse>(url);

    if (response.error) {
      throw new Error(response.error.message);
    }

    return response.data!;
  }

  /**
   * Get a specific provider configuration
   */
  async getProvider(id: number): Promise<ProviderConfig> {
    const response = await apiClient.get<ProviderConfig>(`${this.basePath}/${id}`);

    if (response.error) {
      throw new Error(response.error.message);
    }

    return response.data!;
  }

  /**
   * Create a new provider configuration
   */
  async createProvider(config: ProviderConfigCreate): Promise<ProviderConfig> {
    const response = await apiClient.post<ProviderConfig>(this.basePath, config);

    if (response.error) {
      throw new Error(response.error.message);
    }

    return response.data!;
  }

  /**
   * Update an existing provider configuration
   */
  async updateProvider(id: number, config: ProviderConfigUpdate): Promise<ProviderConfig> {
    const response = await apiClient.put<ProviderConfig>(`${this.basePath}/${id}`, config);

    if (response.error) {
      throw new Error(response.error.message);
    }

    return response.data!;
  }

  /**
   * Delete a provider configuration
   */
  async deleteProvider(id: number): Promise<void> {
    const response = await apiClient.delete(`${this.basePath}/${id}`);

    if (response.error) {
      throw new Error(response.error.message);
    }
  }

  /**
   * Set API key for a provider
   */
  async setApiKey(id: number, apiKey: string): Promise<void> {
    const response = await apiClient.post(`${this.basePath}/${id}/api-key`, { api_key: apiKey });

    if (response.error) {
      throw new Error(response.error.message);
    }
  }

  /**
   * Get API key status for a provider
   */
  async getApiKeyStatus(id: number): Promise<ApiKeyStatusResponse> {
    const response = await apiClient.get<ApiKeyStatusResponse>(`${this.basePath}/${id}/api-key`);

    if (response.error) {
      throw new Error(response.error.message);
    }

    return response.data!;
  }

  /**
   * Test provider connection
   */
  async testProvider(id: number): Promise<ProviderTestResponse> {
    const response = await apiClient.post<ProviderTestResponse>(`${this.basePath}/${id}/test`);

    if (response.error) {
      throw new Error(response.error.message);
    }

    return response.data!;
  }

  /**
   * Sync models for a provider
   */
  async syncModels(id: number, forceRefresh: boolean = true): Promise<unknown> {
    const response = await apiClient.post(`${this.basePath}/${id}/sync?force_refresh=${forceRefresh}`);

    if (response.error) {
      throw new Error(response.error.message);
    }

    return response.data!;
  }
}

// Create and export singleton instance
export const providerConfigService = new ProviderConfigService();

export default providerConfigService;
