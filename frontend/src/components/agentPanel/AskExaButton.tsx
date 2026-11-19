/**
 * AskExaButton — opens the Exa panel with a CONTEXT payload.
 *
 * Mirror of HelpButton: dispatches an 'open-agent-panel' CustomEvent
 * with detail.context so the panel can seed its hand-off with where
 * you opened it from ("help me with these macro issues", "guide me
 * through setup", "why did this run fail?"...). One Exa, many
 * surfaces — context-injected per open (strategy: exa-roles-and-
 * surfaces.md).
 */

import React from 'react';
import { Bot } from 'lucide-react';

export interface AskExaButtonProps {
  /**
   * Context identifier — what the panel should focus on.
   * The panel maps this to a hand-off prompt template.
   */
  context: string;
  className?: string;
  size?: 'sm' | 'md' | 'lg';
  showIcon?: boolean;
  showLabel?: boolean;
  label?: string;
  tooltip?: string;
}

export function AskExaButton({
  context,
  className = '',
  size = 'md',
  showIcon = true,
  showLabel = true,
  label = 'Ask Exa',
  tooltip,
}: AskExaButtonProps) {
  const sizeClasses = {
    sm: 'btn-xs',
    md: 'btn-sm',
    lg: 'btn-md',
  };

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    window.dispatchEvent(
      new CustomEvent('open-agent-panel', {
        detail: { context },
      }),
    );
  };

  const button = (
    <button
      type="button"
      onClick={handleClick}
      title={tooltip}
      className={`btn ${sizeClasses[size]} bg-primary/20 text-primary border-primary/30 hover:bg-primary/30 hover:border-primary/40 ${className}`}
    >
      {showIcon && <Bot size={14} />}
      {showLabel && label}
    </button>
  );

  if (tooltip) {
    return (
      <div className="tooltip tooltip-top" data-tip={tooltip}>
        {button}
      </div>
    );
  }
  return button;
}

export default AskExaButton;
