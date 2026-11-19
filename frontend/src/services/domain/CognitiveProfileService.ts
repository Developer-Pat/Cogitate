/**
 * CognitiveProfileService - CRUD for cognitive pipeline configurations.
 *
 * Provides API client for managing cognitive profiles that bundle strategy
 * selectors and reference a memory profile.
 */

import { apiClient } from '../apiClient';
import { frontendLoggingService } from '../frontendLoggingService';

/** Cognitive profile data from the API */
export interface CognitiveProfile {
  id: number;
  name: string;
  description?: string | null;
  context_builder: string;
  executor: string;
  response_formatter: string;
  memory_profile_id?: number | null;
  memory_profile_name?: string | null;
  config?: Record<string, unknown> | null;
  is_builtin: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

/** Payload for creating a cognitive profile */
export interface CognitiveProfileCreate {
  name: string;
  description?: string | null;
  context_builder?: string;
  executor?: string;
  response_formatter?: string;
  memory_profile_id?: number | null;
  config?: Record<string, unknown> | null;
}

/** Payload for updating a cognitive profile */
export interface CognitiveProfileUpdate {
  name?: string;
  description?: string | null;
  context_builder?: string;
  executor?: string;
  response_formatter?: string;
  memory_profile_id?: number | null;
  config?: Record<string, unknown> | null;
}

/**
 * CognitiveProfileService
 */
export class CognitiveProfileService {
  private basePath = '/api/v1/cognitive-profiles';

  /**
   * List all cognitive profiles.
   */
  async list(includeBuiltin: boolean = true): Promise<CognitiveProfile[]> {
    try {
      const params = includeBuiltin ? '' : '?include_builtin=false';
      const response = await apiClient.get<CognitiveProfile[]>(
        `${this.basePath}${params}`
      );
      if (!response.error && response.data) {
        return response.data;
      }
      throw new Error(response.error?.message || 'Failed to fetch cognitive profiles');
    } catch (error) {
      frontendLoggingService.error('CognitiveProfileService', 'Failed to list profiles', error);
      throw error;
    }
  }

  /**
   * Get a cognitive profile by ID.
   */
  async get(id: number): Promise<CognitiveProfile> {
    try {
      const response = await apiClient.get<CognitiveProfile>(`${this.basePath}/${id}`);
      if (!response.error && response.data) {
        return response.data;
      }
      throw new Error(response.error?.message || `Cognitive profile not found: ${id}`);
    } catch (error) {
      frontendLoggingService.error('CognitiveProfileService', `Failed to get profile ${id}`, error);
      throw error;
    }
  }

  /**
   * Create a new cognitive profile.
   */
  async create(data: CognitiveProfileCreate): Promise<CognitiveProfile> {
    try {
      const response = await apiClient.post<CognitiveProfile>(`${this.basePath}`, data);
      if (!response.error && response.data) {
        return response.data;
      }
      throw new Error(response.error?.message || 'Failed to create cognitive profile');
    } catch (error) {
      frontendLoggingService.error('CognitiveProfileService', 'Failed to create profile', error);
      throw error;
    }
  }

  /**
   * Update an existing cognitive profile.
   */
  async update(id: number, data: CognitiveProfileUpdate): Promise<CognitiveProfile> {
    try {
      const response = await apiClient.put<CognitiveProfile>(`${this.basePath}/${id}`, data);
      if (!response.error && response.data) {
        return response.data;
      }
      throw new Error(response.error?.message || `Failed to update cognitive profile: ${id}`);
    } catch (error) {
      frontendLoggingService.error('CognitiveProfileService', `Failed to update profile ${id}`, error);
      throw error;
    }
  }

  /**
   * Delete a cognitive profile.
   */
  async delete(id: number): Promise<void> {
    try {
      const response = await apiClient.delete(`${this.basePath}/${id}`);
      if (response.error) {
        throw new Error(response.error.message || `Failed to delete cognitive profile: ${id}`);
      }
    } catch (error) {
      frontendLoggingService.error('CognitiveProfileService', `Failed to delete profile ${id}`, error);
      throw error;
    }
  }
}

/** Singleton instance */
export const cognitiveProfileService = new CognitiveProfileService();
