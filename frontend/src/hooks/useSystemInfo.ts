import { useQuery } from '@tanstack/react-query';
import { healthService } from '../services';
import { logsService } from '../services';

/**
 * Hook for fetching system status
 */
export function useSystemStatus() {
  return useQuery({
    queryKey: ['system-status'],
    queryFn: async () => {
      const response = await healthService.getSystemStatus();
      if (response.error) {
        throw new Error(response.error.message);
      }
      return response.data;
    },
    refetchInterval: 30000, // 30 seconds
  });
}

/**
 * Hook for fetching system information
 */
export function useSystemInfo() {
  return useQuery({
    queryKey: ['system-info'],
    queryFn: async () => {
      const response = await healthService.getSystemInfo();
      if (response.error) {
        throw new Error(response.error.message);
      }
      return response.data;
    },
    refetchInterval: 300000, // 5 minutes (rarely changes)
  });
}

/**
 * Hook for fetching recent events/logs
 */
export function useRecentEvents() {
  return useQuery({
    queryKey: ['recent-events'],
    queryFn: async () => {
      const response = await logsService.getLogs({}, 1, 10);
      if (response.error) {
        throw new Error(response.error.message);
      }
      return response.data?.logs ?? [];
    },
    refetchInterval: 10000, // 10 seconds
  });
}
