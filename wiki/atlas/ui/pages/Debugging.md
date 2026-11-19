---
title: Debugging
type: atlas-page
path: frontend/src/pages/Debugging.tsx
confidence: high
updated: 2026-07-31
tags: [type/page, domain/atlas-ui]
---
# Debugging

**Component**: `frontend/src/pages/Debugging.tsx`
**Route**: `/debugging` (protected, requiresAuth: true, icon `bug`, breadcrumb `Debugging`)
**Last Updated**: 2026-07-31

## Purpose

The Debugging page is the consolidated debugging and troubleshooting hub for the Cogitate frontend. It exposes system inspection tools: analyzing system state, debugging requests, and diagnosing issues. The page was built during the Phase 4 consolidation (2026-03-07): it introduced tab-based navigation and absorbed the functionality of the deleted RealTimeMonitor page into the Live Monitoring tab. A Trace Analysis tab was added 2026-03-09 for real-time flow-trace capture, filtering, and export. The page is wrapped in an `ErrorBoundary` so a failing child tool never takes down the whole route.

## Key Features

- **8-tab navigation** — tabs are conditionally rendered from local state (`agent-traces` is the default tab): Agent Traces, Cognitive Traces, Trace Analysis, Error Analysis, Debug Actions, Live Monitoring, Settings (Log Viewer), and Database.
- **Agent Traces** — `BackendTraceViewer` configured with `defaultSource="agent"`, title *Agent Request Traces*; lists recent backend trace summaries with session filtering and per-trace observation drill-down.
- **Cognitive Traces** — `CognitiveTraceViewer` with a real-time SSE trace stream (auto-starts on mount, last 100 events kept in memory), a historical trace browser, per-component filtering (context_builder, executor, memory_manager, response_formatter), expand/collapse detail cards, and trace summary metrics.
- **Trace Analysis** — `TraceControls` (runtime tracing toggle, flow-traces toggle, sampling rate) plus `TraceAnalysis` (auto-refreshing flow-trace log table with filters for flow, sequence range, step text, include/exclude patterns, tags, and time range; JSON/CSV export; per-row expandable context).
- **Error Analysis** — `ErrorAnalysis` summary stats (total, critical, active, resolved), filters by type/severity/status, per-error resolve/ignore actions, and a detail modal with stack trace and context.
- **Debug Actions** — `DebugControls` grouped action cards by category with execute buttons, dangerous/confirmation badges, a breakpoints toggle, status summary, and a confirmation modal for dangerous actions.
- **Live Monitoring** — `LiveMonitoring` real-time session list (mock data), live event feed, and metrics (requests/sec, errors/sec, connections, avg response) fed by the monitoring WebSocket; session detail panel with terminate action.
- **Settings (Log Viewer)** — `LogViewer` recent-logs table with level/source/time/search filters, JSON/CSV export, clear-logs, SSE live streaming toggle, and an embedded `LoggingConfigPanel` for logging configuration.
- **Database** — `DatabaseTools` destructive "Clear All Sessions" tool with confirmation, result reporting, and a CLI alternative (`python backend/scripts/clear_sessions.py`).

## Components Used

| Component | Path | Purpose |
|---|---|---|
| `ErrorBoundary` | `frontend/src/components/ErrorBoundary.tsx` | Wraps the entire page so a failing tab cannot crash the route |
| `PageBanner` | `frontend/src/components/ui/PageBanner.tsx` | Page header banner (title, bug icon, tooltip) |
| `BackendTraceViewer` | `frontend/src/components/features/debugging/BackendTraceViewer.tsx` | Agent Traces tab: trace summary list + observation detail from the backend traces API |
| `CognitiveTraceViewer` | `frontend/src/components/features/debugging/CognitiveTraceViewer.tsx` | Cognitive Traces tab: live SSE stream + history browser for cognitive pipeline traces |
| `TraceControls` | `frontend/src/components/features/debugging/TraceControls.tsx` | Trace Analysis tab: toggles tracing/flow-traces and sampling rate via `loggingConfigService` |
| `TraceAnalysis` | `frontend/src/components/features/debugging/TraceAnalysis.tsx` | Trace Analysis tab: flow-trace table, filters, stats, JSON/CSV export |
| `ErrorAnalysis` | `frontend/src/components/features/debugging/ErrorAnalysis.tsx` | Error Analysis tab: error list, filters, resolve/ignore, detail modal |
| `DebugControls` | `frontend/src/components/features/debugging/DebugControls.tsx` | Debug Actions tab: action cards, execute, breakpoint toggle, confirmation modal |
| `LiveMonitoring` | `frontend/src/components/features/debugging/LiveMonitoring.tsx` | Live Monitoring tab: sessions, event feed, metrics (from deleted RealTimeMonitor page) |
| `LogViewer` | `frontend/src/components/features/debugging/LogViewer.tsx` | Settings tab: log table, filters, export, clear, SSE streaming |
| `DatabaseTools` | `frontend/src/components/features/debugging/DatabaseTools.tsx` | Database tab: clear-sessions tool with confirmation |
| `LoggingConfigPanel` (transitive) | `frontend/src/components/settings/LoggingConfigPanel.tsx` | Rendered inside LogViewer's Settings panel; edits logging config via `loggingConfigService` |

## Hooks Used

| Hook | Path | Purpose |
|---|---|---|
| `usePageTitle` | `frontend/src/hooks/usePageTitle.tsx` | Sets the document title ("Debugging") and meta description via react-helmet-async |
| `useState` (React) | react | Page-level `activeTab` state; also unused `_diagnosticResults`/`_activeErrors` placeholders |
| `useEffect` / `useCallback` / `useRef` (React) | react | Used inside child components (SSE lifecycle, polling, visibility observers, auto-scroll) |

## Data Flow

- **Page level**: The page renders one tab's component tree at a time based on `activeTab`. All tab handler callbacks (`handleErrorResolve`, `handleErrorIgnore`, `handleLogFilter`, `handleLogExport`, `handleActionExecute`, `handleBreakpointToggle`, `handleTraceExport`, `handleTraceConfigChange`) are thin logging shims that emit through `frontendLoggingService`; actual data work happens inside the child components.
- **Error Analysis**: `ErrorAnalysis` calls `errorTrackingService.loadFromBackend()` on mount (GET `/api/v1/debug/errors`) and subscribes to the service's subscriber pattern for reactive updates. Resolve posts to `/api/v1/debug/errors/{id}/resolve`; Ignore deletes `/api/v1/debug/errors/{id}`. The service also background-syncs every 30s.
- **Debug Actions**: `DebugControls` calls `debugActionsService.loadActions()` (GET `/api/v1/debug/actions`; falls back to disabled mock actions if the backend is unavailable). Executing an action calls the action's own endpoint (POST/DELETE/GET via apiClient) and stores results locally; running actions are status-polled every 2s via GET `/api/v1/debug/actions/{id}/status`.
- **Live Monitoring**: `LiveMonitoring` starts `liveMonitoringService` on mount: a WebSocket connection to `/api/v1/monitoring/stream` delivers `ActivityEvent`s (kept to the last 100), and metrics arrive via polling (`/api/v1/monitoring/stats`). Session cards are static mock data rendered client-side; terminating a session only flips local state.
- **Settings / Log Viewer**: `LogViewer` loads logs through `logManagementService.loadRecentLogs(100)` (GET `/api/v1/logs/file/recent?n=100`, items extracted from the `{ items, total, file }` response), subscribes to cache updates, and can open an SSE stream at `/api/v1/logs/stream`. Export downloads a blob from GET `/api/v1/logs/export?format=json|csv`; Clear Logs deletes `/api/v1/logs/file/clear?frontend=true&backend=false`. Logging config is applied locally via `loggingConfigService` (no API call).
- **Trace Analysis**: `TraceAnalysis` polls `${VITE_API_URL}/api/v1/logs/recent?n=500&source=FlowTrace` (default 2s interval, paused when the container is off-screen via IntersectionObserver), then transforms raw log records into trace entries by parsing flow/step out of the message and sorting by sequence. Export builds GET `/api/v1/logs/traces/export?format=&limit=` and downloads the blob. `TraceControls` reads/writes tracing config through the client-side `loggingConfigService`.
- **Cognitive Traces**: `CognitiveTraceViewer` opens an `EventSource` on `/api/v1/agent-chat/trace-stream` (auto-start on mount; listens for the `cognitive_trace_complete` event, keeps last 100). The History tab fetches GET `/api/v1/agent-chat/session/traces?limit=50`. Both live and historical payloads share the same shape (per-component trace data, metrics, memory delta, error) and are rendered by shared sub-components.
- **Agent Traces**: `BackendTraceViewer` fetches GET `/api/v1/traces/traces?limit=50` (plus optional `session_id` and `source=agent` filters) and, on row click, GET `/api/v1/traces/traces/{traceId}` for the observation list.
- **Database**: `DatabaseTools` sends DELETE `http://localhost:8000/api/v1/sessions/all` (hardcoded dev URL) after confirmation and renders the `{ deleted, failed, total_* }` response.

## State Management

- **No Zustand stores** are read or written by the page itself; tab selection is plain local `useState`.
- Child components use **domain service singletons with subscriber patterns** as their source of truth: `errorTrackingService` (error cache + 30s background sync), `debugActionsService` (action list, status map, history), `logManagementService` (recent-log cache + 5s background sync + SSE), and `liveMonitoringService` (event/metric caches + WebSocket). Components subscribe on mount and unsubscribe on unmount.
- `frontendLoggingService` (client-side, rate-limited) writes all debug activity into the frontend log store (`globalLogStore` via `logStoreInstance`), which is what the Log Viewer tab ultimately displays alongside backend logs.
- `loggingConfigService` holds the client-side tracing/logging configuration edited by `TraceControls` and `LoggingConfigPanel`.

## API Endpoints Called

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/debug/errors` | Load tracked errors (Error Analysis tab) |
| POST | `/api/v1/debug/errors/{id}/resolve` | Mark an error resolved |
| DELETE | `/api/v1/debug/errors/{id}` | Ignore/remove an error |
| GET | `/api/v1/debug/actions` | List available debug actions |
| GET | `/api/v1/debug/actions/{id}/status` | Poll status of running actions |
| (per action) | action's own `endpoint` (POST/DELETE/GET) | Execute a debug action |
| WS | `/api/v1/monitoring/stream` | Live monitoring event stream (Live Monitoring tab) |
| GET | `/api/v1/monitoring/stats` | Monitoring metrics polling |
| GET | `/api/v1/logs/file/recent?n={limit}` | Recent log entries (Settings/Log Viewer tab) |
| SSE | `/api/v1/logs/stream` | Live log streaming |
| GET | `/api/v1/logs/export?format=json|csv` | Export logs as downloadable blob |
| DELETE | `/api/v1/logs/file/clear?frontend=true&backend=false` | Clear the frontend log file |
| GET | `/api/v1/logs/recent?n={limit}&source=FlowTrace` | Flow-trace log source for Trace Analysis tab |
| GET | `/api/v1/logs/traces/export?format=&limit=` | Export filtered traces as JSON/CSV |
| SSE | `/api/v1/agent-chat/trace-stream` | Cognitive pipeline trace stream (event `cognitive_trace_complete`) |
| GET | `/api/v1/agent-chat/session/traces?limit=50` | Historical cognitive traces |
| GET | `/api/v1/traces/traces?limit=50[&session_id=][&source=]` | Agent trace summaries (Agent Traces tab) |
| GET | `/api/v1/traces/traces/{traceId}` | Observations for one agent trace |
| DELETE | `http://localhost:8000/api/v1/sessions/all` | Clear all sessions/messages (Database tab) |

## Related Pages

- [[Logs]] — dedicated log viewing/analysis page; the Settings tab shares the same `logManagementService` data source
- [[SystemHistory]] — log pattern and frequency analysis over the same backend logs
- [[RagIndex]] — system health and diagnostics (sibling monitoring surface)
- [[TestingDashboard]] — Phase 3 testing tools page; Debugging is its Phase 4 debugging counterpart
- [[AgentInteraction]] — chat page that generates the agent/cognitive traces inspected here
- [[CognitivePipeline]] — configures the cognitive pipeline whose per-component traces appear in the Cognitive Traces tab
- [[Dashboard]] — main entry point linking to this page
