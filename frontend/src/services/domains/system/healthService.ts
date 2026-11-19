/**
 * Enhanced Health Service - System Domain
 *
 * Service abstraction layer for system health monitoring with proper domain boundaries.
 */

import { apiClient } from '@/services/apiClient';
import { frontendLoggingService } from '@/services/frontendLoggingService'
import type { ApiResponse, SystemHealth, SystemMetrics, ServiceStatus } from '@/types';

/**
 * Health Service Interface
 */
export interface IHealthService {
  getSystemHealth(): Promise<ApiResponse<SystemHealth>>;
  checkHealth(): Promise<ApiResponse<{ status: string; service: string }>>;
  getHealthMetrics(): Promise<ApiResponse<SystemMetrics>>;
  getSystemStatus(): Promise<ApiResponse<{ status: string; uptime: number; version: string; python_version: string; platform: string; environment: string }>>;
  getSystemInfo(): Promise<ApiResponse<Record<string, unknown>>>;
  getHealthServices(): Promise<ApiResponse<ServiceStatus[]>>;
  getServiceStatus(): Promise<ApiResponse<ServiceStatus[]>>;
  getSystemMetrics(): Promise<ApiResponse<SystemMetrics>>;
}

/**
 * Health Service Implementation
 */
class HealthService implements IHealthService {
  private readonly basePath = '/api/v1/health';
  private readonly systemPath = '/api/v1/system';

  /**
   * Get comprehensive system health status
   */
  async getSystemHealth(): Promise<ApiResponse<SystemHealth>> {
    // Get basic health and metrics from backend
    const [healthResponse, statusResponse, metricsResponse] = await Promise.all([
      apiClient.get<{ status?: string; data?: Record<string, unknown> }>(this.basePath),
      apiClient.get<{ uptime?: number; version?: string }>(`${this.systemPath}/status`).catch(() => null),
      apiClient.get<SystemMetrics>(`${this.systemPath}/metrics`).catch(() => null)
    ]);

    // Handle backend response structure
    if (healthResponse.data && healthResponse.data.data) {
      const backendData = healthResponse.data.data;
      const metricsData = metricsResponse?.data || null;

      const transformedData: SystemHealth = {
        status: ((backendData.status as string) || 'unknown') as 'healthy' | 'degraded' | 'unhealthy',
        timestamp: (backendData.timestamp as string) || new Date().toISOString(),
        services: [],
        metrics: metricsData || {
          cpu: { usage: 0, cores: 8, loadAverage: [0.5, 0.3, 0.2] },
          memory: { total: 16000000000, used: 8000000000, free: 8000000000, usage: 50 },
          disk: { total: 500000000000, used: 250000000000, free: 250000000000, usage: 50 },
          network: { bytesIn: 0, bytesOut: 0, connections: 0 }
        },
        uptime: statusResponse?.data?.uptime || (backendData.uptime as number) || 0,
        version: statusResponse?.data?.version || (backendData.version as string) || '1.0.0'
      };

      return {
        data: transformedData,
        status: healthResponse.status,
        timestamp: healthResponse.timestamp
      };
    }

    return healthResponse as ApiResponse<SystemHealth>;
  }

  /**
   * Basic health check
   */
  async checkHealth(): Promise<ApiResponse<{ status: string; service: string }>> {
    return await apiClient.get<{ status: string; service: string }>(this.basePath);
  }

  /**
   * Get detailed health metrics
   * Uses real backend endpoint /system/metrics
   */
  async getHealthMetrics(): Promise<ApiResponse<SystemMetrics>> {
    return await apiClient.get<SystemMetrics>(`${this.systemPath}/metrics`);
  }

  /**
   * Get system status (uptime, version, platform)
   * Uses real backend endpoint /system/status
   */
  async getSystemStatus(): Promise<ApiResponse<{ status: string; uptime: number; version: string; python_version: string; platform: string; environment: string }>> {
    return await apiClient.get<{ status: string; uptime: number; version: string; python_version: string; platform: string; environment: string }>(`${this.systemPath}/status`);
  }

  /**
   * Get detailed system information
   * Uses real backend endpoint /system/info
   */
  async getSystemInfo(): Promise<ApiResponse<Record<string, unknown>>> {
    return await apiClient.get<Record<string, unknown>>(`${this.systemPath}/info`);
  }

  /**
   * Get health status of individual services
   * TODO: Implement /health/services backend endpoint
   * Currently returns empty array - no backend implementation
   */
  async getHealthServices(): Promise<ApiResponse<ServiceStatus[]>> {
    frontendLoggingService.warning('healthService', 'getHealthServices(): Backend endpoint not implemented. Returning empty services list.');
    return {
      data: [],
      status: 200,
      timestamp: new Date().toISOString()
    };
  }

  /**
   * Get service status (alias for getHealthServices)
   */
  async getServiceStatus(): Promise<ApiResponse<ServiceStatus[]>> {
    return this.getHealthServices();
  }

  /**
   * Get system metrics (alias for getHealthMetrics)
   */
  async getSystemMetrics(): Promise<ApiResponse<SystemMetrics>> {
    return this.getHealthMetrics();
  }
}

// Create and export singleton instance
export const healthService: IHealthService = new HealthService();

// Export for dependency injection
export default healthService;