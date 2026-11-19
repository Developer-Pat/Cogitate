/**
 * Scheduler Service - Phase 4
 *
 * Service for managing automatic model synchronization schedules.
 * Connects to backend API endpoints for scheduling operations.
 */

import { apiClient } from '@/services/apiClient';
import type {
  ISchedulerService,
  SyncScheduleResponse,
  SyncStatusResponse,
  SyncScheduleRequest,
} from '@/types/providers';
import { frontendLoggingService } from '@/services/frontendLoggingService';

/**
 * Scheduler Service Implementation
 */
class SchedulerService implements ISchedulerService {
  private readonly basePath = '/api/v1/providers/sync-schedule';

  /**
   * Get sync schedule for a provider
   */
  async getSyncSchedule(providerId: number): Promise<SyncScheduleResponse> {
    // Return mock data for invalid providerId or when backend not available
    if (!providerId || providerId === 0) {
      frontendLoggingService.debug('SchedulerService', 'Returning mock data for invalid providerId', { providerId })
      return {
        provider_id: providerId,
        sync_interval_hours: 24,
        last_sync_at: null,
        next_sync_at: null,
        sync_enabled: false,
        last_sync_status: 'idle'
      }
    }

    try {
      const response = await apiClient.get<SyncScheduleResponse>(`${this.basePath}/${providerId}`);

      if (response.error) {
        throw new Error(response.error.message);
      }

      return response.data!;
    } catch (error) {
      // Return mock data if backend endpoint not available
      frontendLoggingService.warning('SchedulerService', 'Backend endpoint not available, using mock data', { providerId, error })
      return {
        provider_id: providerId,
        sync_interval_hours: 24,
        last_sync_at: null,
        next_sync_at: null,
        sync_enabled: false,
        last_sync_status: 'idle'
      }
    }
  }

  /**
   * Set sync schedule for a provider
   */
  async setSyncSchedule(
    providerId: number,
    intervalHours: number
  ): Promise<SyncScheduleResponse> {
    if (!providerId || providerId === 0) {
      frontendLoggingService.warning('SchedulerService', 'Cannot set schedule for invalid providerId', { providerId })
      throw new Error('Invalid provider ID')
    }

    try {
      const request: SyncScheduleRequest = { sync_interval_hours: intervalHours };
      const response = await apiClient.post<SyncScheduleResponse>(
        `${this.basePath}/${providerId}`,
        request
      );

      if (response.error) {
        throw new Error(response.error.message);
      }

      return response.data!;
    } catch (error) {
      frontendLoggingService.error('SchedulerService', 'Failed to set sync schedule', { providerId, error })
      throw error
    }
  }

  /**
   * Disable automatic sync for a provider
   */
  async disableSync(providerId: number): Promise<void> {
    if (!providerId || providerId === 0) {
      frontendLoggingService.warning('SchedulerService', 'Cannot disable sync for invalid providerId', { providerId })
      throw new Error('Invalid provider ID')
    }

    try {
      const response = await apiClient.delete(`${this.basePath}/${providerId}`);

      if (response.error) {
        throw new Error(response.error.message);
      }
    } catch (error) {
      frontendLoggingService.error('SchedulerService', 'Failed to disable sync', { providerId, error })
      throw error
    }
  }

  /**
   * Run model synchronization now
   */
  async runSync(providerId: number): Promise<SyncStatusResponse> {
    if (!providerId || providerId === 0) {
      frontendLoggingService.warning('SchedulerService', 'Cannot run sync for invalid providerId', { providerId })
      throw new Error('Invalid provider ID')
    }

    try {
      const response = await apiClient.post<SyncStatusResponse>(
        `${this.basePath}/${providerId}/run`
      );

      if (response.error) {
        throw new Error(response.error.message);
      }

      return response.data!;
    } catch (error) {
      frontendLoggingService.error('SchedulerService', 'Failed to run sync', { providerId, error })
      // Return mock status on error
      return {
        provider_id: providerId,
        status: 'error',
        message: 'Backend endpoint not available',
        models_synced: 0,
        last_sync_at: null,
        next_sync_at: null
      }
    }
  }

  /**
   * Get current sync status for a provider
   */
  async getSyncStatus(providerId: number): Promise<SyncStatusResponse> {
    if (!providerId || providerId === 0) {
      frontendLoggingService.debug('SchedulerService', 'Returning mock status for invalid providerId', { providerId })
      return {
        provider_id: providerId,
        status: 'idle',
        message: 'No sync configured',
        models_synced: 0,
        last_sync_at: null,
        next_sync_at: null
      }
    }

    try {
      const response = await apiClient.get<SyncStatusResponse>(
        `${this.basePath}/status/${providerId}`
      );

      if (response.error) {
        throw new Error(response.error.message);
      }

      return response.data!;
    } catch (error) {
      frontendLoggingService.warning('SchedulerService', 'Backend endpoint not available, using mock status', { providerId, error })
      return {
        provider_id: providerId,
        status: 'idle',
        message: 'Backend not available',
        models_synced: 0,
        last_sync_at: null,
        next_sync_at: null
      }
    }
  }
}

// Create and export singleton instance
export const schedulerService = new SchedulerService();

export default schedulerService;
