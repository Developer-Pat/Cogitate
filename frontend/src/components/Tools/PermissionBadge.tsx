/**
 * Permission Badge Component
 *
 * Displays a badge showing the permission level with icon and label.
 */

import React from 'react'
import type { PermissionLevel } from '@/types/toolPermissions'
import { getPermissionLevelInfo } from '@/types/toolPermissions'

interface PermissionBadgeProps {
  level: PermissionLevel
  showLabel?: boolean
  showTooltip?: boolean
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

export const PermissionBadge: React.FC<PermissionBadgeProps> = ({
  level,
  showLabel = true,
  showTooltip = true,
  size = 'sm',
  className = '',
}) => {
  const info = getPermissionLevelInfo(level)
  
  const sizeClasses = {
    sm: 'badge-sm text-xs',
    md: 'badge-md text-sm',
    lg: 'badge-lg text-base',
  }

  const badge = (
    <div className={`badge ${info.color} ${sizeClasses[size]} ${className} gap-1`}>
      {showLabel && <span>{info.label}</span>}
    </div>
  )

  if (!showTooltip) {
    return badge
  }

  return (
    <div className="tooltip tooltip-top" data-tip={info.description}>
      {badge}
    </div>
  )
}

export default PermissionBadge
