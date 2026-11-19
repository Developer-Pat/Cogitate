---
title: LiveMonitoring
type: atlas-component
path: frontend/src/components/features/debugging/LiveMonitoring.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---

# LiveMonitoring

**Path**: `frontend/src/components/features/debugging/LiveMonitoring.tsx`
**Last Updated**: 2026-08-01

## Purpose

Real-time activity monitoring panel for the Debugging page's "Live Monitoring" tab. Shows a live status header (Live/Stopped badge, event count, active session count), a metrics overview (requests/sec, errors/sec, active connections, avg response time), a mock list of agent sessions that can be selected and terminated, and a live event feed.

Data flow: on mount it starts the singleton `liveMonitoringService` (WebSocket connection to the backend monitoring stream plus 5-second metrics polling) and subscribes to its event/metrics push channels; on unmount it unsubscribes and stops the service. The session list itself is **hard-coded mock data** initialized once on mount — it is not fetched. Activity events and metrics come from the **real backend when available** (WebSocket at `ws://<VITE_API_URL host>/api/v1/monitoring/stream`, REST fallbacks `/api/v1/monitoring/events` and `/api/v1/monitoring/metrics`), with mock fallback values injected by the service only if the backend is unreachable. See the service doc note: `LiveMonitoringService.ts` uses `import.meta.env.VITE_API_URL || 'http://localhost:8000'` as its base URL.

## Props Interface

The component takes **no props** — it is a plain `React.FC` with an empty props type. The `Session` interface below is internal to the file (used for the mock session list and local selection state); it is not exported and not part of any public props contract.

```typescript
// Internal (not exported) — used for the mock session list and selection state
interface Session {
  id: string
  name: string
  status: 'active' | 'idle' | 'error' | 'completed'
  createdAt: string
  lastActivity: string
  agentCount: number
  workflowCount: number
  progress: number
}

// Consumed from LiveMonitoringService (types imported, not redefined here)
// ActivityEvent, MonitoringMetrics — see src/services/domain/LiveMonitoringService.ts

export const LiveMonitoring: React.FC = () => {
  // ...
}
```

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `ErrorBoundary` (`../../ErrorBoundary`) | Component | Wraps the entire panel; catches and contains render errors |
| `useState`, `useEffect` (`react`) | Hook | Local state management; mount/unmount lifecycle for service start/stop and subscriptions |
| `frontendLoggingService` (`../../../services/frontendLoggingService`) | Service (singleton) | Structured browser logging for component mount/unmount, events received, metrics updated, session select/terminate |
| `liveMonitoringService` (`../../../services/domain/LiveMonitoringService`) | Service (singleton) | WebSocket connection + REST polling for real-time activity events and monitoring metrics; subscriber pattern |
| `ActivityEvent`, `MonitoringMetrics` (`../../../services/domain/LiveMonitoringService`) | Type | Typing for the events feed and metrics overview |

## Usage Example

Used without props by the Debugging page (named export):

```tsx
// frontend/src/pages/Debugging.tsx (Live Monitoring tab)
import { LiveMonitoring } from '../components/features/debugging/LiveMonitoring'

// inside the page's tab content
<LiveMonitoring />
```

## State Used

| State | Type | Initial | Notes |
|---|---|---|---|
| `sessions` | `Session[]` | `[]` | Populated once on mount with 3 hard-coded mock sessions (Research Workflow / Document Analysis / Code Review); updated locally by `handleSessionTerminate` (sets status to `'completed'`) |
| `selectedSession` | `Session \| null` | `null` | Session chosen in the Active Sessions list; drives the Session Details card |
| `events` | `ActivityEvent[]` | `[]` | Live event feed; prepends each subscribed event and keeps the last 100 (`[event, ...prev].slice(0, 100)`) |
| `metrics` | `MonitoringMetrics \| null` | `null` | Latest metrics pushed by `subscribeToMetrics`; renders the 4-stat overview when non-null |
| `isMonitoring` | `boolean` | `false` | Tracks whether the monitoring service is running; drives the Live/Stopped badge |

## Related Components

- `frontend/src/pages/Debugging.tsx` — host page; renders `<LiveMonitoring />` inside its Live Monitoring tab
- `frontend/src/services/domain/LiveMonitoringService.ts` — source of live events/metrics (WebSocket + polling, mock fallback)
- `frontend/src/components/ErrorBoundary.tsx` — error containment wrapper
- `frontend/src/services/frontendLoggingService.ts` — logging used throughout the component
- `frontend/src/services/domain/__tests__/LiveMonitoringService.test.ts` — unit tests for the underlying service
