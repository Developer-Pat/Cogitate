/**
 * Tool Permissions Manager Modal
 *
 * Main modal for managing tool-collection permissions.
 * Allows setting default access and managing collection-specific permissions.
 */

import React, { useState, useEffect } from 'react'
import type { PermissionLevel, ToolPermissionsResponse } from '@/types/toolPermissions'
import { PERMISSION_LEVELS } from '@/types/toolPermissions'
import { toolPermissionsService } from '@/services/domain/ToolPermissionsService'
import { useNotificationStore } from '@/stores/notificationStore'
import { CollectionPermissionRow } from './CollectionPermissionRow'
import { PermissionBadge } from './PermissionBadge'

interface ToolPermissionsManagerProps {
  toolId: string
  toolName: string
  onClose: () => void
  onPermissionsUpdated: () => void
}

export const ToolPermissionsManager: React.FC<ToolPermissionsManagerProps> = ({
  toolId,
  toolName,
  onClose,
  onPermissionsUpdated,
}) => {
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [permissions, setPermissions] = useState<ToolPermissionsResponse | null>(null)
  const [defaultAccess, setDefaultAccess] = useState<PermissionLevel>('read')
  const [showAddCollection, setShowAddCollection] = useState(false)
  const [selectedCollectionId, setSelectedCollectionId] = useState<string>('')
  const [availableCollections, setAvailableCollections] = useState<Array<{ id: string; name: string }>>([])

  // Load current permissions
  useEffect(() => {
    loadPermissions()
    loadAvailableCollections()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [toolId])

  const loadPermissions = async () => {
    try {
      setIsLoading(true)
      const response = await toolPermissionsService.getToolPermissions(toolId)
      setPermissions(response)
      setDefaultAccess(response.default_access)
    } catch (error) {
      console.error('Failed to load permissions:', error)
      useNotificationStore.getState().addError(
        'Failed to Load Permissions',
        'Could not load tool permissions. Please try again.'
      )
    } finally {
      setIsLoading(false)
    }
  }

  const loadAvailableCollections = async () => {
    try {
      // For now, we'll use a placeholder - in real implementation,
      // this would fetch collections that don't have permissions yet
      const response = await toolPermissionsService.getAvailableCollections(toolId)
      setAvailableCollections(response)
    } catch (error) {
      // Silently fail - user can still manage existing permissions
      console.debug('Could not load available collections:', error)
    }
  }

  const handleDefaultAccessChange = (newLevel: PermissionLevel) => {
    setDefaultAccess(newLevel)
  }

  const handlePermissionChange = async (collectionId: string, newLevel: PermissionLevel) => {
    try {
      await toolPermissionsService.setCollectionPermission(toolId, collectionId, newLevel)
      
      // Update local state
      if (permissions) {
        const updatedPermissions = permissions.permissions.map(p =>
          p.collection_id === collectionId
            ? { ...p, permission_level: newLevel, updated_at: new Date().toISOString() }
            : p
        )
        setPermissions({
          ...permissions,
          permissions: updatedPermissions,
        })
      }

      useNotificationStore.getState().addSuccess(
        'Permission Updated',
        `Collection permission updated to ${PERMISSION_LEVELS[newLevel].label}`
      )
    } catch (error) {
      console.error('Failed to update permission:', error)
      useNotificationStore.getState().addError(
        'Failed to Update Permission',
        'Could not update collection permission. Please try again.'
      )
    }
  }

  const handleRemovePermission = async (collectionId: string) => {
    if (!confirm('Remove this collection\'s permission? Users in this collection will lose access.')) {
      return
    }

    try {
      await toolPermissionsService.removeCollectionPermission(toolId, collectionId)
      
      // Update local state
      if (permissions) {
        const updatedPermissions = {
          ...permissions,
          permissions: permissions.permissions.filter(p => p.collection_id !== collectionId),
          total: permissions.total - 1,
        }
        setPermissions(updatedPermissions)
      }

      useNotificationStore.getState().addSuccess(
        'Permission Removed',
        'Collection permission removed successfully'
      )
    } catch (error) {
      console.error('Failed to remove permission:', error)
      useNotificationStore.getState().addError(
        'Failed to Remove Permission',
        'Could not remove collection permission. Please try again.'
      )
    }
  }

  const handleAddCollection = async () => {
    if (!selectedCollectionId) return

    try {
      await toolPermissionsService.setCollectionPermission(toolId, selectedCollectionId, 'read')
      
      // Reload permissions to get updated list
      await loadPermissions()
      await loadAvailableCollections()
      
      setSelectedCollectionId('')
      setShowAddCollection(false)

      useNotificationStore.getState().addSuccess(
        'Permission Added',
        'Collection permission added successfully'
      )
    } catch (error) {
      console.error('Failed to add permission:', error)
      useNotificationStore.getState().addError(
        'Failed to Add Permission',
        'Could not add collection permission. Please try again.'
      )
    }
  }

  const handleSave = async () => {
    try {
      setIsSaving(true)
      
      await toolPermissionsService.updateToolPermissions(toolId, {
        default_access: defaultAccess,
        permissions: permissions?.permissions.map(p => ({
          collection_id: p.collection_id,
          permission_level: p.permission_level,
        })) || [],
      })

      useNotificationStore.getState().addSuccess(
        'Permissions Saved',
        'Tool permissions updated successfully'
      )
      
      onPermissionsUpdated()
      onClose()
    } catch (error) {
      console.error('Failed to save permissions:', error)
      useNotificationStore.getState().addError(
        'Failed to Save Permissions',
        'Could not save tool permissions. Please try again.'
      )
    } finally {
      setIsSaving(false)
    }
  }

  if (isLoading) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9999]">
        <div className="bg-base-200 rounded-lg shadow-xl p-6">
          <span className="loading loading-lg"></span>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9999]">
      <div className="bg-base-200 rounded-lg shadow-xl w-[600px] max-w-full mx-4 max-h-[80vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-base-300 sticky top-0 bg-base-200 z-10">
          <div>
            <h2 className="text-2xl font-bold text-base-content">Tool Permissions</h2>
            <p className="text-sm text-readout mt-1">
              Manage access for "{toolName}"
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-base-content/50 hover:text-base-content/70"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Default Access */}
          <div className="p-4 bg-base-300 rounded-lg">
            <h3 className="text-sm font-medium text-base-content mb-3">
              Default Access Level
            </h3>
            <div className="flex items-center gap-4">
              <select
                value={defaultAccess}
                onChange={(e) => handleDefaultAccessChange(e.target.value as PermissionLevel)}
                className="select select-bordered w-full max-w-xs"
              >
                {(Object.keys(PERMISSION_LEVELS) as PermissionLevel[]).map((level) => (
                  <option key={level} value={level}>
                    {PERMISSION_LEVELS[level].label} - {PERMISSION_LEVELS[level].description}
                  </option>
                ))}
              </select>
              <div className="flex-1 text-sm text-readout">
                Users without explicit access will get this permission level
              </div>
            </div>
          </div>

          {/* Collection Permissions */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-medium text-base-content">
                Collection Access
              </h3>
              {!showAddCollection && availableCollections.length > 0 && (
                <button
                  onClick={() => setShowAddCollection(true)}
                  className="btn btn-outline btn-xs"
                >
                  Add Collection
                </button>
              )}
            </div>

            {/* Add Collection Form */}
            {showAddCollection && (
              <div className="p-4 border border-base-300 rounded mb-4 flex gap-2 items-center">
                <select
                  value={selectedCollectionId}
                  onChange={(e) => setSelectedCollectionId(e.target.value)}
                  className="select select-bordered flex-1"
                >
                  <option value="">Select a collection...</option>
                  {availableCollections.map((coll) => (
                    <option key={coll.id} value={coll.id}>
                      {coll.name}
                    </option>
                  ))}
                </select>
                <button
                  onClick={handleAddCollection}
                  className="btn btn-primary btn-sm"
                  disabled={!selectedCollectionId}
                >
                  Add
                </button>
                <button
                  onClick={() => {
                    setShowAddCollection(false)
                    setSelectedCollectionId('')
                  }}
                  className="btn btn-neutral btn-ghost btn-sm"
                >
                  Cancel
                </button>
              </div>
            )}

            {/* Permissions Table */}
            {permissions && permissions.permissions.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="table w-full">
                  <thead className="bg-base-300">
                    <tr>
                      <th>Collection</th>
                      <th>Permission</th>
                      <th className="text-center">Items</th>
                      <th className="text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {permissions.permissions.map((permission) => (
                      <CollectionPermissionRow
                        key={permission.collection_id}
                        permission={permission}
                        onPermissionChange={handlePermissionChange}
                        onRemove={handleRemovePermission}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-center py-8 text-readout">
                <p className="text-sm">No collection-specific permissions set</p>
                <p className="text-xs mt-1">All users will have the default access level</p>
              </div>
            )}
          </div>

          {/* Access Summary */}
          {permissions && permissions.total > 0 && (
            <div className="p-4 bg-base-300 rounded-lg">
              <h3 className="text-sm font-medium text-base-content mb-2">
                Access Summary
              </h3>
              <p className="text-sm text-readout">
                {permissions.total} collection{permissions.total !== 1 ? 's' : ''} can access this tool
              </p>
              <div className="flex gap-2 mt-3">
                <PermissionBadge level={defaultAccess} showLabel={true} />
                <span className="text-sm text-readout self-center">
                  Default access for all users
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-base-300 flex justify-end gap-2 sticky bottom-0 bg-base-200">
          <button onClick={onClose} className="btn btn-neutral btn-ghost btn-sm" disabled={isSaving}>
            Cancel
          </button>
          <button onClick={handleSave} className="btn btn-primary btn-sm" disabled={isSaving}>
            {isSaving ? (
              <>
                <span className="loading loading-spinner loading-sm"></span>
                Saving...
              </>
            ) : (
              'Save Changes'
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

export default ToolPermissionsManager
