/**
 * ToolPermissionsService - Manage tool-collection permissions.
 *
 * Provides API client for tool permission management endpoints.
 */

import type {
  PermissionLevel,
  ToolPermissionsResponse,
  ToolPermissionsUpdateRequest,
  PermissionCheckResponse,
  AccessibleToolsResponse,
  ToolCollectionPermission,
} from '@/types/toolPermissions'
import { apiClient } from '../apiClient'
import { frontendLoggingService } from '../frontendLoggingService'

/**
 * ToolPermissionsService - Manage tool permissions
 */
export class ToolPermissionsService {
  private basePath = '/api/v1/tools'

  /**
   * Get permissions for a specific tool.
   */
  async getToolPermissions(toolId: string): Promise<ToolPermissionsResponse> {
    try {
      const response = await apiClient.get<ToolPermissionsResponse>(
        `${this.basePath}/${toolId}/permissions`
      )

      if (response.error) {
        frontendLoggingService.error('ToolPermissionsService', 'Failed to get tool permissions', response.error)
        throw new Error(response.error.message)
      }

      frontendLoggingService.debug('ToolPermissionsService', `Got permissions for tool ${toolId}`, {
        total: response.data?.total
      })

      return response.data!
    } catch (error) {
      frontendLoggingService.error('ToolPermissionsService', 'Failed to get tool permissions', error)
      throw error
    }
  }

  /**
   * Update permissions for a tool.
   */
  async updateToolPermissions(
    toolId: string,
    updateData: ToolPermissionsUpdateRequest
  ): Promise<ToolPermissionsResponse> {
    try {
      const response = await apiClient.put<ToolPermissionsResponse>(
        `${this.basePath}/${toolId}/permissions`,
        updateData
      )

      if (response.error) {
        frontendLoggingService.error('ToolPermissionsService', 'Failed to update tool permissions', response.error)
        throw new Error(response.error.message)
      }

      frontendLoggingService.debug('ToolPermissionsService', `Updated permissions for tool ${toolId}`)

      return response.data!
    } catch (error) {
      frontendLoggingService.error('ToolPermissionsService', 'Failed to update tool permissions', error)
      throw error
    }
  }

  /**
   * Set permission for a specific collection.
   */
  async setCollectionPermission(
    toolId: string,
    collectionId: string,
    permissionLevel: PermissionLevel
  ): Promise<ToolCollectionPermission> {
    try {
      const response = await apiClient.post<ToolCollectionPermission>(
        `${this.basePath}/${toolId}/permissions/collections/${collectionId}?permission_level=${permissionLevel}`
      )

      if (response.error) {
        frontendLoggingService.error('ToolPermissionsService', 'Failed to set collection permission', response.error)
        throw new Error(response.error.message)
      }

      frontendLoggingService.debug('ToolPermissionsService', `Set permission for tool ${toolId}, collection ${collectionId}`)

      return response.data!
    } catch (error) {
      frontendLoggingService.error('ToolPermissionsService', 'Failed to set collection permission', error)
      throw error
    }
  }

  /**
   * Remove permission for a specific collection.
   */
  async removeCollectionPermission(
    toolId: string,
    collectionId: string
  ): Promise<void> {
    try {
      const response = await apiClient.delete(
        `${this.basePath}/${toolId}/permissions/collections/${collectionId}`
      )

      if (response.error) {
        frontendLoggingService.error('ToolPermissionsService', 'Failed to remove collection permission', response.error)
        throw new Error(response.error.message)
      }

      frontendLoggingService.debug('ToolPermissionsService', `Removed permission for tool ${toolId}, collection ${collectionId}`)
    } catch (error) {
      frontendLoggingService.error('ToolPermissionsService', 'Failed to remove collection permission', error)
      throw error
    }
  }

  /**
   * Check if a user has permission to access a tool.
   */
  async checkPermission(
    toolId: string,
    userId: string = 'default',
    requiredPermission: PermissionLevel = 'read'
  ): Promise<PermissionCheckResponse> {
    try {
      const response = await apiClient.get<PermissionCheckResponse>(
        `${this.basePath}/${toolId}/check?user_id=${userId}&permission=${requiredPermission}`
      )

      if (response.error) {
        frontendLoggingService.error('ToolPermissionsService', 'Failed to check permission', response.error)
        throw new Error(response.error.message)
      }

      return response.data!
    } catch (error) {
      frontendLoggingService.error('ToolPermissionsService', 'Failed to check permission', error)
      throw error
    }
  }

  /**
   * Get list of tools accessible to a user.
   */
  async getAccessibleTools(
    userId: string = 'default',
    minPermission: PermissionLevel = 'read',
    limit: number = 100,
    offset: number = 0
  ): Promise<AccessibleToolsResponse> {
    try {
      const params = new URLSearchParams()
      params.append('user_id', userId)
      params.append('permission', minPermission)
      params.append('limit', limit.toString())
      params.append('offset', offset.toString())

      const response = await apiClient.get<AccessibleToolsResponse>(
        `${this.basePath}/accessible?${params.toString()}`
      )

      if (response.error) {
        frontendLoggingService.error('ToolPermissionsService', 'Failed to get accessible tools', response.error)
        throw new Error(response.error.message)
      }

      return response.data!
    } catch (error) {
      frontendLoggingService.error('ToolPermissionsService', 'Failed to get accessible tools', error)
      throw error
    }
  }

  /**
   * Get available collections for adding permissions.
   * This is a helper method that fetches collections without permissions for this tool.
   */
  async getAvailableCollections(toolId: string): Promise<Array<{ id: string; name: string }>> {
    try {
      // For now, fetch all tool collections and filter on the frontend
      // In a real implementation, this would be a dedicated endpoint
      const collectionsService = await import('./CollectionsService')
      const response = await collectionsService.collectionsService.listCollections({
        entity_type: 'tool'
      })

      // Get current permissions to filter out collections that already have access
      const currentPermissions = await this.getToolPermissions(toolId)
      const currentCollectionIds = new Set(currentPermissions.permissions.map(p => p.collection_id))

      // Return collections that don't have permissions yet
      return response.collections
        .filter(c => !currentCollectionIds.has(c.id))
        .map(c => ({ id: c.id, name: c.name }))
    } catch (error) {
      // Return empty array on error
      console.debug('Could not load available collections:', error)
      return []
    }
  }
}

export const toolPermissionsService = new ToolPermissionsService()
