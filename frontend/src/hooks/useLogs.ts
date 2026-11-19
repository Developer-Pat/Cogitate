import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { logsService } from '../services';
import type { LogFilter } from '../types';

/**
 * Hook for fetching and managing system logs
 *
 * Features:
 * - Only refreshes when page is actively viewed (saves resources)
 * - Fast 1-second refresh for active monitoring
 * - Loads 100 logs by default (pagination)
 * - Initial load on page view
 */
export function useLogs(filters: LogFilter = {}) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return useQuery<any>({
    queryKey: ['logs', filters],
    queryFn: async () => {
      const response = await logsService.getLogs(filters, filters.page, filters.page_size);

      // Log error if present
      if (response.error) {
        throw new Error(response.error.message);
      }
      return response.data;
    },
    retry: (_failureCount: number, _error: Error) => {
      return false // Don't retry on errors to prevent loops
    },
    enabled: true,
    refetchInterval: 1000, // Refresh every 1 second when page is active
    refetchIntervalInBackground: false, // Don't refresh when tab is inactive
    refetchOnWindowFocus: true, // Refresh when user returns to page
    staleTime: 0, // Always consider data stale (force refresh)
  });
}

/**
 * Hook for fetching available log sources
 */
export function useLogSources() {
  return useQuery({
    queryKey: ['log-sources'],
    queryFn: async () => {
      const response = await logsService.getLogSources();
      if (response.error) {
        throw new Error(response.error.message);
      }
      return response.data;
    },
    staleTime: 300000, // Consider data stale after 5 minutes
  });
}

/**
 * Hook for fetching log statistics
 * Syncs with logs refresh rate for consistent dashboard
 */
export function useLogStats() {
  return useQuery({
    queryKey: ['log-stats-v2'],
    queryFn: async () => {
      const response = await logsService.getLogStats();
      if (response.error) {
        throw new Error(response.error.message);
      }
      return response.data;
    },
    refetchInterval: 1000, // Sync with logs (1 second)
    refetchIntervalInBackground: false, // Don't refresh when tab is inactive
    refetchOnWindowFocus: true, // Refresh when user returns to page
  });
}

/**
 * Hook for clearing logs (admin only)
 */
export function useClearLogs() {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: async () => {
      const response = await logsService.clearLogs();
      if (response.error) {
        throw new Error(response.error.message);
      }
      return response.data;
    },
    onSuccess: () => {
      // Invalidate all log-related queries
      queryClient.invalidateQueries({ queryKey: ['logs'] });
      queryClient.invalidateQueries({ queryKey: ['log-stats'] });
    },
  });

  return mutation;
}

