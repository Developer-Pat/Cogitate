---
title: ModelSyncScheduler
type: atlas-component
path: frontend/src/components/features/providers/ModelSyncScheduler.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# ModelSyncScheduler

**Path**: `frontend/src/components/features/providers/ModelSyncScheduler.tsx`
**Last Updated**: 2026-08-01

## Purpose

ModelSyncScheduler (Phase 4) is a controlled panel for managing automatic model synchronization schedules for a single provider. It lets users pick a sync interval (1 hour to 7 days), save/disable the schedule, trigger an immediate manual sync ("Sync Now"), and view the current sync status, last/next sync timestamps, and last sync result. The component performs no API calls itself — all operations are delegated through callback props (`onSetSchedule`, `onDisableSchedule`, `onRunSync`, `onRefreshStatus`) wired by the parent page, so it is fully presentational and reusable. It is a default export.

## Props Interface

```typescript
interface ModelSyncSchedulerProps {
  providerId: number;
  providerName: string;
  schedule?: SyncScheduleResponse | null;
  syncStatus?: SyncStatusResponse | null;
  onSetSchedule?: (intervalHours: number) => Promise<void>;
  onDisableSchedule?: () => Promise<void>;
  onRunSync?: () => Promise<SyncStatusResponse | null>;
  onRefreshStatus?: () => Promise<void>;
  loading?: boolean;
}
```

Note: `providerId` and `providerName` are accepted but unused in the render (destructured as `_providerId` / `_providerName`) — they are kept for API symmetry with sibling provider components.

Supporting types from `frontend/src/types/providers.ts`:

```typescript
export interface SyncScheduleResponse {
  provider_id: number;
  sync_interval_hours: number;
  last_sync_at: string | null;
  next_sync_at: string | null;
  sync_enabled: boolean;
  last_sync_status: string;
}

export interface SyncStatusResponse {
  provider_id: number;
  status: string;
  message: string;
  models_synced: number;
  last_sync_at: string | null;
  next_sync_at: string | null;
}
```

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `react` (`useState`) | Library | Local UI state: `selectedInterval`, `isSyncing` |
| `SyncScheduleResponse`, `SyncStatusResponse` (`../../../types/providers`) | Type | Prop typing for `schedule` and `syncStatus` |
| `useSyncSchedule` (`frontend/src/hooks/useSyncSchedule.ts`) | Hook (indirect, via parent) | Supplies `schedule`, `syncStatus`, and the `setSchedule` / `disableSchedule` / `runSync` / `getSyncStatus` callbacks to the page |
| `schedulerService` (`frontend/src/services/domains/providers/schedulerService.ts`) | Service (indirect, via hook) | All backend API calls for sync scheduling |

### API calls (model sync endpoint)

The component itself makes no network calls; its callback props map 1:1 to `schedulerService` methods (base path `GET/POST/DELETE /api/v1/providers/sync-schedule`):

| Callback prop | schedulerService method | HTTP call |
|---|---|---|
| `onSetSchedule(intervalHours)` | `setSyncSchedule(providerId, intervalHours)` | `POST /api/v1/providers/sync-schedule/{providerId}` with body `{ sync_interval_hours }` |
| `onDisableSchedule()` | `disableSync(providerId)` | `DELETE /api/v1/providers/sync-schedule/{providerId}` |
| `onRunSync()` | `runSync(providerId)` | `POST /api/v1/providers/sync-schedule/{providerId}/run` |
| `onRefreshStatus()` | `getSyncStatus(providerId)` | `GET /api/v1/providers/sync-schedule/status/{providerId}` |
| — (loaded on mount by the hook) | `getSyncSchedule(providerId)` | `GET /api/v1/providers/sync-schedule/{providerId}` |

`getSyncSchedule` and `getSyncStatus` fall back to mock data (and `runSync` to a mock error status) when the backend endpoint is unavailable or `providerId` is invalid; `setSyncSchedule` / `disableSync` throw on failure.

## Usage Example

```tsx
// In ProviderDashboard.tsx (pages/ProviderDashboard.tsx)
const { schedule, syncStatus, loading: scheduleLoading, setSchedule, disableSchedule, runSync, getSyncStatus } =
  useSyncSchedule(provider.id);

// ...
{selectedProviderId === provider.id && (
  <div className="mt-4">
    <ModelSyncScheduler
      providerId={provider.id}
      providerName={provider.name}
      schedule={schedule}
      syncStatus={syncStatus}
      onSetSchedule={setSchedule}
      onDisableSchedule={disableSchedule}
      onRunSync={runSync}
      onRefreshStatus={getSyncStatus}
      loading={scheduleLoading}
    />
  </div>
)}
```

## State Used

| State | Type | Initial value | Notes |
|---|---|---|---|
| `selectedInterval` | `number` | `schedule?.sync_interval_hours \|\| 168` | Currently selected interval in hours; updated via the `<select>`; sent to `onSetSchedule` on save |
| `isSyncing` | `boolean` | `false` | Set `true` around `onRunSync()` (with `onRefreshStatus()` after), drives the "Syncing..." button label and disables controls |

Derived/constant helpers (not state): `intervalOptions` (1, 6, 12, 24, 168 hours), `formatDateTime(dateString)` (returns "Never" for null), `getStatusColor(status)` (success/pending/error/disabled → Tailwind color classes).

## Related Components

- `frontend/src/pages/ProviderDashboard.tsx` — parent page; renders ModelSyncScheduler inside each provider card and wires all callback props from `useSyncSchedule`
- `frontend/src/hooks/useSyncSchedule.ts` — hook providing schedule/status state and the operation callbacks
- `frontend/src/services/domains/providers/schedulerService.ts` — API client for the sync-schedule endpoints
- `frontend/src/types/providers.ts` — `SyncScheduleResponse`, `SyncStatusResponse`, `SyncScheduleRequest`, `ISchedulerService` definitions
- Sibling panels shown alongside it on the provider dashboard: `frontend/src/components/features/providers/ProviderHealthModal.tsx`, `frontend/src/components/features/providers/UsageDashboard.tsx`, `frontend/src/components/features/providers/ProviderConfigModal.tsx`
