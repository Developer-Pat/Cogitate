/**
 * Tag Badge Component
 *
 * Displays a tool tag with appropriate color coding based on category.
 */

import React from 'react'
import {
  getTagBadgeClass,
  getTagLabel,
  getTagDescription,
} from '@/types/toolTags'

interface TagBadgeProps {
  tag: string
  showTooltip?: boolean
  size?: 'sm' | 'md' | 'lg'
  clickable?: boolean
  onClick?: (tag: string) => void
  className?: string
}

export const TagBadge: React.FC<TagBadgeProps> = ({
  tag,
  showTooltip = true,
  size = 'sm',
  clickable = false,
  onClick,
  className = '',
}) => {
  const badgeClass = getTagBadgeClass(tag)
  const label = getTagLabel(tag)
  const description = getTagDescription(tag)

  const sizeClasses = {
    sm: 'badge-sm text-xs',
    md: 'badge-md text-sm',
    lg: 'badge-lg text-base',
  }

  const handleClick = () => {
    if (clickable && onClick) {
      onClick(tag)
    }
  }

  const badge = (
    <div
      className={`badge ${badgeClass} ${sizeClasses[size]} ${clickable ? 'cursor-pointer hover:opacity-80' : ''} ${className}`}
      onClick={handleClick}
    >
      {label}
    </div>
  )

  if (!showTooltip || clickable) {
    return badge
  }

  return (
    <div className="tooltip tooltip-top" data-tip={description}>
      {badge}
    </div>
  )
}

export default TagBadge
