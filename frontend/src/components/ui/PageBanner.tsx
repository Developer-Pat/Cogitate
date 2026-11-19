import React from 'react';
import { ExaPromptFlyout } from '../features/agentInteraction/ExaPromptFlyout';

interface PageBannerProps {
  title: string;
  subtitle?: string;
  description?: string;
  icon?: string;
  className?: string;
  children?: React.ReactNode;
  tooltip?: string;
  /** Optional action slot rendered on the title row's right side
   *  (e.g. a Help button) — avoids a wasted row below the banner. */
  action?: React.ReactNode;
  /** Hide the app's command widget on this banner (rarely wanted). */
  hideCommand?: boolean;
}

/**
 * Reusable page banner component that matches the sidebar styling
 * Provides consistent branding and page headers across the application
 */
export const PageBanner: React.FC<PageBannerProps> = ({
  title,
  description,
  icon,
  className = '',
  children,
  tooltip,
  action,
  hideCommand = false
}) => {
  return (
    <div className={`mb-8 ${className}`}>
      <div className="bg-base-300 border border-base-300 rounded-lg p-6 shadow-sm">
        <div className="flex items-center gap-4">
          {icon && (
            <div className="text-3xl opacity-80">
              {icon}
            </div>
          )}
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <h1 className="text-3xl font-bold text-base-content">
                {title}
              </h1>
              {tooltip && (
                <div className="tooltip tooltip-bottom" data-tip={tooltip}>
                  <button className="btn btn-ghost btn-xs btn-circle transition-all duration-[var(--button-transition)]">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </button>
                </div>
              )}
            </div>
            {description && (
              <p className="text-lg text-readout leading-relaxed mt-2">
                {description}
              </p>
            )}
          </div>
          {/* THE COMMAND WIDGET RIDES THIS ROW (2026-09-15, the user's
              call: "vertical space is at a premium. it goes on the same line
              as the header if there is one"). No new row, ever — and the
              banner's right side is already the row's spare seat, which is
              why the widget lands here rather than in a bar above the page.

              ARCHITECTURAL NOTE: a generic UI component now imports a feature
              component. That is deliberate — the widget is app-wide chrome by
              design, and the alternative (passing it in from 26 pages) is 26
              places to forget. If a second consumer ever needs this row, move
              the slot to a layout-level convention instead. */}
          {(action || !hideCommand) && (
            <div className="shrink-0 flex items-center gap-2">
              {action}
              {!hideCommand && <ExaPromptFlyout />}
            </div>
          )}
        </div>
        {children && (
          <div className="mt-4">
            {children}
          </div>
        )}
      </div>
    </div>
  );
};

/**
 * Alternative banner with centered layout
 */
export const CenteredPageBanner: React.FC<PageBannerProps> = ({
  title,
  description,
  icon,
  className = '',
  children
}) => {
  return (
    <div className={`mb-8 ${className}`}>
      <div className="bg-base-300 border border-base-300 rounded-lg p-8 shadow-sm text-center">
        {icon && (
          <div className="text-4xl opacity-80 mb-4">
            {icon}
          </div>
        )}
        <h1 className="text-3xl font-bold text-base-content mb-3">
          {title}
        </h1>
        {description && (
          <p className="text-lg text-readout max-w-2xl mx-auto leading-relaxed">
            {description}
          </p>
        )}
        {children && (
          <div className="mt-4">
            {children}
          </div>
        )}
      </div>
    </div>
  );
};

export default PageBanner;