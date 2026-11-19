import React from 'react'

interface TooltipProps {
  content: string
  children: React.ReactNode
  position?: 'top' | 'bottom' | 'left' | 'right'
}

/**
 * Thin DaisyUI-tooltip wrapper (2026-09-06: this was a hand-rolled
 * JS-hover tooltip — state + timeout + absolutely-positioned bubble —
 * the DaisyUI-only audit's find. Same API, the native DaisyUI
 * machinery now (the .tooltip class + data-tip on the wrapper).
 */
export default function Tooltip({
  content,
  children,
  position = 'top',
}: TooltipProps) {
  const positionClass = {
    top: 'tooltip-top',
    bottom: 'tooltip-bottom',
    left: 'tooltip-left',
    right: 'tooltip-right',
  }[position]

  return (
    <div className={`tooltip ${positionClass}`} data-tip={content}>
      {children}
    </div>
  )
}
