import React from 'react';
import { useSystemHealth } from '@/hooks/useSystemHealth';
import { useNotificationStore } from '@/stores/notificationStore';
import { outageGate } from '@/services/outageGate';

interface BackendStatusIndicatorProps {
  showLabel?: boolean;
  className?: string;
  compact?: boolean;
  tooltipPosition?: 'top' | 'bottom' | 'left' | 'right';
}

/**
 * BackendStatusIndicator component displays the current backend connection status
 * with visual indicators (🟢🟡🔴) and optional retry functionality.
 */
export function BackendStatusIndicator({
  showLabel = true,
  className = '',
  compact = false,
  tooltipPosition = 'top'
}: BackendStatusIndicatorProps) {
  const { 
    isHealthy, 
    isDegraded, 
    isUnhealthy, 
    isLoading, 
    error, 
    refetch 
  } = useSystemHealth();
  
  const addNotification = useNotificationStore((state) => state.addError);

  // THE TRANSITION BOOKKEEPING (2026-09-03, the runaway-loop fix):
  // the old effect kept consecutiveFailures / lastNotificationTime /
  // wasUnhealthy as STATE and listed them in its own deps — every
  // unhealthy tick SET the state, re-ran the effect, incremented
  // again -> an infinite update loop + a notification per cycle
  // (crashed Firefox when the indicator was mounted on Agent Chat).
  // Refs break the loop: the effect runs ONLY on a status CHANGE
  // (status is the sole dep); the counters live outside the render.
  const lastNotificationTimeRef = React.useRef<number>(0);
  const consecutiveFailuresRef = React.useRef<number>(0);
  const wasUnhealthyRef = React.useRef<boolean>(false);
  const lastStatusRef = React.useRef<string>('unknown');
  // THE CONFIRMATION TIMER (2026-09-07, the user's false alarm on
  // the Sounds page): the first unhealthy transition only ARMS this
  // — the toast fires when the timer elapses IF the outage is still
  // current (the next 30s poll should have confirmed). A single
  // dropped poll never claims 'Backend Unavailable'.
  const confirmTimerRef = React.useRef<number | null>(null);

  // Determine status based on health data
  const getStatus = () => {
    if (isLoading) return 'loading';
    if (error || isUnhealthy) return 'unhealthy';
    if (isDegraded) return 'degraded';
    if (isHealthy) return 'healthy';
    return 'unknown';
  };

  const status = getStatus();

  // Handle status TRANSITIONS and show notifications
  React.useEffect(() => {
    const prevStatus = lastStatusRef.current;
    if (prevStatus === status) return; // no change — nothing to do
    lastStatusRef.current = status;

    const now = Date.now();
    const timeSinceLastNotification = now - lastNotificationTimeRef.current;

    if (status === 'unhealthy') {
      consecutiveFailuresRef.current += 1;
      const failures = consecutiveFailuresRef.current;

      // THE CONFIRMATION GATE (2026-09-07, the user's false alarm on
      // the Sounds page): the FIRST unhealthy transition arms a 40s
      // timer (the health poll runs every 30s) and does NOT toast —
      // if the next poll still reports unhealthy when the timer
      // elapses, THAT is the confirmed outage and it toasts (the
      // recovery before the timer clears it — no false 'Backend
      // Unavailable' from a single dropped poll). The recurring
      // nudge (every 3rd confirmed episode) keeps the rate limit.
      if (failures === 1) {
        confirmTimerRef.current = window.setTimeout(() => {
          confirmTimerRef.current = null;
          // still unhealthy? the outage is real — announce it
          if (lastStatusRef.current === 'unhealthy' && timeSinceLastNotification > 10000 && outageGate.markDown()) {
            addNotification(
              'Backend Unavailable',
              'Cannot connect to backend server. Some features may not work.',
              10000 // Show for 10 seconds
            );
            lastNotificationTimeRef.current = Date.now();
          }
        }, 40000);
      } else if (failures % 3 === 0 && timeSinceLastNotification > 10000 && outageGate.markDown()) {
        // the episode persists — the periodic reminder (rate limited)
        addNotification(
          'Backend Unavailable',
          'Cannot connect to backend server. Some features may not work.',
          10000 // Show for 10 seconds
        );
        lastNotificationTimeRef.current = now;
      }

      wasUnhealthyRef.current = true;
    } else if (status === 'healthy' && wasUnhealthyRef.current) {
      // Show recovery notification when backend comes back online —
      // the first recovery-detector of the episode announces (the
      // gate) + closes it.
      if (timeSinceLastNotification > 10000 && outageGate.markUp()) {
        useNotificationStore.getState().addSuccess(
          'Backend Connection Restored',
          'Connection to backend server has been restored.',
          5000
        );
        lastNotificationTimeRef.current = now;
      }
      consecutiveFailuresRef.current = 0;
      wasUnhealthyRef.current = false;
    } else if (status === 'healthy') {
      consecutiveFailuresRef.current = 0;
      wasUnhealthyRef.current = false;
    }

    // the recovery (any healthy transition) clears the confirmation
    // timer — a blip that heals before the gate never toasts
    if (confirmTimerRef.current !== null && status === 'healthy') {
      window.clearTimeout(confirmTimerRef.current);
      confirmTimerRef.current = null;
    }
  }, [status, addNotification]);

  // Get status display properties
  const getStatusConfig = () => {
    switch (status) {
      case 'healthy':
        return {
          icon: '🟢',
          label: 'Backend Online',
          color: 'text-success',
          bgColor: 'bg-success/10',
          tooltip: 'Backend server is online and responding normally'
        };
      case 'degraded':
        return {
          icon: '🟡',
          label: 'Backend Degraded',
          color: 'text-warning',
          bgColor: 'bg-warning/10',
          tooltip: 'Backend server is experiencing issues but still responding'
        };
      case 'unhealthy':
        return {
          icon: '🔴',
          label: 'Backend Offline',
          color: 'text-error',
          bgColor: 'bg-error/10',
          tooltip: 'Cannot connect to backend server. Some features may not work.'
        };
      case 'loading':
        return {
          icon: '⏳',
          label: 'Checking...',
          color: 'text-readout',
          bgColor: 'bg-base-content/10',
          tooltip: 'Checking backend connection status...'
        };
      default:
        return {
          icon: '❓',
          label: 'Unknown',
          color: 'text-readout',
          bgColor: 'bg-base-content/10',
          tooltip: 'Backend connection status unknown'
        };
    }
  };

  const config = getStatusConfig();

  // THE DAISYUI TOOLTIP (2026-09-04, the user's ask — the custom
  // Tooltip popover was NOT DaisyUI): the state dot rides the
  // standard tooltip classes + data-tip. The state readout stays
  // in the aria-label (the house rule — the dot is a state
  // indicator, not an action).
  const tooltipPositionClass =
    tooltipPosition === 'bottom' ? 'tooltip-bottom' : tooltipPosition === 'left' ? 'tooltip-left' : tooltipPosition === 'right' ? 'tooltip-right' : 'tooltip-top';

  const handleRetry = () => {
    if (status === 'unhealthy' || status === 'degraded') {
      refetch();
      useNotificationStore.getState().addInfo(
        'Retrying Connection',
        'Attempting to reconnect to backend server...',
        3000
      );
    }
  };

  if (compact) {
    return (
      <div
        className={`tooltip ${tooltipPositionClass}`}
        data-tip={config.label}
      >
        <div
          className={`inline-flex items-center justify-center w-6 h-6 rounded-full ${config.bgColor} ${className} cursor-help`}
          role="status"
          aria-live="polite"
          aria-label={`Backend status: ${config.label}`}
        >
          <span className={`text-sm ${config.color}`} aria-hidden="true">
            {config.icon}
          </span>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`tooltip ${tooltipPositionClass}`}
      data-tip={config.tooltip}
    >
      <div
        className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-md ${config.bgColor} ${className} cursor-help`}
        role="status"
        aria-live="polite"
        aria-label={`Backend status: ${config.label}`}
      >
        <span className={`text-lg ${config.color}`} aria-hidden="true">
          {config.icon}
        </span>
        
        {showLabel && (
          <span className={`text-sm font-medium ${config.color}`}>
            {config.label}
          </span>
        )}
        
        {(status === 'unhealthy' || status === 'degraded') && (
          <button
            onClick={handleRetry}
            className="ml-2 px-2 py-0.5 text-xs font-medium text-primary-content bg-primary hover:bg-primary/90 rounded transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-1"
            aria-label="Retry connection"
          >
            Retry
          </button>
        )}
        
        {isLoading && (
          <span className="ml-2 text-xs text-readout">
            Checking...
          </span>
        )}
      </div>
    </div>
  );
}