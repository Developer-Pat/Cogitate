import { apiClient } from './apiClient';
import { globalLogStore } from './logStoreInstance';
import { frontendLoggingService } from './frontendLoggingService';
import type { ApiResponse, LogEntry, LogFilter, PaginatedResponse } from '../types';
import type { ILogsService } from './domains/system/logsService';

/**
 * Logs Service - Handles system logs and events endpoints
 *
 * Now connects to backend API for persistent storage while maintaining
 * in-memory store as cache/fallback.
 */
export const logsService: ILogsService = {
  /**
   * Get paginated logs with filtering
   *
   * Fetches from backend API with in-memory fallback
   */
  async getLogs(filters: LogFilter = {}, _page?: number, pageSize?: number): Promise<ApiResponse<PaginatedResponse<LogEntry>>> {
    try {
      // Build query parameters for file-based endpoint
      // Use 'n' parameter to get more logs for better filtering

      const pageSizeNum = pageSize || filters.page_size || filters.limit || 100;
      const params = new URLSearchParams();
      
      // Use 'n' to get enough logs for filtering (file endpoint doesn't paginate)
      params.set('n', String(Math.min(pageSizeNum * 10, 1000))); // Get up to 1000 logs

      // Handle level filter
      if (filters.level) {
        const levelValue = Array.isArray(filters.level) ? filters.level[0] : filters.level;
        if (levelValue) {
          params.set('level', levelValue);
        }
      }
      
      // Handle source filter
      if (filters.source) {
        const sourceValue = Array.isArray(filters.source) ? filters.source[0] : filters.source;
        if (sourceValue && sourceValue !== 'all') {
          // Map the FILE sources to the log_type parameter. `console` and
          // `vite` are the launcher's unmanaged captures (2026-09-12) — they
          // are the files that actually broke, and until now the UI could not
          // reach them at all. Everything else is a log-line `source` name.
          if (['frontend', 'backend', 'console', 'vite'].includes(sourceValue)) {
            params.set('log_type', sourceValue);
          } else {
            params.set('source', sourceValue);
          }
        }
      }
      
      // Search filter (full-text)
      if (filters.search) {
        params.set('search', filters.search);
      }
      
      // Time range filters
      if (filters.from) params.set('from', filters.from);
      if (filters.to) params.set('to', filters.to);
      if (filters.session_id) params.set('session_id', filters.session_id);

      // Fetch from FILE-based endpoint (not database)
      const endpoint = `/api/v1/logs/file/recent?${params.toString()}`;
      const response = await apiClient.get<{items: LogEntry[]}>(endpoint, { timeout: 30000 });

      if (response.data) {
        const items = response.data.items || [];
        const normalizedItems = items.map(item => ({
          ...item,
          level: item.level?.toLowerCase() as LogEntry['level']
        }));

        const transformedData: PaginatedResponse<LogEntry> = {
          data: normalizedItems,
          pagination: {
            page: 1,
            limit: normalizedItems.length,
            total: normalizedItems.length
          },
          has_more: false
        };

        // Also update in-memory store as cache (only if not fetching logs themselves to prevent loops)
        const currentPath = window.location.pathname;
        const isLogsPage = currentPath.includes('/logs');
        if (!isLogsPage) {
          normalizedItems.forEach(log => globalLogStore.addLog(log));
        }

        return {
          data: transformedData,
          status: response.status || 200,
          timestamp: new Date().toISOString()
        };
      }
      
      // Fallback to in-memory store
      const allLogs = globalLogStore.getLogs(filters);
      const offset = filters.offset || 0;
      const limit = filters.limit || 50;
      const paginatedLogs = allLogs.slice(offset, offset + limit);

      return {
        data: {
          data: paginatedLogs,
          pagination: {
            page: Math.floor(offset / limit) + 1,
            limit,
            total: allLogs.length
          }
        },
        status: 200,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      frontendLoggingService.error('LogsService', 'Error getting logs from backend, falling back to in-memory store', error);

      // Fallback to in-memory store
      const allLogs = globalLogStore.getLogs(filters);
      const offset = filters.offset || 0;
      const limit = filters.limit || 50;
      const paginatedLogs = allLogs.slice(offset, offset + limit);

      return {
        data: {
          data: paginatedLogs,
          pagination: {
            page: Math.floor(offset / limit) + 1,
            limit,
            total: allLogs.length
          }
        },
        status: 200,
        timestamp: new Date().toISOString()
      };
    }
  },

  /**
   * Get a specific log entry by ID
   */
  async getLogById(id: string): Promise<ApiResponse<LogEntry>> {
    try {
      // Try to get from backend first with timeout
      const response = await apiClient.get<LogEntry>(`/api/v1/logs/${id}`, { timeout: 10000 });
      
      if (response.data) {
        // Update in-memory store
        globalLogStore.addLog(response.data);
        return {
          data: response.data,
          status: 200,
          timestamp: new Date().toISOString()
        };
      }
      
      // Fallback to in-memory store
      const log = globalLogStore.getLogById(id);
      if (!log) {
        return {
          data: undefined as unknown as LogEntry,
          status: 404,
          timestamp: new Date().toISOString(),
          error: {
            code: 'not_found',
            message: 'Log entry not found'
          }
        };
      }
      return {
        data: log,
        status: 200,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      frontendLoggingService.error('LogsService', 'Error getting log', error);
      // Fallback to in-memory store
      const log = globalLogStore.getLogById(id);
      if (!log) {
        return {
          data: undefined as unknown as LogEntry,
          status: 404,
          timestamp: new Date().toISOString(),
          error: {
            code: 'not_found',
            message: 'Log entry not found'
          }
        };
      }
      return {
        data: log,
        status: 200,
        timestamp: new Date().toISOString()
      };
    }
  },

  /**
   * Get available log sources
   */
  async getLogSources(): Promise<ApiResponse<{ value: string; label: string; count: number }[]>> {
    try {
      const response = await apiClient.get<{ sources: string[]; total: number }>('/api/v1/logs/sources', { timeout: 10000 });

      if (response.data) {
        return {
          data: response.data.sources.map(s => ({ value: s, label: s, count: 0 })),
          status: 200,
          timestamp: new Date().toISOString()
        };
      }

      // Fallback to in-memory store
      const sources = globalLogStore.getSources();
      return {
        data: sources.map(s => ({ value: s, label: s, count: 0 })),
        status: 200,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      frontendLoggingService.error('LogsService', 'Error getting log sources', error);
      const sources = globalLogStore.getSources();
      return {
        data: sources.map(s => ({ value: s, label: s, count: 0 })),
        status: 200,
        timestamp: new Date().toISOString()
      };
    }
  },

  /**
   * Get log statistics
   */
  async getLogStats(): Promise<ApiResponse<{
    total: number;
    byLevel: Record<string, number>;
    bySource: Record<string, number>;
    recentActivity: number;
    frontendLogs: number;
    backendLogs: number;
  }>> {
    try {
      // Fetch from FILE-based stats endpoint (not database)
      const response = await apiClient.get<{
        total_size_mb: number;
        archive_count: number;
        files: Record<string, {size_mb: number; exists: boolean}>;
      }>('/api/v1/logs/file/stats', { timeout: 10000 });

      if (response.data) {
        // Calculate stats from file data
        const files = response.data.files || {};
        const frontendSize = files['frontend.log']?.size_mb || 0;
        const backendSize = files['app.log']?.size_mb || 0;

        return {
          data: {
            total: response.data.total_size_mb,
            byLevel: {},
            bySource: {},
            recentActivity: 0,
            frontendLogs: frontendSize,
            backendLogs: backendSize
          },
          status: 200,
          timestamp: new Date().toISOString()
        };
      }

      // Fallback to in-memory store
      const stats = globalLogStore.getStats();
      return {
        data: { ...stats },
        status: 200,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      frontendLoggingService.error('LogsService', 'Error getting log stats', error);
      const stats = globalLogStore.getStats();
      return {
        data: stats,
        status: 200,
        timestamp: new Date().toISOString()
      };
    }
  },

  /**
   * Send a log entry to the backend
   *
   * Posts to backend API while maintaining in-memory store as cache
   */
  async sendLogToBackend(entry: {
    timestamp: string;
    level: string;
    source: string;
    message: string;
    context?: Record<string, unknown>;
    user_agent?: string;
    url?: string;
    session_id?: string;
    trace_id?: string;
  }): Promise<ApiResponse<{ id: string }>> {
    // ENABLED FOR DEBUGGING
    try {
      const response = await apiClient.post<{ id: number; timestamp: string; status: string }>(
        '/api/v1/logs/frontend',
        entry,
        { retries: 0, timeout: 5000, excludeFromOutageTracking: true }
      );

      return {
        data: { id: String(response.data?.id ?? 0) },
        status: 200,
        timestamp: new Date().toISOString()
      } as unknown as ApiResponse<{ id: string }>;
    } catch {
      return {
        data: { id: '0' },
        status: 500,
        timestamp: new Date().toISOString(),
        error: {
          code: 'backend_log_error',
          message: 'Backend unavailable'
        }
      };
    }
  },

  /**
   * Send batch logs to backend
   */
  async sendBatchLogsToBackend(entries: Array<{
    timestamp: string;
    level: string;
    source: string;
    message: string;
    context?: Record<string, unknown>;
    user_agent?: string;
    url?: string;
    session_id?: string;
    trace_id?: string;
  }>): Promise<ApiResponse<{ sent: number; failed: number }>> {
    try {
      const response = await apiClient.post<{ count: number; status: string }>(
        '/api/v1/logs/frontend/batch',
        entries
      );

      return {
        data: { sent: response.data?.count || 0, failed: 0 },
        status: 200,
        timestamp: new Date().toISOString()
      } as unknown as ApiResponse<{ sent: number; failed: number }>;
    } catch (error) {
      frontendLoggingService.error('LogsService', 'Failed to send batch logs to backend', error);
      return {
        data: { sent: 0, failed: entries.length },
        status: 500,
        timestamp: new Date().toISOString(),
        error: {
          code: 'backend_log_error',
          message: 'Failed to send batch logs to backend'
        }
      };
    }
  },

  /**
   * Export logs to file
   */
  async exportLogs(filters: LogFilter = {}, format: 'csv' | 'json' = 'csv'): Promise<ApiResponse<{ download_url: string }>> {
    try {
      // Get logs from backend
      const response = await this.getLogs(filters);
      const logs = response.data?.logs || response.data?.data || [];
      
      if (format === 'json') {
        const json = JSON.stringify(logs, null, 2);
        const blob = new Blob([json], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        
        return {
          data: {
            download_url: url
          },
          status: 200,
          timestamp: new Date().toISOString()
        };
      } else {
        const csv = convertLogsToCSV(logs);
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        
        return {
          data: {
            download_url: url
          },
          status: 200,
          timestamp: new Date().toISOString()
        };
      }
    } catch (error) {
      frontendLoggingService.error('LogsService', 'Error exporting logs', error);
      return {
        data: { download_url: '' },
        status: 500,
        timestamp: new Date().toISOString(),
        error: {
          code: 'logs_error',
          message: 'Failed to export logs'
        }
      };
    }
  },

  /**
   * Clear logs (admin only)
   */
  async clearLogs(_olderThan?: string): Promise<ApiResponse<{ message: string; deletedCount: number }>> {
    try {
      // Note: olderThan parameter is accepted but not used in in-memory store
      const countBefore = globalLogStore.getLength();
      globalLogStore.clearLogs();
      return {
        data: {
          message: 'Logs cleared successfully',
          deletedCount: countBefore
        },
        status: 200,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      frontendLoggingService.error('LogsService', 'Error clearing logs', error);
      return {
        data: { message: '', deletedCount: 0 },
        status: 500,
        timestamp: new Date().toISOString(),
        error: {
          code: 'logs_error',
          message: 'Failed to clear logs'
        }
      };
    }
  },

  /**
   * Add a log entry to the in-memory store (called by frontendLoggingService)
   */
  addLog(log: LogEntry) {
    globalLogStore.addLog(log);
  }
};

/**
 * Helper function to convert logs to CSV format
 */
function convertLogsToCSV(logs: LogEntry[]): string {
  const headers = ['Timestamp', 'Level', 'Source', 'Message', 'Context'];
  const rows = logs.map(log => [
    log.timestamp,
    log.level,
    log.source,
    log.message,
    JSON.stringify(log.context || {})
  ]);

  const csvContent = [
    headers.join(','),
    ...rows.map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(','))
  ].join('\n');

  return csvContent;
}