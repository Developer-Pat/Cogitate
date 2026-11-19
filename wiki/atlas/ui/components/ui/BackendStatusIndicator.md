---
title: BackendStatusIndicator
type: atlas-component
path: frontend/src/components/ui/BackendStatusIndicator.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# BackendStatusIndicator

**Path**: `frontend/src/components/ui/BackendStatusIndicator.tsx`
**Last Updated**: 2026-08-01

## Purpose

Displays the current backend connection status as a color-coded indicator (🟢🟡🔴) with an optional label, tooltip, and retry button. Status is derived from the `useSystemHealth` hook, which polls the backend health endpoint via React Query (refetch every 30s). The component also emits user notifications on status transitions: an error notification on failure (rate-limited to 1 per 10 seconds, on first failure or every 3rd consecutive failure), and a success notification when the backend recovers. It is used in the Dashboard header.

## Props Interface

```typescript
interface BackendStatusIndicatorProps {
  showLabel?: boolean;
  className?: string;
  compact?: boolean;
  tooltipPosition?: 'top' | 'bottom' | 'left' | 'right';
}
```

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `useSystemHealth` (`../../hooks/useSystemHealth`) | Custom hook | Provides `isHealthy`, `isDegraded`, `isUnhealthy`, `isLoading`, `error`, and `refetch` from the `system-health` React Query; polls `/api/v1/health` every 30s |
| `useNotificationStore` (`../../stores/notificationStore`) | Zustand store | `addError` / `addSuccess` / `addInfo` actions for surfacing connection and recovery notifications |
| `Tooltip` (`./Tooltip`) | UI component | Wraps the indicator to show a status-specific tooltip on hover |

## Usage Example

```tsx
// Dashboard header (compact variant, no label)
import { BackendStatusIndicator } from '../components/ui/BackendStatusIndicator'

<BackendStatusIndicator compact={true} className="ml-2" tooltipPosition="bottom" />

// Default variant with label and retry button (shown when unhealthy/degraded)
<BackendStatusIndicator showLabel tooltipPosition="top" />
```

## State Used

- `lastNotificationTime` (`useState<number>`): timestamp of the last notification, used to rate-limit to max 1 notification per 10 seconds.
- `consecutiveFailures` (`useState<number>`): running count of unhealthy polls; a notification fires on the first failure and then every 3rd consecutive failure.
- `wasUnhealthy` (`useState<boolean>`): tracks whether the backend was previously unhealthy so a recovery notification can be shown on the healthy transition.
- Status is computed locally from `useSystemHealth` data: `loading` → `unhealthy` (error or `isUnhealthy`) → `degraded` → `healthy` → `unknown`.

## Related Components

- `frontend/src/pages/Dashboard.tsx` — renders `<BackendStatusIndicator compact tooltipPosition="bottom" />` in the page header.
- `frontend/src/components/ui/Tooltip.tsx` — wrapper component for the hover tooltip.
- `frontend/src/components/ui/CacheBuster.tsx` / `HelpButton.tsx` — sibling header controls on the Dashboard.
- `frontend/src/hooks/useSystemHealth.ts` — data source hook (also exports `useServiceStatus`, `useSystemMetrics`, `useUptime`, `useHealthCheck`).
- `frontend/src/stores/notificationStore.ts` — notification actions consumed by the component.
