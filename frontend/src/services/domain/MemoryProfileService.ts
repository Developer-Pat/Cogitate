/**
 * MemoryProfileService - CRUD for memory profile configurations.
 *
 * Provides API client for managing memory profiles (strategy, window size,
 * persistence backend, compaction, summarization).
 */

import { apiClient } from '../apiClient';
import { frontendLoggingService } from '../frontendLoggingService';

/** Memory profile data from the API */
export interface MemoryProfile {
  id: number;
  name: string;
  description?: string | null;
  strategy: string;
  window_size: number;
  persistence: string;
  compaction_threshold?: number | null;
  summarization: boolean;
  config?: Record<string, unknown> | null;
  is_builtin: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

/** Payload for creating a memory profile */
export interface MemoryProfileCreate {
  name: string;
  description?: string | null;
  strategy?: string;
  window_size?: number;
  persistence?: string;
  compaction_threshold?: number | null;
  summarization?: boolean;
  config?: Record<string, unknown> | null;
}

/** Payload for updating a memory profile */
export interface MemoryProfileUpdate {
  name?: string;
  description?: string | null;
  strategy?: string;
  window_size?: number;
  persistence?: string;
  compaction_threshold?: number | null;
  summarization?: boolean;
  config?: Record<string, unknown> | null;
}

/**
 * MemoryProfileService
 */
export class MemoryProfileService {
  private basePath = '/api/v1/memory-profiles';

  /**
   * List all memory profiles.
   */
  async list(includeBuiltin: boolean = true): Promise<MemoryProfile[]> {
    try {
      const params = includeBuiltin ? '' : '?include_builtin=false';
      const response = await apiClient.get<MemoryProfile[]>(
        `${this.basePath}${params}`
      );
      if (!response.error && response.data) {
        return response.data;
      }
      throw new Error(response.error?.message || 'Failed to fetch memory profiles');
    } catch (error) {
      frontendLoggingService.error('MemoryProfileService', 'Failed to list profiles', error);
      throw error;
    }
  }

  /**
   * Get a memory profile by ID.
   */
  async get(id: number): Promise<MemoryProfile> {
    try {
      const response = await apiClient.get<MemoryProfile>(`${this.basePath}/${id}`);
      if (!response.error && response.data) {
        return response.data;
      }
      throw new Error(response.error?.message || `Memory profile not found: ${id}`);
    } catch (error) {
      frontendLoggingService.error('MemoryProfileService', `Failed to get profile ${id}`, error);
      throw error;
    }
  }

  /**
   * Create a new memory profile.
   */
  async create(data: MemoryProfileCreate): Promise<MemoryProfile> {
    try {
      const response = await apiClient.post<MemoryProfile>(`${this.basePath}`, data);
      if (!response.error && response.data) {
        return response.data;
      }
      throw new Error(response.error?.message || 'Failed to create memory profile');
    } catch (error) {
      frontendLoggingService.error('MemoryProfileService', 'Failed to create profile', error);
      throw error;
    }
  }

  /**
   * Update an existing memory profile.
   */
  async update(id: number, data: MemoryProfileUpdate): Promise<MemoryProfile> {
    try {
      const response = await apiClient.put<MemoryProfile>(`${this.basePath}/${id}`, data);
      if (!response.error && response.data) {
        return response.data;
      }
      throw new Error(response.error?.message || `Failed to update memory profile: ${id}`);
    } catch (error) {
      frontendLoggingService.error('MemoryProfileService', `Failed to update profile ${id}`, error);
      throw error;
    }
  }

  /**
   * Delete a memory profile.
   */
  async delete(id: number): Promise<void> {
    try {
      const response = await apiClient.delete(`${this.basePath}/${id}`);
      if (response.error) {
        throw new Error(response.error.message || `Failed to delete memory profile: ${id}`);
      }
    } catch (error) {
      frontendLoggingService.error('MemoryProfileService', `Failed to delete profile ${id}`, error);
      throw error;
    }
  }
}

/** Singleton instance */
export const memoryProfileService = new MemoryProfileService();
