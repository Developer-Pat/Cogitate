/**
 * BadgeButton Component
 *
 * Compact pill-style button used for secondary actions like Help, Create, Sessions, Tools.
 * Uses design tokens from tokens.css for consistent theming across all DaisyUI themes.
 *
 * Usage:
 *   <BadgeButton onClick={...}>Help</BadgeButton>
 *   <BadgeButton size="sm" onClick={...}>‹</BadgeButton>
 *   <BadgeButton disabled>Tools</BadgeButton>
 */

import React from 'react'

export interface BadgeButtonProps {
  children: React.ReactNode
  onClick?: () => void
  disabled?: boolean
  size?: 'sm' | 'md'
  className?: string
  title?: string
  'aria-label'?: string
  type?: 'button' | 'submit' | 'reset'
}

export function BadgeButton({
  children,
  onClick,
  disabled = false,
  size = 'md',
  className = '',
  title,
  'aria-label': ariaLabel,
  type = 'button',
}: BadgeButtonProps) {
  const sizeClasses = size === 'sm'
    ? 'px-[var(--badge-btn-sm-padding-x)] py-[var(--badge-btn-sm-padding-y)] text-[var(--badge-btn-sm-font-size)]'
    : 'px-[var(--badge-btn-padding-x)] py-[var(--badge-btn-padding-y)] text-[var(--badge-btn-font-size)]'

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      title={title}
      aria-label={ariaLabel}
      className={`
        rounded-[var(--badge-btn-radius)]
        font-medium
        bg-[var(--badge-btn-bg)]
        text-[var(--badge-btn-text)]
        border border-[var(--badge-btn-border)]
        hover:bg-[var(--badge-btn-hover-bg)]
        transition-all
        disabled:opacity-[var(--badge-btn-disabled-opacity)]
        disabled:cursor-not-allowed
        ${sizeClasses}
        ${className}
      `}
    >
      {children}
    </button>
  )
}

export default BadgeButton
