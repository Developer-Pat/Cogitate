---
title: ErrorAnalysis
type: atlas-component
path: frontend/src/components/features/debugging/ErrorAnalysis.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# ErrorAnalysis

**Path**: `frontend/src/components/features/debugging/ErrorAnalysis.tsx`
**Last Updated**: 2026-08-01

## Purpose

Error analysis panel for the Debugging page's Errors tab. It lists backend-tracked error/warning/info entries with summary count cards (Total, Critical, Active, Resolved), type/severity/status filter dropdowns, per-entry Resolve/Ignore actions, and a detail modal showing the full record including stack trace and context JSON.

The data source is **real backend data** — not simulated. Errors load through `errorTrackingService.loadFromBackend()` (`GET /api/v1/debug/errors`), and the component subscribes to the service so the list updates reactively (initial load, the service's 30-second background sync, and after resolve/ignore actions). If the backend endpoint is unavailable, the component fails loudly: the load promise re-throws and `frontendLoggingService` logs "BACKEND API NOT AVAILABLE - ErrorTrackingService failed" plus "EXPECTED: Backend endpoint /api/v1/debug/errors must be implemented".

`ErrorAnalysis` is a **named export** (`export const ErrorAnalysis: React.FC<ErrorAnalysisProps>`), not a default export.

## Props Interface

```typescript
interface ErrorAnalysisProps {
  onErrorResolve?: (errorId: string) => void
  onErrorIgnore?: (errorId: string) => void
}
```

Both props are optional callbacks fired only after the corresponding service call succeeds:

- `onErrorResolve(errorId)` — called after `errorTrackingService.resolveError(errorId)` (Resolve button in the list, or "Mark as Resolved" in the modal).
- `onErrorIgnore(errorId)` — called after `errorTrackingService.ignoreError(errorId)` (Ignore button).

The Debugging page passes both; its handlers log the action via `frontendLoggingService` and remove the id from a local `_activeErrors` state array.

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `react` (`useState`, `useEffect`) | Library | Local UI state; mount effect loads errors and subscribes to the service, cleanup unsubscribes |
| `ErrorBoundary` (`../../ErrorBoundary`) | Component | Wraps the whole panel (loading state and main card) to catch render errors |
| `errorTrackingService` (`../../../services/domain/ErrorTrackingService`) | Service singleton | Data source and actions: `loadFromBackend()` (`GET /api/v1/debug/errors`), `resolveError()` (`POST /api/v1/debug/errors/{id}/resolve`), `ignoreError()` (`DELETE /api/v1/debug/errors/{id}`), `subscribe()` for reactive updates |
| `ErrorEntry` (imported as `ServiceErrorEntry`) | Type | Error record shape from the service: `id`, `type`, `message`, `stackTrace?`, `timestamp`, `source`, `severity`, `context?`, `status`, `resolvedAt?`, `resolvedBy?` |
| `frontendLoggingService` (`../../../services/frontendLoggingService`) | Service | Logs mount/unmount, load failure, resolve/ignore attempts |

## Usage Example

From `frontend/src/pages/Debugging.tsx` (Errors tab):

```tsx
import { ErrorAnalysis } from '../components/features/debugging/ErrorAnalysis'

// ...
{activeTab === 'errors' && (
  <div className="space-y-6">
    <ErrorAnalysis
      onErrorResolve={handleErrorResolve}
      onErrorIgnore={handleErrorIgnore}
    />
  </div>
)}
```

## State Used

All state is local `useState` — the component reads no external store:

| State | Type | Initial | Purpose |
|---|---|---|---|
| `errors` | `ServiceErrorEntry[]` | `[]` | Error list fed by the service subscription |
| `isLoading` | `boolean` | `true` | True until `loadFromBackend()` settles; renders a spinner card |
| `selectedError` | `ServiceErrorEntry \| null` | `null` | Error shown in the detail modal |
| `filterType` | `'all' \| 'error' \| 'warning' \| 'info'` | `'all'` | Type filter select |
| `filterSeverity` | `'all' \| 'low' \| 'medium' \| 'high' \| 'critical'` | `'all'` | Severity filter select |
| `filterStatus` | `'all' \| 'active' \| 'resolved' \| 'ignored'` | `'active'` | Status filter select (defaults to Active only) |

Derived values computed inline each render: `filteredErrors` (client-side AND of the three filters), `activeCount`, `criticalCount` (severity `critical` and not ignored), `resolvedCount` — these back the summary stat cards and the list. Local helpers: `getTypeColor`, `getSeverityColor`, `getStatusColor` (badge/background classes per value) and `getTimeAgo` (renders `Nd ago` / `Nh ago` / `Nm ago` / `Just now`).

## Data Source & API Endpoints

Real backend data via `errorTrackingService` (base path `/api/v1/debug/errors`, called through `apiClient`). The component itself makes no direct `fetch`/SSE calls — all transport lives in the service:

| Method | Endpoint | When |
|---|---|---|
| GET | `/api/v1/debug/errors` | On mount (`loadFromBackend()`); the service also re-syncs every 30 s in the background. Failures are re-thrown and logged loudly (see Purpose) |
| POST | `/api/v1/debug/errors/{id}/resolve` | Resolve button (list) / "Mark as Resolved" (modal) → `handleResolve` → `resolveError(errorId)` |
| DELETE | `/api/v1/debug/errors/{id}` | Ignore button → `handleIgnore` → `ignoreError(errorId)` |

On mount the component subscribes to `errorTrackingService.subscribe()` (and unsubscribes on unmount) so the list always mirrors the service cache. The list UI shows each entry's type/severity/status badges, message, source, relative timestamp, and a collapsible "Context Details" JSON block; active entries get Resolve/Ignore buttons. Empty states: "No errors found. System is healthy!" (no errors at all) or "No errors found matching the current filters."

## Related Components

- Parent: `frontend/src/pages/Debugging.tsx` — renders it in the `errors` tab with `onErrorResolve` / `onErrorIgnore`
- Siblings (other tabs of the same page): `frontend/src/components/features/debugging/LogViewer.tsx`, `DebugControls.tsx`, `LiveMonitoring.tsx`, `TraceAnalysis.tsx`
- Wrapper: `frontend/src/components/ErrorBoundary.tsx`
- Data service: `frontend/src/services/domain/ErrorTrackingService.ts`
