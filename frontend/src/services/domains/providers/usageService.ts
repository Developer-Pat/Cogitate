/**
 * Usage Service - Phase 4
 *
 * Service for tracking and analyzing provider usage.
 * Connects to backend API endpoints for usage statistics.
 */

import { apiClient } from '@/services/apiClient';
import type {
  IUsageService,
  UsagePeriod,
  UsageSummaryResponse,
  UsageByProviderResponse,
  ModelUsageResponse,
  UsageTrendResponse,
  CostBreakdownResponse,
} from '@/types/providers';

/**
 * Usage Service Implementation
 */
class UsageService implements IUsageService {
  private readonly basePath = '/api/v1/providers/usage';

  /**
   * Get usage summary for a period
   */
  async getUsageSummary(period: UsagePeriod): Promise<UsageSummaryResponse> {
    const response = await apiClient.get<UsageSummaryResponse>(`${this.basePath}?period=${period}`);

    if (response.error) {
      throw new Error(response.error.message);
    }

    return response.data!;
  }

  /**
   * Get usage breakdown by provider
   */
  async getUsageByProvider(period: UsagePeriod): Promise<UsageByProviderResponse> {
    const response = await apiClient.get<UsageByProviderResponse>(`${this.basePath}/by-provider?period=${period}`);

    if (response.error) {
      throw new Error(response.error.message);
    }

    return response.data!;
  }

  /**
   * Get usage breakdown by model
   */
  async getUsageByModel(period: UsagePeriod): Promise<ModelUsageResponse[]> {
    const response = await apiClient.get<ModelUsageResponse[]>(`${this.basePath}/by-model?period=${period}`);

    if (response.error) {
      throw new Error(response.error.message);
    }

    return response.data! || [];
  }

  /**
   * Get usage trend over time
   */
  async getUsageTrend(days: number): Promise<UsageTrendResponse[]> {
    const response = await apiClient.get<UsageTrendResponse[]>(`${this.basePath}/trend?days=${days}`);

    if (response.error) {
      throw new Error(response.error.message);
    }

    return response.data! || [];
  }

  /**
   * Get cost breakdown by provider
   */
  async getCostBreakdown(period: UsagePeriod): Promise<CostBreakdownResponse> {
    const response = await apiClient.get<CostBreakdownResponse>(`${this.basePath}/cost-breakdown?period=${period}`);

    if (response.error) {
      throw new Error(response.error.message);
    }

    return response.data!;
  }

  /**
   * Reset usage logs (for testing)
   */
  async resetUsage(providerId: number): Promise<void> {
    const response = await apiClient.post(`${this.basePath}/${providerId}/reset`);

    if (response.error) {
      throw new Error(response.error.message);
    }
  }
}

// Create and export singleton instance
export const usageService = new UsageService();

export default usageService;
