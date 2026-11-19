/**
 * UsageDashboard Component - Phase 4
 *
 * Dashboard for tracking provider usage and costs.
 * Shows usage statistics, trends, and cost breakdowns.
 */

import React, { useState } from 'react';
import Tooltip from '@/components/ui/Tooltip';
import type {
  UsageSummaryResponse,
  ModelUsageResponse,
  UsageTrendResponse,
  CostBreakdownResponse,
  UsagePeriod,
} from '@/types/providers';

interface UsageDashboardProps {
  usage?: UsageSummaryResponse | null;
  usageByModel?: ModelUsageResponse[];
  usageTrend?: UsageTrendResponse[];
  costBreakdown?: CostBreakdownResponse | null;
  loading?: boolean;
  onPeriodChange?: (period: UsagePeriod) => void;
}

/**
 * UsageDashboard Component
 */
const UsageDashboard: React.FC<UsageDashboardProps> = ({
  usage,
  usageByModel = [],
  usageTrend = [],
  costBreakdown,
  loading = false,
  onPeriodChange,
}) => {
  const [period, setPeriod] = useState<UsagePeriod>('monthly');

  /**
   * Handle period change
   */
  const handlePeriodChange = (newPeriod: UsagePeriod) => {
    setPeriod(newPeriod);
    onPeriodChange?.(newPeriod);
  };

  /**
   * Format tokens
   */
  const formatTokens = (tokens: number) => {
    if (tokens >= 1000000) {
      return `${(tokens / 1000000).toFixed(2)}M`;
    }
    if (tokens >= 1000) {
      return `${(tokens / 1000).toFixed(2)}K`;
    }
    return tokens.toString();
  };

  /**
   * Format currency
   */
  const formatCurrency = (amount: number) => {
    return `$${amount.toFixed(4)}`;
  };

  /**
   * Get max value from trend data (for chart scaling)
   */
  const getMaxTrendValue = () => {
    if (usageTrend.length === 0) return 1;
    return Math.max(...usageTrend.map((t) => t.total_tokens));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <span className="loading loading-spinner text-primary"></span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header with Period Selector */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-base-content dark:text-base-content">
          Usage Statistics
        </h2>
        <div className="flex gap-2">
          <Tooltip content="Show usage for the last 24 hours" position="bottom">
            <button
              key="daily"
              onClick={() => handlePeriodChange('daily')}
              className={`px-3 py-1 text-sm rounded-lg transition-colors ${
                period === 'daily'
                  ? 'bg-primary text-base-content'
                  : 'bg-base-200 dark:bg-base-200 text-readout  hover:bg-base-300 dark:hover:bg-base-content/60'
              }`}
            >
              Daily
            </button>
          </Tooltip>
          <Tooltip content="Show usage for the last 7 days" position="bottom">
            <button
              key="weekly"
              onClick={() => handlePeriodChange('weekly')}
              className={`px-3 py-1 text-sm rounded-lg transition-colors ${
                period === 'weekly'
                  ? 'bg-primary text-base-content'
                  : 'bg-base-200 dark:bg-base-200 text-readout  hover:bg-base-300 dark:hover:bg-base-content/60'
              }`}
            >
              Weekly
            </button>
          </Tooltip>
          <Tooltip content="Show usage for the last 30 days" position="bottom">
            <button
              key="monthly"
              onClick={() => handlePeriodChange('monthly')}
              className={`px-3 py-1 text-sm rounded-lg transition-colors ${
                period === 'monthly'
                  ? 'bg-primary text-base-content'
                  : 'bg-base-200 dark:bg-base-200 text-readout  hover:bg-base-300 dark:hover:bg-base-content/60'
              }`}
            >
              Monthly
            </button>
          </Tooltip>
          <Tooltip content="Show all recorded usage data" position="bottom">
            <button
              key="all_time"
              onClick={() => handlePeriodChange('all_time')}
              className={`px-3 py-1 text-sm rounded-lg transition-colors ${
                period === 'all_time'
                  ? 'bg-primary text-base-content'
                  : 'bg-base-200 dark:bg-base-200 text-readout  hover:bg-base-300 dark:hover:bg-base-content/60'
              }`}
            >
              All Time
            </button>
          </Tooltip>
        </div>
      </div>

      {/* Summary Cards */}
      {usage && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Tooltip content="Total tokens processed (prompt + completion)" position="bottom">
            <div className="bg-base-100 dark:bg-base-200 rounded-lg shadow p-4 border border-base-content/20 dark:border-base-content/20 cursor-help">
              <p className="text-sm text-readout ">Total Tokens</p>
              <p className="text-2xl font-bold text-base-content dark:text-base-content">
                {formatTokens(usage.total_tokens)}
              </p>
              <p className="text-xs text-readout  mt-1">
                {usage.prompt_tokens} prompt / {usage.completion_tokens} completion
              </p>
            </div>
          </Tooltip>

          <Tooltip content="Total cost in USD for API usage" position="bottom">
            <div className="bg-base-100 dark:bg-base-200 rounded-lg shadow p-4 border border-base-content/20 dark:border-base-content/20 cursor-help">
              <p className="text-sm text-readout ">Total Cost</p>
              <p className="text-2xl font-bold text-success">
                {formatCurrency(usage.total_cost_usd)}
              </p>
            </div>
          </Tooltip>

          <Tooltip content="Total API requests made (successful and failed)" position="bottom">
            <div className="bg-base-100 dark:bg-base-200 rounded-lg shadow p-4 border border-base-content/20 dark:border-base-content/20 cursor-help">
              <p className="text-sm text-readout ">Total Requests</p>
              <p className="text-2xl font-bold text-base-content dark:text-base-content">
                {usage.total_requests}
              </p>
              <p className="text-xs text-readout  mt-1">
                {usage.success_count} successful / {usage.error_count} failed
              </p>
            </div>
          </Tooltip>

          <Tooltip content="Average response time per request" position="bottom">
            <div className="bg-base-100 dark:bg-base-200 rounded-lg shadow p-4 border border-base-content/20 dark:border-base-content/20 cursor-help">
              <p className="text-sm text-readout ">Avg Response Time</p>
              <p className="text-2xl font-bold text-base-content dark:text-base-content">
                {usage.avg_response_time_ms
                  ? `${Math.round(usage.avg_response_time_ms)}ms`
                  : 'N/A'}
              </p>
            </div>
          </Tooltip>
        </div>
      )}

      {/* Usage Trend Chart */}
      {usageTrend.length > 0 && (
        <div className="bg-base-100 dark:bg-base-200 rounded-lg shadow p-4 border border-base-content/20 dark:border-base-content/20">
          <h3 className="text-sm font-medium text-base-content dark:text-base-content mb-4">
            Usage Trend
          </h3>
          <div className="h-48 flex items-end gap-1">
            {usageTrend.map((day, index) => {
              const maxValue = getMaxTrendValue();
              const height = (day.total_tokens / maxValue) * 100;
              return (
                <div
                  key={index}
                  className="flex-1 flex flex-col items-center gap-1 group relative"
                >
                  <div
                    className="w-full bg-primary hover:bg-primary rounded-t transition-all"
                    style={{ height: `${height}%` }}
                  ></div>
                  <span className="text-xs text-readout  rotate-45 origin-top-left translate-y-2">
                    {new Date(day.date).toLocaleDateString('en-US', {
                      month: 'short',
                      day: 'numeric',
                    })}
                  </span>
                  {/* Tooltip */}
                  <div className="absolute bottom-full mb-2 hidden group-hover:block bg-base-300 text-base-content text-xs rounded px-2 py-1 whitespace-nowrap z-10">
                    {formatTokens(day.total_tokens)} tokens - {formatCurrency(day.total_cost_usd)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Cost Breakdown by Provider */}
      {costBreakdown && costBreakdown.by_provider && Object.keys(costBreakdown.by_provider).length > 0 && (
        <div className="bg-base-100 dark:bg-base-200 rounded-lg shadow p-4 border border-base-content/20 dark:border-base-content/20">
          <h3 className="text-sm font-medium text-base-content dark:text-base-content mb-4">
            Cost by Provider
          </h3>
          <div className="space-y-3">
            {Object.entries(costBreakdown.by_provider).map(([provider, cost]) => {
              const percentage =
                costBreakdown.total_cost_usd > 0
                  ? (cost / costBreakdown.total_cost_usd) * 100
                  : 0;
              return (
                <div key={provider}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-readout  capitalize">
                      {provider}
                    </span>
                    <span className="text-base-content dark:text-base-content font-medium">
                      {formatCurrency(cost)}
                    </span>
                  </div>
                  <div className="w-full bg-base-300 dark:bg-base-200 rounded-full h-2">
                    <div
                      className="bg-primary h-2 rounded-full transition-all"
                      style={{ width: `${percentage}%` }}
                    ></div>
                  </div>
                </div>
              );
            })}
          </div>
          <div className="mt-4 pt-4 border-t border-base-content/20 dark:border-base-content/20">
            <div className="flex justify-between text-sm">
              <span className="text-readout  font-medium">Total</span>
              <span className="text-base-content dark:text-base-content font-bold">
                {formatCurrency(costBreakdown.total_cost_usd)}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Usage by Model Table */}
      {usageByModel.length > 0 && (
        <div className="bg-base-100 dark:bg-base-200 rounded-lg shadow p-4 border border-base-content/20 dark:border-base-content/20">
          <h3 className="text-sm font-medium text-base-content dark:text-base-content mb-4">
            Usage by Model
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-base-content/20 dark:border-base-content/20">
                  <th className="text-left py-2 px-3 text-readout  font-medium">
                    Model
                  </th>
                  <th className="text-right py-2 px-3 text-readout  font-medium">
                    Tokens
                  </th>
                  <th className="text-right py-2 px-3 text-readout  font-medium">
                    Requests
                  </th>
                  <th className="text-right py-2 px-3 text-readout  font-medium">
                    Cost
                  </th>
                </tr>
              </thead>
              <tbody>
                {usageByModel.map((model, index) => (
                  <tr
                    key={index}
                    className="border-b border-base-content/10 hover:bg-base-200/50"
                  >
                    <td className="py-2 px-3 text-base-content dark:text-base-content">
                      {model.model}
                    </td>
                    <td className="py-2 px-3 text-right text-base-content dark:text-base-content">
                      {formatTokens(model.total_tokens)}
                    </td>
                    <td className="py-2 px-3 text-right text-base-content dark:text-base-content">
                      {model.total_requests}
                    </td>
                    <td className="py-2 px-3 text-right text-success font-medium">
                      {formatCurrency(model.total_cost_usd)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!usage && usageByModel.length === 0 && (
        <div className="text-center py-8 text-readout ">
          No usage data available for this period
        </div>
      )}
    </div>
  );
};

export default UsageDashboard;
