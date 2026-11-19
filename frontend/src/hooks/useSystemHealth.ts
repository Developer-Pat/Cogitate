import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';
import { useSystemStore } from '../stores/systemStore';
import { useNotificationStore } from '../stores/notificationStore';
import { healthService } from '../services';
import { outageGate } from '../services/outageGate';
import type { SystemHealth } from '../types';

/**
 * Hook for fetching and managing system health data
 */
export function useSystemHealth() {
  const updateSystemHealth = useSystemStore((state) => state.updateSystemHealth);
  const addNotification = useNotificationStore((state) => state.addError);
  const addSuccessNotification = useNotificationStore((state) => state.addSuccess);
  
  const previousHealthRef = useRef<SystemHealth | null>(null);
  // THE ERROR-TRANSITION GUARD (2026-09-03, the outage dig): the
  // query.error effect below fired a 'Health Check Failed' toast on
  // EVERY poll failure (react-query re-creates the error object each
  // refetch) — during an outage that was one notification per 30s
  // poll, plus a message-center entry per firing. The guard fires
  // only on the error APPEARING (null -> error), never repeatedly.
  const wasErrorRef = useRef<boolean>(false);

  const query = useQuery<SystemHealth | undefined, Error>({
    queryKey: ['system-health'],
    queryFn: async () => {
      const response = await healthService.getSystemHealth();
      if (response.error) {
        throw new Error(response.error.message);
      }
      return response.data;
    },
    refetchInterval: 30000, // Refetch every 30 seconds
    staleTime: 15000, // Consider data stale after 15 seconds
  });

  // Handle health check errors and status changes
  useEffect(() => {
    if (query.error) {
      if (!wasErrorRef.current) {
        wasErrorRef.current = true;
        // THE EPISODE GATE (2026-09-04, the dedupe): the apiClient
        // + the indicator announce the same outage — the first
        // down-detector of an episode wins.
        if (outageGate.markDown()) {
          addNotification(
            'Health Check Failed',
            `Unable to check backend health: ${query.error.message}`,
            10000
          );
        }
      }
    } else {
      wasErrorRef.current = false;
    }
  }, [query.error, addNotification]);

  // Handle health status recovery notifications
  useEffect(() => {
    if (query.data) {
      const currentHealth = query.data;
      const previousHealth = previousHealthRef.current;

      // Show recovery notification if health improved from
      // unhealthy/degraded to healthy — the first recovery-detector
      // of the episode announces (the gate) + closes it.
      if (previousHealth &&
          previousHealth.status !== 'healthy' &&
          currentHealth.status === 'healthy' &&
          outageGate.markUp()) {
        addSuccessNotification(
          'Backend Health Restored',
          'Backend server is now healthy and responding normally.',
          5000
        );
      }

      // Update previous health reference
      previousHealthRef.current = currentHealth;
      
      // Update Zustand store
      updateSystemHealth(currentHealth);
    }
  }, [query.data, addSuccessNotification, updateSystemHealth]);

  return {
    ...query,
    systemHealth: query.data,
    isHealthy: query.data?.status === 'healthy',
    isDegraded: query.data?.status === 'degraded',
    isUnhealthy: query.data?.status === 'unhealthy',
  };
}

/**
 * Hook for fetching service status
 */
export function useServiceStatus() {
  return useQuery({
    queryKey: ['service-status'],
    queryFn: async () => {
      const response = await healthService.getServiceStatus();
      if (response.error) {
        throw new Error(response.error.message);
      }
      return response.data;
    },
    refetchInterval: 60000, // Refetch every minute
  });
}

/**
 * Hook for fetching system metrics
 */
export function useSystemMetrics() {
  return useQuery({
    queryKey: ['system-metrics'],
    queryFn: async () => {
      const response = await healthService.getSystemMetrics();
      if (response.error) {
        throw new Error(response.error.message);
      }
      return response.data;
    },
    refetchInterval: 10000, // Refetch every 10 seconds for real-time metrics
  });
}

/**
 * Hook for fetching uptime information
 */
export function useUptime() {
  return useQuery({
    queryKey: ['uptime'],
    queryFn: async () => {
      const response = await healthService.getSystemStatus();
      if (response.error) {
        throw new Error(response.error.message);
      }
      return response.data?.uptime ?? 0;
    },
    refetchInterval: 60000, // Refetch every minute
  });
}

/**
 * Hook for manual health check
 */
export function useHealthCheck() {
  const queryClient = useQueryClient();

  const checkHealth = async () => {
    const response = await healthService.checkHealth();
    if (response.error) {
      throw new Error(response.error.message);
    }
    
    // Invalidate and refetch system health data
    queryClient.invalidateQueries({ queryKey: ['system-health'] });
    
    return response.data;
  };

  return {
    checkHealth,
  };
}