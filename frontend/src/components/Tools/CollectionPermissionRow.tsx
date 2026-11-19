/**
 * Collection Permission Row Component
 *
 * Displays a single collection permission entry in the permission manager.
 */

import React from 'react'
import type { PermissionLevel, ToolPermissionSummary } from '@/types/toolPermissions'
import { PERMISSION_LEVELS } from '@/types/toolPermissions'

interface CollectionPermissionRowProps {
  permission: ToolPermissionSummary
  onPermissionChange: (collectionId: string, newLevel: PermissionLevel) => void
  onRemove: (collectionId: string) => void
  isLoading?: boolean
}

export const CollectionPermissionRow: React.FC<CollectionPermissionRowProps> = ({
  permission,
  onPermissionChange,
  onRemove,
  isLoading = false,
}) => {

  return (
    <tr
      className="hover:bg-base-200 transition-colors"
    >
      {/* Collection Name */}
      <td>
        <div className="font-medium text-sm">{permission.collection_name}</div>
        <div className="text-xs text-readout">
          Updated {new Date(permission.updated_at).toLocaleDateString()}
        </div>
      </td>

      {/* Permission Level Dropdown */}
      <td>
        <div className="dropdown dropdown-top">
          <label tabIndex={0} className={`badge ${PERMISSION_LEVELS[permission.permission_level].color} gap-2 cursor-pointer`}>
            <span>{PERMISSION_LEVELS[permission.permission_level].label}</span>
            <svg className="w-3 h-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </label>
          <ul
            tabIndex={0}
            className="dropdown-content z-[1] menu p-2 shadow bg-base-100 rounded-box w-52"
          >
            {(Object.keys(PERMISSION_LEVELS) as PermissionLevel[]).map((level) => (
              <li key={level}>
                <a
                  onClick={() => onPermissionChange(permission.collection_id, level)}
                  className={permission.permission_level === level ? 'active' : ''}
                >
                  <div>
                    <div className="font-medium">{PERMISSION_LEVELS[level].label}</div>
                    <div className="text-xs opacity-60">{PERMISSION_LEVELS[level].description}</div>
                  </div>
                </a>
              </li>
            ))}
          </ul>
        </div>
      </td>

      {/* Member Count */}
      <td className="text-center">
        <span className="text-sm text-readout">
          {permission.member_count > 0 ? `${permission.member_count} items` : '—'}
        </span>
      </td>

      {/* Actions */}
      <td className="text-right">
        <button
          onClick={() => onRemove(permission.collection_id)}
          className="btn btn-xs btn-error btn-outline"
          disabled={isLoading}
        >
          Remove
        </button>
      </td>
    </tr>
  )
}

export default CollectionPermissionRow
