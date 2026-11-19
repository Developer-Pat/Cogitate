/**
 * Hook for fetching log histogram data
 *
 * Features:
 * - Computes histogram from logs on-demand
 * - No persistence (pure log analysis)
 * - Configurable time range
 * - Auto-refresh when time range changes
 */

import { useQuery } from '@tanstack/react-query'
import { historyService, type HistogramOptions, type TimeRange } from '../services/domain/HistoryService'

/**
 * Hook for fetching log histogram
 */
export function useLogsHistogram(timeRange: TimeRange, options?: Omit<HistogramOptions, 'timeRange'>) {
  return useQuery({
    queryKey: ['logs-histogram', timeRange, options],
    queryFn: async () => {
      const histogramOptions: HistogramOptions = {
        timeRange,
        ...options
      }
      return await historyService.getLogsHistogram(histogramOptions)
    },
    staleTime: 0, // Always consider data stale (force refresh)
    refetchOnWindowFocus: true, // Refresh when user returns to page
  })
}

/**
 * Hook for fetching log statistics from history
 */
export function useHistoryStats(timeRange?: TimeRange) {
  return useQuery({
    queryKey: ['history-stats', timeRange],
    queryFn: async () => {
      return await historyService.getStats(timeRange)
    },
    staleTime: 0,
    refetchOnWindowFocus: true,
  })
}

/**
 * Hook for detecting issues in logs
 */
export function useHistoryIssues() {
  return useQuery({
    queryKey: ['history-issues'],
    queryFn: async () => {
      return await historyService.detectIssues()
    },
    staleTime: 5000, // Consider data stale after 5 seconds
    refetchOnWindowFocus: true,
  })
}

/**
 * Hook for fetching message analysis
 */
export function useMessageAnalysis(timeRange?: TimeRange) {
  return useQuery({
    queryKey: ['message-analysis', timeRange],
    queryFn: async () => {
      return await historyService.getMessageAnalysis(timeRange)
    },
    staleTime: 0,
    refetchOnWindowFocus: true,
    // Always enabled - will fetch all data if no timeRange provided
  })
}

/**
 * Hook for fetching message performance metrics
 */
export function useMessagePerformance(timeRange?: TimeRange) {
  return useQuery({
    queryKey: ['message-performance', timeRange],
    queryFn: async () => {
      return await historyService.getMessagePerformance(timeRange)
    },
    staleTime: 0,
    refetchOnWindowFocus: true,
    // Always enabled - will fetch all data if no timeRange provided
  })
}

/**
 * Hook for fetching message length distribution
 */
export function useMessageDistribution(timeRange?: TimeRange) {
  return useQuery({
    queryKey: ['message-distribution', timeRange],
    queryFn: async () => {
      return await historyService.getMessageLengthDistribution(timeRange)
    },
    staleTime: 0,
    refetchOnWindowFocus: true,
    // Always enabled - will fetch all data if no timeRange provided
  })
}

/**
 * Hook for fetching provider/model statistics
 */
export function useProviderModelStats(timeRange?: TimeRange) {
  return useQuery({
    queryKey: ['provider-model-stats', timeRange],
    queryFn: async () => {
      return await historyService.getProviderModelStats(timeRange)
    },
    staleTime: 0,
    refetchOnWindowFocus: true,
    // Always enabled - will fetch all data if no timeRange provided
  })
}

/**
 * Hook for fetching session analysis
 */
export function useSessionAnalysis(limit: number = 10) {
  return useQuery({
    queryKey: ['session-analysis', limit],
    queryFn: async () => {
      return await historyService.getLastSessionsAnalysis(limit)
    },
    staleTime: 0,
    refetchOnWindowFocus: true,
    enabled: limit > 0, // Only fetch when limit is valid
  })
}

/**
 * Hook for fetching session summary
 */
export function useSessionSummary(limit: number = 10) {
  return useQuery({
    queryKey: ['session-summary', limit],
    queryFn: async () => {
      return await historyService.getSessionSummary(limit)
    },
    staleTime: 0,
    refetchOnWindowFocus: true,
  })
}
