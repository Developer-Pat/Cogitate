/**
 * useSyncSchedule Hook - Phase 4
 *
 * Hook for managing automatic model synchronization schedules.
 * Provides state management for sync scheduling operations.
 */

import { useState, useEffect, useCallback } from 'react';
import { schedulerService } from '../services/domains/providers/schedulerService';
import type {
  SyncScheduleResponse,
  SyncStatusResponse,
  UseSyncScheduleReturn,
} from '../types/providers';

/**
 * Hook for sync schedule management
 */
export const useSyncSchedule = (providerId: number): UseSyncScheduleReturn => {
  const [schedule, setScheduleState] = useState<SyncScheduleResponse | null>(null);
  const [syncStatus, setSyncStatus] = useState<SyncStatusResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  /**
   * Load sync schedule from the API
   */
  const loadSchedule = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const scheduleData = await schedulerService.getSyncSchedule(providerId);
      setScheduleState(scheduleData);
    } catch (err) {
      // 404 means no schedule configured yet, which is OK
      if (err instanceof Error && !err.message.includes('404')) {
        setError(err.message);
      }
      setScheduleState(null);
    } finally {
      setLoading(false);
    }
  }, [providerId]);

  /**
   * Load sync status from the API
   */
  const loadSyncStatus = useCallback(async () => {
    setError(null);

    try {
      const statusData = await schedulerService.getSyncStatus(providerId);
      setSyncStatus(statusData);
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      }
      setSyncStatus(null);
    }
  }, [providerId]);

  /**
   * Set sync schedule
   */
  const setSchedule = useCallback(
    async (intervalHours: number) => {
      setLoading(true);
      setError(null);

      try {
        const result = await schedulerService.setSyncSchedule(providerId, intervalHours);
        setScheduleState(result);
        await loadSyncStatus(); // Refresh status
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to set sync schedule');
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [providerId, loadSyncStatus]
  );

  /**
   * Disable sync schedule
   */
  const disableSchedule = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      await schedulerService.disableSync(providerId);
      await loadSchedule(); // Refresh schedule
      await loadSyncStatus(); // Refresh status
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to disable sync');
      throw err;
    } finally {
      setLoading(false);
    }
  }, [providerId, loadSchedule, loadSyncStatus]);

  /**
   * Run sync now
   */
  const runSync = useCallback(async (): Promise<SyncStatusResponse | null> => {
    setError(null);

    try {
      const result = await schedulerService.runSync(providerId);
      await loadSchedule(); // Refresh schedule
      await loadSyncStatus(); // Refresh status
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to run sync');
      return null;
    }
  }, [providerId, loadSchedule, loadSyncStatus]);

  /**
   * Get sync status
   */
  const getSyncStatus = useCallback(async () => {
    await loadSyncStatus();
  }, [loadSyncStatus]);

  // Load schedule and status on mount
  useEffect(() => {
    loadSchedule();
    loadSyncStatus();
  }, [loadSchedule, loadSyncStatus]);

  return {
    schedule,
    syncStatus,
    loading,
    error,
    setSchedule,
    disableSchedule,
    runSync,
    getSyncStatus,
  };
};

export default useSyncSchedule;
