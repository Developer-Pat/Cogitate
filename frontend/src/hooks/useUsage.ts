/**
 * useUsage Hook - Phase 4
 *
 * Hook for tracking and analyzing provider usage.
 * Provides state management for usage statistics and trends.
 */

import { useState, useEffect, useCallback } from 'react';
import { usageService } from '../services/domains/providers/usageService';
import type {
  UsagePeriod,
  UsageSummaryResponse,
  UsageByProviderResponse,
  ModelUsageResponse,
  UsageTrendResponse,
  CostBreakdownResponse,
  UseUsageReturn,
} from '../types/providers';

interface UseUsageOptions {
  period?: UsagePeriod;
  trendDays?: number;
}

/**
 * Default options
 */
const defaultOptions: UseUsageOptions = {
  period: 'monthly',
  trendDays: 30,
};

/**
 * Hook for usage tracking and analytics
 */
export const useUsage = (options: UseUsageOptions = defaultOptions): UseUsageReturn => {
  const { period = 'monthly', trendDays = 30 } = options;

  const [usage, setUsage] = useState<UsageSummaryResponse | null>(null);
  const [usageByProvider, setUsageByProvider] = useState<UsageByProviderResponse | null>(null);
  const [usageByModel, setUsageByModel] = useState<ModelUsageResponse[]>([]);
  const [usageTrend, setUsageTrend] = useState<UsageTrendResponse[]>([]);
  const [costBreakdown, setCostBreakdown] = useState<CostBreakdownResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  /**
   * Load all usage data from the API
   */
  const loadUsage = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      // Load all usage data in parallel
      const [
        usageData,
        byProviderData,
        byModelData,
        trendData,
        costData,
      ] = await Promise.all([
        usageService.getUsageSummary(period),
        usageService.getUsageByProvider(period),
        usageService.getUsageByModel(period),
        usageService.getUsageTrend(trendDays),
        usageService.getCostBreakdown(period),
      ]);

      setUsage(usageData);
      setUsageByProvider(byProviderData);
      setUsageByModel(byModelData);
      setUsageTrend(trendData);
      setCostBreakdown(costData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load usage data');
    } finally {
      setLoading(false);
    }
  }, [period, trendDays]);

  /**
   * Refresh usage data
   */
  const refreshUsage = useCallback(async () => {
    await loadUsage();
  }, [loadUsage]);

  // Load usage data on mount and when options change
  useEffect(() => {
    loadUsage();
  }, [loadUsage]);

  return {
    usage,
    usageByProvider,
    usageByModel,
    usageTrend,
    costBreakdown,
    loading,
    error,
    refreshUsage,
  };
};

export default useUsage;
