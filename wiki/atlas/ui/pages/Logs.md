---
title: Logs
type: atlas-page
path: frontend/src/pages/Logs.tsx
confidence: high
updated: 2026-09-15
tags: [type/page, domain/atlas-ui]
---
# Logs

**Component**: `frontend/src/pages/Logs.tsx`
**Route**: `/logs` (protected — `requiresAuth: true`, title "Logs", breadcrumb "Logs")
**Last Updated**: 2026-09-15

## Purpose

Monitoring and analysis page for application logging. It presents both backend logs (`app.log`) and frontend browser logs (`frontend.log`) in a unified, auto-refreshing table with server-side search/time filtering, client-side level/source filtering, live log-file size statistics, and maintenance actions for clearing log files or generating full-spread test log entries. The filter controls live behind a collapsed expander bar (closed by default).

## Key Features

- **Live log stats cards** — Backend, Frontend, Archives, and Total file sizes (MB) derived from the file-stats endpoint; status indicators light up when data is present.
- **Auto-refresh** — the log list and the stats both refetch every 1 second while the page is active (refreshing pauses when the tab is in the background).
- **THE FILTERS EXPANDER** — the whole filter card collapses behind a slim bar: a `Filters` badge (outline primary) + an active-filter count (`1 active` etc.) + the collapse arrow. Closed by default — clicking the bar expands the card. The badge count = non-default level/source/search/time state. Hover tooltip on the bar: "Expand or collapse the log filters".
- **The page-header button group** — right-aligned, in order: the **Exa pill** (`ExaPromptFlyout`, the ask-Exa widget), **Refresh**, then **HelpButton**. The Exa pill is passed in by THIS page rather than seated by `PageBanner` (`hideCommand`): the banner shrinks to its content, so inside the header's `justify-between` row a banner-seated pill lands beside the title at the page's left edge, and its 440 px panel — which opens leftward via `absolute right-0` — would run under the nav panel. In the button group the pill sits with its neighbours and the panel opens into the page. Refresh sits here (not behind the filter expander) so it is visible without opening the filters; the list auto-refreshes every 1 second while the page is active.
- **Search + Time on one line** — the debounced (300 ms) full-text search input (server-side `search`) shares its row with the time preset cluster (Time: select + Advanced/Simple toggle + clear-time ✕).
- **Level + source controls on one line** — left: the level buttons (All Levels / Debug / Info / Warning / Error / Critical, client-side); right: the `Source:` select (specific component, server-side `source`) with a gap, then the file-type segmented Both / Frontend / Backend (client-side).
- **The uniform SELECTED state** — every selected filter button renders `btn-active btn-selected`: one action-blue fill with white text (levels + the segmented alike; survives Quiet Mode by design — a selection is state, not noise).
- **Time range filter** — presets (All Time / 1h / 6h / 12h / 24h / 7d) plus an advanced custom From/To datetime picker; sent server-side as `from` / `to`.
- **Client-side pagination** — page sizes 25 / 50 / 100 / 250; resets to page 1 whenever search, source, or time filters change.
- **Clear actions (semantic row)** — Clear Frontend / Clear Backend / Clear Archives = amber (`warning`) outlines; Clear ALL Logs = the one solid red (`error`) — the hierarchy: one extreme tier, the rest regular caution. Each calls the file-clear endpoint with a 5-second abort timeout and invalidates/refetches queries on success; the archives button is disabled when the archive size is 0.
- **Test Logs dropdown (cyan info)** — generates a FULL level spread — DEBUG / INFO / WARNING / ERROR / CRITICAL — into app.log, frontend.log, or both (All). Exists so every badge style is visible at once and the write path is verifiable end-to-end. Success toast names the count + where to look. Opens down (`dropdown-end`).
- **Log details modal** — full entry inspection with copy-to-clipboard for timestamp, message, trace ID, session ID, URL, user agent, and context JSON.
- **Page chrome** — `PageBanner` header (with `hideCommand`, so the Exa pill rides the page's own button group), `ExaPromptFlyout`, `HelpButton` (context `logs`), `ErrorBoundary` wrapper, and document title/meta description via `usePageTitle`.

## Components Used

| Component | Path | Purpose |
|---|---|---|
| ErrorBoundary | `frontend/src/components/ErrorBoundary.tsx` | Catches render errors in the page subtree |
| PageContainer | `frontend/src/components/ui/PageContainer.tsx` | Layout wrapper for page content |
| PageBanner | `frontend/src/components/ui/PageBanner.tsx` | Page header with title, icon, and tooltip; seats the Exa widget unless `hideCommand` |
| ExaPromptFlyout | `frontend/src/components/features/agentInteraction/ExaPromptFlyout.tsx` | The ask-Exa widget — the pill in the page-header button group |
| HelpButton | `frontend/src/components/help/HelpButton.tsx` | Opens help content for the `logs` context |
| LogFilters | `frontend/src/components/logs/LogFilters.tsx` | The filter card body (rendered inside the Logs page's expander): search + time line, level + source line, advanced range, pagination. Body only — no card shell, no refresh button |
| Pagination | `frontend/src/components/logs/Pagination.tsx` | Prev/next/page controls (rendered inside LogFilters) |
| LogsTable | `frontend/src/components/logs/LogsTable.tsx` | Zebra-striped table of log entries with level badges, frontend/backend type icons, locally formatted timestamps, and loading/error/empty states |
| LogDetailsModal | `frontend/src/components/logs/LogDetailsModal.tsx` | Modal showing full log details with copy buttons |

## Hooks Used

| Hook | Path | Purpose |
|---|---|---|
| usePageTitle | `frontend/src/hooks/usePageTitle.tsx` | Sets the document title and meta description |
| useLogs | `frontend/src/hooks/useLogs.ts` | Fetches log entries via `logsService.getLogs`; query key `['logs', filters]`; 1 s refetch interval; no retry on error |
| useLogStats | `frontend/src/hooks/useLogs.ts` | Fetches log-file stats via `logsService.getLogStats`; query key `['log-stats-v2']`; 1 s refetch interval |
| useLogsFilters | `frontend/src/hooks/useLogsFilters.ts` | Client-side level and source-type filtering; persists filters to sessionStorage under `cogitate_logs_filters` |
| useDebounce | `frontend/src/hooks/useDebounce.ts` | Debounces the search term (300 ms) before it is sent to the API |
| useQueryClient / useMutation | `@tanstack/react-query` | Mutation handling and query invalidation for the clear and test actions |

## Data Flow

1. **Fetch logs** — `useLogs` calls `logsService.getLogs` → `GET /api/v1/logs/file/recent` requesting up to 1000 entries (`n=1000`), passing `search`, `from`, `to`, and `source` when set (level and source-type filtering are intentionally left client-side). The service lowercases log levels and returns a `PaginatedResponse { data, pagination, has_more }`; on API failure it falls back to the in-memory `globalLogStore`.
2. **Fetch stats** — `useLogStats` calls `logsService.getLogStats` → `GET /api/v1/logs/file/stats`, mapping `files['frontend.log'].size_mb` and `files['app.log'].size_mb` into `frontendLogs` / `backendLogs` and `total_size_mb` into `total` (all sizes in MB). The page derives active size (backend + frontend) and archive size (total − active).
3. **Client-side transformation** — unique `source` values from the fetched logs populate the source dropdown; `useLogsFilters` applies the level and source-type filters; the filtered array is sliced by client-side pagination.
4. **Actions** — clear mutations `DELETE /api/v1/logs/file/clear?...` (frontend / backend / both / archives) and test mutations `POST /api/v1/logs/test...` run through `apiClient`; on success they invalidate the `['logs']` and `['log-stats']` query keys, force `refetchLogs()`, and emit audit entries through `frontendLoggingService`.
5. **Selection** — clicking View opens `LogDetailsModal` with the selected `LogEntry`.

## State Management

- **React Query cache** — the page reads the `['logs', filters]` and `['log-stats-v2']` queries and, after mutations, invalidates the `['logs']` and `['log-stats']` keys via `useQueryClient` (note: the stats hook key is `log-stats-v2`, while invalidations target `log-stats`).
- **Local component state** — selectedLog, filtersOpen (the expander's open state), searchTerm (plus its debounced copy), fromTime / toTime, timePreset, showAdvancedTime, selectedSource, pageSize, currentPage.
- **sessionStorage** — `useLogsFilters` persists level / search / source-type filters under `cogitate_logs_filters` so they survive reloads within the session.
- **In-memory store** — `frontendLoggingService` writes browser-side logs to `globalLogStore` (`frontend/src/services/logStoreInstance.ts`) and posts them to the backend; `logsService` uses the same store as a fallback cache when the API is unavailable.

## API Endpoints Called

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/logs/file/recent?n=…&search=…&from=…&to=…&source=…` | Fetch recent log entries (up to 1000) for display and client-side filtering |
| GET | `/api/v1/logs/file/stats` | Fetch log-file sizes (frontend.log, app.log, archives, total MB) |
| DELETE | `/api/v1/logs/file/clear?frontend=true` | Clear the frontend log file |
| DELETE | `/api/v1/logs/file/clear?backend=true` | Clear the backend log file |
| DELETE | `/api/v1/logs/file/clear?frontend=true&backend=true` | Clear all active log files |
| DELETE | `/api/v1/logs/file/clear?archives=true` | Clear archived/compressed log files |
| POST | `/api/v1/logs/test` | Generate test log entries across all sources |
| POST | `/api/v1/logs/test/frontend` | Generate frontend test log entries |
| POST | `/api/v1/logs/test/backend` | Generate backend test log entries |

Supporting endpoints used by the logging subsystem (not called directly by this page): `GET /api/v1/logs/sources`, `GET /api/v1/logs/{id}`, `POST /api/v1/logs/frontend` (frontend log ingestion), `POST /api/v1/logs/frontend/batch`, and the DB-backed domain service at `/api/v1/system/logs` (list / stats / sources / clear, exported as `domainLogsService` from the services index).

## Related Pages

- [[Dashboard]] — system overview that surfaces log-derived health signals
- [[RagIndex]] — system health and status monitoring
- [[SystemHistory]] — log pattern and message-frequency analysis built on the same logging data
