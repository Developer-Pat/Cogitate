/**
 * Session Service - LLM Domain
 *
 * Service abstraction layer for session management with proper domain boundaries.
 */

import { apiClient } from '@/services/apiClient';
import type { ApiResponse } from '@/types';

/**
 * Session Service Interface
 */
export interface ISessionService {
  getSessions(): Promise<ApiResponse<unknown[]>>;
  getSessionById(id: string): Promise<ApiResponse<unknown>>;
  createSession(config: unknown): Promise<ApiResponse<unknown>>;
  updateSession(id: string, config: unknown): Promise<ApiResponse<unknown>>;
  deleteSession(id: string): Promise<ApiResponse<{ message: string }>>;
  getSessionStatus(id: string): Promise<ApiResponse<unknown>>;
  getActiveSessions(): Promise<ApiResponse<unknown[]>>;
  endSession(id: string): Promise<ApiResponse<{ message: string }>>;
}

/**
 * Session Service Implementation
 */
class SessionService implements ISessionService {
  private readonly basePath = '/api/v1/sessions';

  /**
   * Get all available sessions
   */
  async getSessions(): Promise<ApiResponse<unknown[]>> {
    return apiClient.get<unknown[]>(this.basePath);
  }

  /**
   * Get a specific session by ID
   */
  async getSessionById(id: string): Promise<ApiResponse<unknown>> {
    return apiClient.get<unknown>(`${this.basePath}/${id}`);
  }

  /**
   * Create a new session
   */
  async createSession(config: unknown): Promise<ApiResponse<unknown>> {
    return apiClient.post<unknown>(this.basePath, config);
  }

  /**
   * Update an existing session
   */
  async updateSession(id: string, config: unknown): Promise<ApiResponse<unknown>> {
    return apiClient.put<unknown>(`${this.basePath}/${id}`, config);
  }

  /**
   * Delete a session
   */
  async deleteSession(id: string): Promise<ApiResponse<{ message: string }>> {
    return apiClient.delete<{ message: string }>(`${this.basePath}/${id}`);
  }

  /**
   * Get session status
   */
  async getSessionStatus(id: string): Promise<ApiResponse<unknown>> {
    return apiClient.get<unknown>(`${this.basePath}/${id}/status`);
  }

  /**
   * Get active sessions
   */
  async getActiveSessions(): Promise<ApiResponse<unknown[]>> {
    return apiClient.get<unknown[]>(`${this.basePath}/active`);
  }

  /**
   * End a session
   */
  async endSession(id: string): Promise<ApiResponse<{ message: string }>> {
    return apiClient.post<{ message: string }>(`${this.basePath}/${id}/end`);
  }
}

// Create and export singleton instance
export const sessionService: ISessionService = new SessionService();

// Export for dependency injection
export default sessionService;