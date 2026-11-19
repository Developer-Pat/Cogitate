/**
 * Default Provider Service
 *
 * Service for managing the system-wide default LLM provider.
 * Handles setting, getting, and initializing the default provider.
 */

import { apiClient } from '@/services/apiClient';
import { frontendLoggingService } from '@/services/frontendLoggingService';
import type {
  DefaultProviderResponse,
  SetDefaultProviderRequest,
  InitializeDefaultProviderResponse,
} from '@/types/providers/default';
import type { ApiResponse } from '@/types';

/**
 * Default Provider Service Interface
 */
export interface IDefaultProviderService {
  getDefaultProvider(): Promise<ApiResponse<DefaultProviderResponse>>;
  setDefaultProvider(providerId: number): Promise<ApiResponse<DefaultProviderResponse>>;
  initializeDefaultProvider(): Promise<ApiResponse<InitializeDefaultProviderResponse>>;
}

/**
 * Default Provider Service Implementation
 */
class DefaultProviderService implements IDefaultProviderService {
  private readonly basePath = '/api/v1/providers';

  /**
   * Get the current default provider
   */
  async getDefaultProvider(): Promise<ApiResponse<DefaultProviderResponse>> {
    frontendLoggingService.debug('DefaultProviderService', 'Getting default provider from backend');
    try {
      const response = await apiClient.get<DefaultProviderResponse>(`${this.basePath}/default`);
      frontendLoggingService.info('DefaultProviderService', `Got default provider: ${response.data?.provider_name || 'none'}`);
      return response;
    } catch (error) {
      frontendLoggingService.error('DefaultProviderService', 'Failed to get default provider', error);
      return {
        data: undefined,
        error: {
          code: 'UNKNOWN',
          message: error instanceof Error ? error.message : 'Failed to get default provider',
        },
        status: 500,
        timestamp: new Date().toISOString(),
      };
    }
  }

  /**
   * Set a provider as the system default
   */
  async setDefaultProvider(providerId: number): Promise<ApiResponse<DefaultProviderResponse>> {
    frontendLoggingService.info('DefaultProviderService', `Setting provider ${providerId} as default`);
    try {
      const request: SetDefaultProviderRequest = { provider_id: providerId };
      const response = await apiClient.put<DefaultProviderResponse>(
        `${this.basePath}/default`,
        request
      );
      frontendLoggingService.info('DefaultProviderService', `Set default provider: ${response.data?.provider_name}`);
      return response;
    } catch (error) {
      frontendLoggingService.error('DefaultProviderService', 'Failed to set default provider', error);
      return {
        data: undefined,
        error: {
          code: 'UNKNOWN',
          message: error instanceof Error ? error.message : 'Failed to set default provider',
        },
        status: 500,
        timestamp: new Date().toISOString(),
      };
    }
  }

  /**
   * Initialize default provider if none exists
   * Creates a default Ollama configuration automatically
   */
  async initializeDefaultProvider(): Promise<ApiResponse<InitializeDefaultProviderResponse>> {
    frontendLoggingService.info('DefaultProviderService', 'Initializing default provider');
    try {
      const response = await apiClient.post<InitializeDefaultProviderResponse>(
        `${this.basePath}/initialize-default`
      );
      frontendLoggingService.info('DefaultProviderService', `Initialized default provider: ${response.data?.provider_name || 'none'}`);
      return response;
    } catch (error) {
      frontendLoggingService.error('DefaultProviderService', 'Failed to initialize default provider', error);
      return {
        data: undefined,
        error: {
          code: 'UNKNOWN',
          message: error instanceof Error ? error.message : 'Failed to initialize default provider',
        },
        status: 500,
        timestamp: new Date().toISOString(),
      };
    }
  }
}

// Export singleton instance
export const defaultProviderService = new DefaultProviderService();
