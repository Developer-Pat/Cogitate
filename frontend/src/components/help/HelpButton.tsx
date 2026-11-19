/**
 * HelpButton Component.
 *
 * Context-aware help button that dispatches an 'open-help-modal' event.
 * When clicked, opens the HelpModal right-drawer with the appropriate
 * help content from the wiki.
 */

import React from 'react';
import { HelpCircle } from 'lucide-react';

export interface HelpButtonProps {
  /**
   * Context identifier for help content.
   * Maps to wiki/help/ pages matched by frontmatter 'category'.
   */
  context?: string;
  
  /**
   * Additional CSS classes.
   */
  className?: string;
  
  /**
   * Tooltip position.
   */
  tooltipPosition?: 'top' | 'bottom' | 'left' | 'right';
  
  /**
   * Button size.
   */
  size?: 'sm' | 'md' | 'lg';

  /**
   * Show the HelpCircle icon (default true).
   */
  showIcon?: boolean;

  /**
   * Show the label text (default true).
   */
  showLabel?: boolean;

  /**
   * Label text (default "Help").
   */
  label?: string;
}

/**
 * HelpButton component - provides context-aware help access.
 */
export function HelpButton({
  context,
  className = '',
  size = 'md',
  showIcon = true,
  showLabel = true,
  label = 'Help',
  tooltipPosition = 'top',
}: HelpButtonProps) {
  const sizeClasses = {
    sm: 'btn-xs',
    md: 'btn-sm',
    lg: 'btn-md',
  };

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    
    const currentContext = context || 'help_page';
    
    window.dispatchEvent(
      new CustomEvent('open-help-modal', {
        detail: {
          context: currentContext,
          documentTitle: 'Help',
          timestamp: new Date().toISOString(),
        },
      })
    );
  };

  return (
    <button
      onClick={handleClick}
      className={`btn rounded-lg bg-primary/20 text-primary border-primary/30 hover:bg-primary/30 hover:border-primary/40 ${sizeClasses[size]} gap-1.5 tooltip tooltip-${tooltipPosition} ${className}`}
      aria-label="Help"
      data-tip={label}
    >
      {showIcon && <HelpCircle size={size === 'sm' ? 16 : size === 'lg' ? 24 : 20} />}
      {showLabel && <span className="hidden sm:inline text-xs">{label}</span>}
    </button>
  );
}

export default HelpButton;
