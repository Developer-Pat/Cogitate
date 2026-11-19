---
title: QuickStats
type: atlas-component
path: frontend/src/components/dashboard/QuickStats.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# QuickStats

**Path**: `frontend/src/components/dashboard/QuickStats.tsx`
**Last Updated**: 2026-08-01

## Purpose
Dashboard summary stat cards — System Status (health), CPU Usage, Memory Usage, Recent Logs count. 4-column responsive grid with color-coded values (success/warning/error thresholds at 60%/80%).

## Props Interface
None — no props; fetches its own data.

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| useSystemHealth | Hook | Health status via `/api/v1/health` |
| useSystemMetrics | Hook | CPU/memory via SSE system-metrics |
| useLogStats | Hook | Recent log activity count |

## Usage Example
```tsx
<QuickStats />  // in Dashboard page
```

## State Used
- isHealthy, isLoading (health); data/isLoading (metrics); data/isLoading (log stats)

## Related Components
- dashboard/NavigationCards.tsx — sibling nav cards
- dashboard/SystemHealthCard.tsx — detailed health card