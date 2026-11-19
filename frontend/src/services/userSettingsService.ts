/**
 * User Settings Service
 *
 * Handles synchronization of user settings with the backend.
 * Provides methods to save, load, and manage user preferences persistence.
 */

import { apiClient } from './apiClient'
import { frontendLoggingService } from './frontendLoggingService'
import type { Settings } from '../types/settings'

interface UserSettingsResponse {
  user_key: string
  settings: Settings
  updated_at: string
}

interface UserSettingsRequest {
  settings: Settings
}

class UserSettingsService {
  private readonly basePath = '/api/v1/settings'

  /**
   * Get user settings from backend
   */
  async getSettings(userKey: string = 'default'): Promise<Settings> {
    try {
      const response = await apiClient.get<UserSettingsResponse>(
        `${this.basePath}?user_key=${userKey}`
      )
      if (!response.data) {
        throw new Error('No response data from server')
      }
      frontendLoggingService.debug('UserSettingsService', 'Settings fetched from backend', {
        userKey,
        updatedAt: response.data.updated_at
      })
      return response.data.settings
    } catch (error) {
      frontendLoggingService.error('UserSettingsService', 'Failed to get settings', error)
      throw error
    }
  }

  /**
   * Update user settings on backend
   */
  async updateSettings(
    settings: Settings,
    userKey: string = 'default'
  ): Promise<Settings> {
    try {
      const request: UserSettingsRequest = { settings }
      const response = await apiClient.put<UserSettingsResponse>(
        `${this.basePath}?user_key=${userKey}`,
        request
      )
      if (!response.data) {
        throw new Error('No response data from server')
      }
      frontendLoggingService.debug('UserSettingsService', 'Settings updated on backend', {
        userKey,
        updatedAt: response.data.updated_at
      })
      return response.data.settings
    } catch (error) {
      frontendLoggingService.error('UserSettingsService', 'Failed to update settings', error)
      throw error
    }
  }

  /**
   * Delete user settings
   */
  async deleteSettings(userKey: string = 'default'): Promise<void> {
    try {
      await apiClient.delete(`${this.basePath}?user_key=${userKey}`)
      frontendLoggingService.debug('UserSettingsService', 'Settings deleted from backend', {
        userKey
      })
    } catch (error) {
      frontendLoggingService.error('UserSettingsService', 'Failed to delete settings', error)
      throw error
    }
  }
}

export const userSettingsService = new UserSettingsService()
export default userSettingsService
