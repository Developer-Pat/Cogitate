/**
 * Logs Service - System Domain
 *
 * Service abstraction layer for log management with proper domain boundaries.
 */

import { apiClient } from '@/services/apiClient';
import { frontendLoggingService } from '@/services/frontendLoggingService'
import type { ApiResponse, LogEntry, LogFilter, PaginatedResponse } from '@/types';

/**
 * Logs Service Interface
 */
export interface ILogsService {
  getLogs(filters?: LogFilter, page?: number, pageSize?: number): Promise<ApiResponse<PaginatedResponse<LogEntry>>>;
  getLogSources(): Promise<ApiResponse<Array<{ value: string; label: string; count: number }>>>;
  getLogById(id: string): Promise<ApiResponse<LogEntry>>;
  clearLogs(olderThan?: string): Promise<ApiResponse<{ message: string; deletedCount: number }>>;
  getLogStats(): Promise<ApiResponse<{ total: number; byLevel: Record<string, number>; bySource: Record<string, number>; recentActivity: number; frontendLogs: number; backendLogs: number }>>;
  exportLogs(filters?: LogFilter, format?: 'csv' | 'json'): Promise<ApiResponse<{ download_url: string }>>;
  addLog(log: LogEntry): void;
  streamLogs?(callback: (log: LogEntry) => void): () => void;
  sendLogToBackend?(entry: { timestamp: string; level: string; source: string; message: string; context?: Record<string, unknown> }): Promise<ApiResponse<{ id: string }>>;
  sendBatchLogsToBackend?(logs: Array<{ timestamp: string; level: string; source: string; message: string; context?: Record<string, unknown> }>): Promise<ApiResponse<{ sent: number; failed: number }>>;
}

/**
 * Logs Service Implementation
 */
class LogsService implements ILogsService {
  private readonly basePath = '/api/v1/system/logs';

  /**
   * Get logs with filtering and pagination
   */
  async getLogs(filters?: LogFilter, page: number = 1, pageSize: number = 50): Promise<ApiResponse<{ logs: LogEntry[]; total: number; page: number; pageSize: number }>> {
    const params = new URLSearchParams();

    if (filters) {
      if (filters.level && Array.isArray(filters.level)) params.append('level', filters.level.join(','));
      else if (filters.level) params.append('level', filters.level);
      
      if (filters.source && Array.isArray(filters.source)) params.append('source', filters.source.join(','));
      else if (filters.source) params.append('source', filters.source);
      
      if (filters.startDate) params.append('startDate', filters.startDate);
      if (filters.endDate) params.append('endDate', filters.endDate);
      if (filters.search) params.append('search', filters.search);
      if (filters.user_id) params.append('userId', filters.user_id);
      if (filters.session_id) params.append('sessionId', filters.session_id);
    }

    params.append('page', page.toString());
    params.append('pageSize', pageSize.toString());

    return await apiClient.get<{ logs: LogEntry[]; total: number; page: number; pageSize: number }>(`${this.basePath}?${params}`);
  }

  /**
   * Get available log sources with counts
   */
  async getLogSources(): Promise<ApiResponse<Array<{ value: string; label: string; count: number }>>> {
    return await apiClient.get<Array<{ value: string; label: string; count: number }>>(`${this.basePath}/sources`);
  }

  /**
   * Clear logs (optionally older than specified date)
   */
  async clearLogs(olderThan?: string): Promise<ApiResponse<{ message: string; deletedCount: number }>> {
    const params = olderThan ? `?olderThan=${encodeURIComponent(olderThan)}` : '';
    return await apiClient.delete<{ message: string; deletedCount: number }>(`${this.basePath}/clear${params}`);
  }

  /**
   * Get log statistics
   */
  async getLogStats(): Promise<ApiResponse<{ total: number; byLevel: Record<string, number>; bySource: Record<string, number>; recentActivity: number; frontendLogs: number; backendLogs: number }>> {
    const response = await apiClient.get<{ total: number; by_level: Record<string, number>; by_source: Record<string, number>; recent_activity: number; frontend_logs: number; backend_logs: number }>(`${this.basePath}/stats`);
    if (response.data) {
      return {
        ...response,
        data: {
          total: response.data.total,
          byLevel: response.data.by_level,
          bySource: response.data.by_source,
          recentActivity: response.data.recent_activity,
          frontendLogs: response.data.frontend_logs,
          backendLogs: response.data.backend_logs
        }
      };
    }
    return response as unknown as ApiResponse<{
      total: number;
      byLevel: Record<string, number>;
      bySource: Record<string, number>;
      recentActivity: number;
      frontendLogs: number;
      backendLogs: number;
    }>;
  }

  /**
   * Stream logs in real-time (WebSocket implementation)
   */
  streamLogs(_callback: (log: LogEntry) => void): () => void {
    // TODO: Implement WebSocket connection for real-time log streaming
    frontendLoggingService.warning('logsService', 'Log streaming not yet implemented');

    // Return cleanup function
    return () => {
      frontendLoggingService.info('logsService', 'Log streaming cleanup');
    };
  }

  /**
   * Get a specific log entry by ID
   */
  async getLogById(id: string): Promise<ApiResponse<LogEntry>> {
    return await apiClient.get<LogEntry>(`${this.basePath}/${id}`);
  }

  /**
   * Export logs to file
   */
  async exportLogs(_filters: LogFilter = {}, _format: 'csv' | 'json' = 'csv'): Promise<ApiResponse<{ download_url: string }>> {
    // TODO: Implement actual file export
    frontendLoggingService.warning('logsService', 'Export logs not yet implemented');
    return {
      data: { download_url: '#' },
      status: 200,
      timestamp: new Date().toISOString()
    };
  }

  /**
   * Add a log entry to the in-memory store
   */
  addLog(log: LogEntry): void {
    // TODO: Implement in-memory log storage
    frontendLoggingService.info('logsService', 'Log added:', log as unknown as Record<string, unknown>);
  }
}

// Create and export singleton instance
export const logsService: ILogsService = new LogsService();

// Export for dependency injection
export default logsService;