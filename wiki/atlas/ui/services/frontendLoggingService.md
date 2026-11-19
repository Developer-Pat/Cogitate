---
title: Frontend Logging Service
type: atlas-service
path: frontend/src/services/frontendLoggingService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# Frontend Logging Service

**Path**: `frontend/src/services/frontendLoggingService.ts`
**Type**: service

## Purpose

Central logging service for the Cogitate frontend. Captures frontend errors, interactions, and timing issues; writes every entry to the in-memory `globalLogStore` (a ring buffer that also persists to localStorage) for instant UI visibility; and best-effort forwards entries to the backend (`POST /api/v1/logs/frontend`) for persistent storage when backend logging is enabled. Ships rate-limiting/deduplication machinery (currently disabled for debugging) plus a `getLogSuppressionSummary()` export for inspecting suppression state.

## Exported API

Multi-export module: one type, one interface, one standalone function, and one service object.

```ts
export type LogLevel = 'debug' | 'info' | 'warning' | 'error' | 'critical'

export interface FrontendLogEntry {
  timestamp: string
  level: LogLevel
  source: string
  message: string
  context?: Record<string, unknown>
  userAgent?: string
  url?: string
  sessionId?: string
  traceId?: string
}

export function getLogSuppressionSummary(): Record<string, number>

export const frontendLoggingService = {
  async sendLog(entry: FrontendLogEntry, _options?: {skipRateLimit?: boolean})
  async sendBatchLogs(entries: FrontendLogEntry[])
  debug(source: string, message: string, context?: Record<string, unknown>)
  info(source: string, message: string, context?: Record<string, unknown>)
  warning(source: string, message: string, context?: Record<string, unknown>)
  error(source: string, message: string, error?: Error | unknown, context?: Record<string, unknown>)
  critical(source: string, message: string, error?: Error | unknown, context?: Record<string, unknown>)
  logMessageSync(sessionId: string, messageId: string, role: 'user' | 'assistant', status: 'started' | 'success' | 'failed' | 'retry', duration?: number, error?: Error | unknown)
  logStreamingMetrics(sessionId: string, messageId: string, metrics: {totalCharacters: number; totalStreamTime: number; charactersPerSecond: number; estimatedTokensPerSecond: number; timeToFirstChunk?: number})
  logStateUpdateTiming(source: string, operation: string, duration: number, context?: Record<string, unknown>)
}
```

Notes:
- `error()` and `critical()` are documented in source as "NOT rate-limited" and pass `{skipRateLimit: true}` to `sendLog`; they also enrich context with `errorMessage` / `errorStack` derived from the passed error. `debug` / `info` / `warning` pass no options.
- Convenience methods are fire-and-forget (return `void`; they `.catch()` and `console.error` on send failure).
- `sendLog` resolves to `{data: {id: string}, status: number, timestamp: string, error?: {code: string; message: string}}`; `sendBatchLogs` resolves to the same shape with `data: {count: number}` (inferred from implementation — not annotated in source).

## Endpoints

Hit indirectly through `logsService` (never directly), and only when `loggingConfigService.isBackendLoggingEnabled()` is true:

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/v1/logs/frontend` | POST | Persist a single log entry (via `logsService.sendLogToBackend`, 2s timeout, no retries) |
| `/api/v1/logs/frontend/batch` | POST | Persist a batch of log entries (via `logsService.sendBatchLogsToBackend`) |

Backend sends are best-effort: in `sendLog` the call is raced against a 3-second timeout, and failures are swallowed (a per-session flag `window.__cogitateBackendLogErrorShown` prevents repeated reporting). localStorage is treated as the reliable store.

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `../types` | type-only | `LogEntry` (backend-shaped entry), `ApiResponse` return typing |
| `./logStoreInstance` | module (singleton) | `globalLogStore` — in-memory ring buffer (keeps last 1000 entries, newest-first via `unshift`), persists last 500 to `localStorage['cogitate_logs']` |
| `./logsService` | module | `sendLogToBackend` (POST `/api/v1/logs/frontend`), `sendBatchLogsToBackend` (POST `/api/v1/logs/frontend/batch`) |
| `./domain/LoggingConfigService` | module | `loggingConfigService.isBackendLoggingEnabled()` — gate for backend persistence |

Import-direction note: `logStoreInstance` deliberately cannot import `frontendLoggingService` (circular dependency), while `logsService` imports it for its own error reporting — so `frontendLoggingService` only calls `logsService`'s two send functions.

## Usage Example

```ts
import { frontendLoggingService } from '../services/frontendLoggingService'

// App-wide convention: source = component/service name, message = what happened
frontendLoggingService.info('SessionManager', 'Session created', { sessionId })

frontendLoggingService.warning('useSSE', 'Reconnecting to stream', { attempt: 3 })

frontendLoggingService.error('ErrorBoundary', 'Component crashed', error, { componentName: 'ChatView' })

frontendLoggingService.debug('WorkflowRunner', 'Step completed', { step: 2, durationMs: 140 })

// Specialized loggers
frontendLoggingService.logMessageSync(sessionId, messageId, 'assistant', 'failed', 1200, err)
frontendLoggingService.logStreamingMetrics(sessionId, messageId, {
  totalCharacters: 4210,
  totalStreamTime: 8800,
  charactersPerSecond: 478,
  estimatedTokensPerSecond: 120
})
frontendLoggingService.logStateUpdateTiming('useSessionManagement', 'loadSessions', 1240)

// Debugging helper: inspect suppression state (currently always empty — see Data Flow)
console.table(getLogSuppressionSummary())
```

## Data Flow / Notes

1. **Send path**: `debug` / `info` / `warning` / `error` / `critical` / `logMessageSync` / `logStreamingMetrics` / `logStateUpdateTiming` build a `FrontendLogEntry` and call `sendLog`; `sendBatchLogs` loops entries through the same per-entry pipeline.
2. **Context sanitization**: `sendLog` sanitizes `context` — drops `undefined` and function values, and any object whose `JSON.stringify` output exceeds 1000 chars; the whole sanitization is wrapped in try/catch.
3. **Browser context enrichment**: `userAgent` (`navigator.userAgent`) and `url` (`window.location.href`) are merged into context; `sessionId` is forwarded to the backend as `session_id`.
4. **In-memory store first**: `globalLogStore.addLog(logEntry)` runs immediately for instant UI update. The store is a ring buffer: `unshift` + trim to `maxLogs = 1000` in memory; localStorage keeps the last 500 (`MAX_STORED_LOGS`). IDs are generated locally (`log-<ts>-<counter>-<rand>`) and replaced by the backend ID when available.
5. **Backend best-effort**: gated by `loggingConfigService.isBackendLoggingEnabled()`; raced against a 3s timeout in `sendLog`; errors swallowed with a once-per-session flag.
6. **Rate-limiting / suppression machinery (currently disabled)**: `DEFAULT_RATE_LIMIT` defines `maxLogsPerSecond: 10`, `maxIdenticalLogs: 3`, `windowMs: 1000`, `dedupeWindowMs: 5000`; `rateLimitState` tracks recent-log timestamps and per-key identical counts with `suppressed` flags. The entire enforcement block inside `sendLog` is commented out under `// DISABLE RATE LIMITING FOR DEBUGGING - ALL LOGS SHOULD BE VISIBLE`, so **no logs are currently throttled or deduplicated**, and `getLogSuppressionSummary()` — which returns entries whose count exceeds `maxIdenticalLogs` or that are flagged `suppressed` — currently returns `{}` because `rateLimitState.identicalCounts` is never populated. The `_options.skipRateLimit` parameter is accepted but unused until enforcement is re-enabled.
7. **Failure fallback**: if `sendLog` / `sendBatchLogs` throw internally, they resolve (not reject) with a 500-shaped response carrying `error.code: 'logging_service_error'`.
8. **Log-level derivation**: `logMessageSync` maps status → level (`failed` → `error`, `retry` → `warning`, else `info`); `logStateUpdateTiming` maps `duration > 1000` ms → `warning`, else `info`. `logMessageSync` uses source `MessageSync`; `logStateUpdateTiming` uses source `StateUpdate:<source>`; `logStreamingMetrics` uses level `info` and message `Streaming completed for message ${messageId}` with a fixed streaming-metrics source.

## Related

Consumed across ~100 files; all callers follow the `frontendLoggingService.<level>('SourceName', 'message', context?)` convention where `SourceName` is the component / hook / service name.

- **Pages**: `Logs.tsx`, `Debugging.tsx`, `Sessions.tsx`, `Analytics.tsx`, `WorkflowExecution.tsx`, `AgentProfiles.tsx`, `AgentTemplates.tsx`, `TeamDetail.tsx`, `ProviderModelsBrowser.tsx`, `ProviderDashboard.tsx`, `ToolManagement.tsx`, `WorkflowTemplates.tsx`
- **Hooks**: `useSSE.ts`, `useAgentInteraction.ts`, `useSessionManagement.ts`, `useConfiguration.ts`, `useWorkflowExecution.ts`, `useGlobalSearch.ts`, `useSettings.ts`, `useChatMacros.ts`, `useSearchHistory.ts`, `useAgentSelection.ts`, `useLogsFilters.ts`, `useUIStateBridge.ts`, `useLocalStorage.ts`, `useModeMacros.ts`
- **Services**: `logsService.ts` (uses it for its own error reporting), `sessionSyncService.ts`, `api.ts`, `offlineSyncQueue.ts`, `runtimeConfigService.ts`, `userSettingsService.ts`, `macroExportService.ts`, `uiStateBridge.ts`, `chatMacroService.ts`, `sseClient.ts`, plus most `services/domain/*` services (e.g. `SessionService.ts`, `MessageService.ts`, `StreamingService.ts`, `ErrorTrackingService.ts`, `TraceService.ts`, `LogManagementService.ts`, `LiveMonitoringService.ts`)
- **Components**: `ErrorBoundary.tsx`, `LogDetailsModal.tsx`, debugging feature components (`LogViewer.tsx`, `TraceControls.tsx`, `LiveMonitoring.tsx`, `SystemDiagnostics.tsx`, `TraceAnalysis.tsx`, `DebugControls.tsx`, `ErrorAnalysis.tsx`, `CognitiveTraceViewer.tsx`), agentInteraction components (`SessionManager.tsx`, `ResponseStream.tsx`, `SessionActions.tsx`, `MessageMetadata.tsx`, `QuickSettingsPanel.tsx`, `MacroModeRow.tsx`), workflow execution components (`WorkflowRunner.tsx`, `ProgressTracker.tsx`, `ResultViewer.tsx`), `HelpModal.tsx`, `SessionTable.tsx`, `SessionDetailsModal.tsx`, `ProfileList.tsx`, `ProfileDetail.tsx`, `TeamMembersTab.tsx`, `CognitiveProfileSelector.tsx`, `PipelineConfigTab.tsx`, `ModelFilters.tsx`
- **Utils**: `autoLogging.ts`, `mockDetector.ts`, `chatStateStorage.ts`
