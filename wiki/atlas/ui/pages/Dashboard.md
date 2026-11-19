---
title: Dashboard
type: atlas-page
path: frontend/src/pages/Dashboard.tsx
confidence: high
updated: 2026-09-17
tags: [type/page, domain/atlas-ui]
---
# Dashboard

**Component**: `frontend/src/pages/Dashboard.tsx`
**Route**: `/` (landing page)
**Last Updated**: 2026-09-17

## Purpose
Landing page providing a system overview: backend health, live resource metrics, recent log activity, and quick navigation to major app sections.

## Key Features
- Header with logo, app version (from `localStorage.app_version`, set by CacheBuster), backend status indicator, **build-mode badge**, **mode switch**, cache refresh, and context help
  - **BuildModeBadge** — `DEV` / `PROD`, naming which build is being served. It reports the **build, not the host**, so a scratch server and a deployed one both read `PROD` and both are right
  - **BuildModeSwitch** — opens the dialog that moves the frontend between the two builds on the **same port**: the auth token, the persisted stores and the cross-tab channel are all origin-scoped, so a second port would sign the user out and sever tab coordination. A switch **to** production builds first and swaps the server only if that build succeeds
- **NavigationCards** — quick links to major sections (Agents, Providers, Workflows, etc.)
- **QuickStats** — 4-stat strip: System Status, CPU Usage, Memory Usage, Recent Logs
- Wrapped in ErrorBoundary

## Components Used
| Component | Path | Purpose |
|-----------|------|---------|
| QuickStats | `components/dashboard/QuickStats.tsx` | 4-stat strip (health, CPU, memory, logs) |
| NavigationCards | `components/dashboard/NavigationCards.tsx` | Quick navigation cards |
| BackendStatusIndicator | `components/ui/BackendStatusIndicator.tsx` | Live backend health pill |
| CacheBuster | `components/CacheBuster.tsx` | Version check + cache refresh |
| BuildModeBadge | `components/BuildModeBadge.tsx` | `DEV` / `PROD` badge — which build is being served |
| BuildModeSwitch | `components/BuildModeSwitch.tsx` | The switch dialog + the mode request it sends |
| HelpButton | `components/help/HelpButton.tsx` | Opens help drawer (context: dashboard) |
| Tooltip | `components/ui/Tooltip.tsx` | Logo tooltip |
| ErrorBoundary | `components/ErrorBoundary.tsx` | Crash containment |

## Hooks Used
| Hook | Path | Purpose |
|------|------|---------|
| usePageTitle | `hooks/usePageTitle.ts` | Sets document title |
| useSystemHealth | `hooks/useSystemHealth.ts` | Health status (via QuickStats) |
| useSystemMetrics | `hooks/useSSE.ts` | Live CPU/memory via SSE (via QuickStats) |
| useLogStats | `hooks/useLogs.ts` | Recent activity count (via QuickStats) |

## Data Flow
- **Health**: `useSystemHealth` → `healthService` → `GET /api/v1/health` + `GET /api/v1/system` (React Query, refetches on interval/focus)
- **Metrics**: `useSystemMetrics` → SSE `GET /api/v1/system/metrics` (via `SSEClientFactory.createSystemMetricsClient`)
- **Log stats**: `useLogStats` → `logsService.getLogStats()` → `GET /api/v1/system/logs`, refetch every 1s
- **Version**: read synchronously from `localStorage.app_version`

## State Management
- `systemStore` — health state updated by `useSystemHealth`
- `notificationStore` — error/success notifications on health transitions
- No local page state (stateless composition)

## API Endpoints Called
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v1/health` | Backend health status |
| GET | `/api/v1/system` | System info |
| GET | `/api/v1/system/metrics` (SSE) | Live CPU/memory streaming |
| GET | `/api/v1/system/logs` | Log stats (recent activity) |
| GET | `/api/v1/system/mode` | Current frontend mode (via BuildModeSwitch) |
| POST | `/api/v1/system/mode` | Request a mode switch (via BuildModeSwitch) |

## Related Pages
- SystemInfo — detailed metrics/health (Dashboard shows summary strip)
- Analytics — usage trends (Dashboard shows recent activity count)
- Logs — detailed log viewing
