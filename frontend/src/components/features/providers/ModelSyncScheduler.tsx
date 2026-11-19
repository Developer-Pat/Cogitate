/**
 * ModelSyncScheduler Component - Phase 4
 *
 * Component for managing automatic model synchronization schedules.
 * Allows users to set sync intervals and trigger manual syncs.
 */

import React, { useState } from 'react';
import type { SyncScheduleResponse, SyncStatusResponse } from '@/types/providers';

interface ModelSyncSchedulerProps {
  providerId: number;
  providerName: string;
  schedule?: SyncScheduleResponse | null;
  syncStatus?: SyncStatusResponse | null;
  onSetSchedule?: (intervalHours: number) => Promise<void>;
  onDisableSchedule?: () => Promise<void>;
  onRunSync?: () => Promise<SyncStatusResponse | null>;
  onRefreshStatus?: () => Promise<void>;
  loading?: boolean;
}

/**
 * ModelSyncScheduler Component
 */
const ModelSyncScheduler: React.FC<ModelSyncSchedulerProps> = ({
  providerId: _providerId,
  providerName: _providerName,
  schedule,
  syncStatus,
  onSetSchedule,
  onDisableSchedule,
  onRunSync,
  onRefreshStatus,
  loading = false,
}) => {
  const [selectedInterval, setSelectedInterval] = useState<number>(
    schedule?.sync_interval_hours || 168
  );
  const [isSyncing, setIsSyncing] = useState(false);

  /**
   * Sync interval options
   */
  const intervalOptions = [
    { value: 1, label: '1 hour' },
    { value: 6, label: '6 hours' },
    { value: 12, label: '12 hours' },
    { value: 24, label: '24 hours' },
    { value: 168, label: '7 days' },
  ];

  /**
   * Format datetime
   */
  const formatDateTime = (dateString: string | null) => {
    if (!dateString) return 'Never';
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  /**
   * Get status color
   */
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'success':
        return 'text-success';
      case 'pending':
        return 'text-warning';
      case 'error':
        return 'text-error';
      case 'disabled':
        return 'text-readout ';
      default:
        return 'text-readout ';
    }
  };

  /**
   * Handle interval change
   */
  const handleIntervalChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedInterval(Number(e.target.value));
  };

  /**
   * Handle save schedule
   */
  const handleSaveSchedule = async () => {
    if (!onSetSchedule) return;
    await onSetSchedule(selectedInterval);
  };

  /**
   * Handle disable sync
   */
  const handleDisableSync = async () => {
    if (!onDisableSchedule) return;
    await onDisableSchedule();
  };

  /**
   * Handle run sync now
   */
  const handleRunSync = async () => {
    if (!onRunSync) return;
    setIsSyncing(true);
    try {
      await onRunSync();
      await onRefreshStatus?.();
    } finally {
      setIsSyncing(false);
    }
  };

  return (
    <div className="bg-base-100 dark:bg-base-200 rounded-lg shadow p-4 border border-base-content/20 dark:border-base-content/20">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-base-content dark:text-base-content">
          Model Sync Schedule
        </h3>
        {schedule?.sync_enabled && (
          <span className="px-2 py-1 text-xs font-medium bg-success/10 text-success rounded-full">
            Enabled
          </span>
        )}
      </div>

      {/* Current Status */}
      {syncStatus && (
        <div className="mb-4 p-3 bg-base-200 dark:bg-base-200/50 rounded-lg">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-readout ">Status:</span>
            <span className={`text-sm font-medium ${getStatusColor(syncStatus.status)}`}>
              {syncStatus.status}
            </span>
          </div>
          <p className="text-sm text-readout ">{syncStatus.message}</p>
          {syncStatus.models_synced > 0 && (
            <p className="text-sm text-readout  mt-1">
              Models synced: {syncStatus.models_synced}
            </p>
          )}
        </div>
      )}

      {/* Schedule Settings */}
      <div className="space-y-4">
        {/* Interval Selector */}
        <div>
          <label className="block text-sm font-medium text-label  mb-2">
            Sync Interval
          </label>
          <select
            value={selectedInterval}
            onChange={handleIntervalChange}
            disabled={loading || !schedule?.sync_enabled}
            className="w-full px-3 py-2 border border-base-content/20 dark:border-base-content/20 rounded-lg focus:ring-2 focus:ring-primary dark:bg-base-200 dark:text-base-content disabled:opacity-50"
          >
            {intervalOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        {/* Time Info */}
        {schedule && (
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-readout ">Last Sync</p>
              <p className="text-base-content dark:text-base-content font-medium">
                {formatDateTime(schedule.last_sync_at)}
              </p>
            </div>
            <div>
              <p className="text-readout ">Next Sync</p>
              <p className="text-base-content dark:text-base-content font-medium">
                {formatDateTime(schedule.next_sync_at)}
              </p>
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex gap-2 pt-2">
          {schedule?.sync_enabled ? (
            <>
              <button
                onClick={handleSaveSchedule}
                disabled={loading || isSyncing}
                className="flex-1 px-3 py-2 text-sm text-base-content bg-primary rounded-lg hover:bg-info disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? 'Saving...' : 'Save Schedule'}
              </button>
              <button
                onClick={handleDisableSync}
                disabled={loading || isSyncing}
                className="px-3 py-2 text-sm text-disabled  bg-base-200 dark:bg-base-200 rounded-lg hover:bg-base-300 dark:hover:bg-base-content/60 disabled:opacity-50"
              >
                Disable
              </button>
            </>
          ) : (
            <button
              onClick={handleSaveSchedule}
              disabled={loading || isSyncing}
              className="flex-1 px-3 py-2 text-sm text-base-content bg-primary rounded-lg hover:bg-info disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Enable Sync
            </button>
          )}
        </div>

        {/* Run Sync Now */}
        <button
          onClick={handleRunSync}
          disabled={loading || isSyncing}
          className="w-full px-3 py-2 text-sm text-primary dark:text-primary/90 bg-primary/10 dark:bg-info/20 rounded-lg hover:bg-primary/10 dark:hover:bg-info/30 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isSyncing ? 'Syncing...' : 'Sync Now'}
        </button>
      </div>

      {/* Last Sync Status */}
      {schedule && schedule.last_sync_status && (
        <div className="mt-4 pt-4 border-t border-base-content/20 dark:border-base-content/20">
          <div className="flex items-center justify-between text-xs">
            <span className="text-readout ">Last Sync Status:</span>
            <span
              className={`font-medium ${
                schedule.last_sync_status === 'success'
                  ? 'text-success'
                  : schedule.last_sync_status === 'failed'
                  ? 'text-error'
                  : 'text-readout '
              }`}
            >
              {schedule.last_sync_status}
            </span>
          </div>
        </div>
      )}
    </div>
  );
};

export default ModelSyncScheduler;
