---
title: Error Tracking Service
type: atlas-service
path: frontend/src/services/domain/ErrorTrackingService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# Error Tracking Service

**Path**: `frontend/src/services/domain/ErrorTrackingService.ts`
**Type**: service

## Purpose

Centralized error tracking and management for the frontend. Provides a single source of truth for error state with:

- Real-time error tracking from the backend (polled, not pushed)
- Error resolution and management (resolve / ignore / clear)
- Reactive updates via a subscriber pattern
- Client-side cache so components always get current data

The service is intentionally decoupled from React/Zustand: it is a plain TypeScript class exported as a module-level singleton, and UI components subscribe to changes. It was designed to use a `traceService` for instrumentation, but all trace calls are commented out (see Deprecation / Obsolete Notes).

## Exported API

The file exports the singleton instance `errorTrackingService` plus the `ErrorTrackingService` class (used directly by unit tests). Exact signatures from source:

### Types

```ts
export type ErrorSeverity = 'low' | 'medium' | 'high' | 'critical'
export type ErrorType = 'error' | 'warning' | 'info'
export type ErrorStatus = 'active' | 'resolved' | 'ignored'

export interface ErrorEntry {
  id: string
  type: ErrorType
  message: string
  stackTrace?: string
  timestamp: string
  source: string
  severity: ErrorSeverity
  context?: Record<string, unknown>
  status: ErrorStatus
  resolvedAt?: string
  resolvedBy?: string
}

export interface ErrorFilters {
  type?: ErrorType | ErrorType[]
  severity?: ErrorSeverity | ErrorSeverity[]
  status?: ErrorStatus | ErrorStatus[]
  source?: string
  search?: string
  from?: string
  to?: string
}

export interface ErrorStats {
  total: number
  byType: Record<ErrorType, number>
  bySeverity: Record<ErrorSeverity, number>
  byStatus: Record<ErrorStatus, number>
  bySource: Record<string, number>
  last24Hours: number
  trend: 'up' | 'down' | 'stable'
}
```

### Class `ErrorTrackingService`

```ts
export class ErrorTrackingService {
  getErrors(filters?: ErrorFilters): ErrorEntry[]                      // filter cached errors (type/severity/status/source/search)
  getError(errorId: string): ErrorEntry | null                         // single error from cache by ID
  subscribe(callback: ErrorSubscriber): () => void                     // subscribe to changes; immediately invoked with current state; returns unsubscribe fn
  async loadFromBackend(filters?: ErrorFilters): Promise<void>         // fetch errors from backend, replace cache, notify subscribers; throws on failure
  async resolveError(errorId: string): Promise<void>                   // POST resolve; updates cache status to 'resolved'
  async ignoreError(errorId: string): Promise<void>                    // DELETE error; removes from cache
  async reportError(error: Omit<ErrorEntry, 'id' | 'status'>): Promise<ErrorEntry>  // POST new error; prepends to cache
  async getErrorStats(): Promise<ErrorStats>                           // GET stats; falls back to zeroed ErrorStats on failure
  async clearResolved(): Promise<void>                                 // DELETE resolved; removes resolved from cache
  clearAll(): void                                                     // clears cache locally (no backend call), notifies
  stopBackgroundSync(): void                                           // clearInterval for the 30s poll
  destroy(): void                                                      // stopBackgroundSync + clear subscribers
  getStatus(): { errorCount: number; subscriberCount: number; isLoading: boolean; lastSyncTime: Date | null }
}

type ErrorSubscriber = (errors: ErrorEntry[]) => void

// Singleton instance
export const errorTrackingService = new ErrorTrackingService()
```

Constructor side effect: `startBackgroundSync()` runs `loadFromBackend()` every 30 seconds (`setInterval`, 30000 ms) to keep the cache fresh.

## Endpoints

All calls go through `apiClient` (base URL `import.meta.env.VITE_API_URL || 'http://localhost:8000'`), with `basePath = '/api/v1/debug/errors'`.

| Method | Path | Service method | Backend status |
|---|---|---|---|
| GET | `/api/v1/debug/errors?type=&severity=&status=&source=&search=&from=&to=` | `loadFromBackend` | ✅ Route exists — **stub** (always returns `{"errors": [], "total": 0, ...}`) |
| POST | `/api/v1/debug/errors` | `reportError` | ❌ **No backend route** (404) |
| GET | `/api/v1/debug/errors/stats` | `getErrorStats` | ❌ **No backend route** (404) |
| POST | `/api/v1/debug/errors/{errorId}/resolve` | `resolveError` | ✅ Route exists — **stub** (canned success) |
| DELETE | `/api/v1/debug/errors/{errorId}` | `ignoreError` | ✅ Route exists — **stub** (canned success) |
| DELETE | `/api/v1/debug/errors/resolved` | `clearResolved` | ✅ Route exists — **stub** (canned success) |

Backend router: `backend/app/api/v1/debug/router.py` (`APIRouter(prefix="/debug", tags=["debug"])`, mounted under `/api/v1`). Every error endpoint is a stub implementation — no persistence, no real error store.

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `apiClient` (`../apiClient`) | HTTP client | All backend calls; base URL `VITE_API_URL` or `http://localhost:8000` |
| `frontendLoggingService` (`../frontendLoggingService`) | logging service | `info`/`error` logging of service operations (load, resolve, ignore, report, clear) |
| `traceService` | tracing service | **Commented out** — all `traceService.trace(...)` calls are disabled in source; not an active dependency |

## Usage Example

```ts
import { errorTrackingService } from '../../services/domain/ErrorTrackingService'

// Load initial errors (fails loudly if backend unavailable)
await errorTrackingService.loadFromBackend()

// Subscribe to reactive updates — callback fires immediately with current state
const unsubscribe = errorTrackingService.subscribe((errors) => {
  console.log('errors updated', errors.length)
})

// Filter cached errors
const critical = errorTrackingService.getErrors({ severity: 'critical', status: 'active' })

// Manage errors
await errorTrackingService.resolveError('err-123')   // mark resolved
await errorTrackingService.ignoreError('err-456')    // delete from backend + cache

// Cleanup on unmount
unsubscribe()
```

## Data Flow / Notes

1. **Instantiation**: the module instantiates the singleton at import time; the constructor immediately starts a 30-second background poll of `loadFromBackend()`.
2. **Cache-first reads**: `getErrors`/`getError` read from the in-memory `errors` array; writes (`resolveError`, `ignoreError`, `reportError`, `clearResolved`) optimistically update the cache after the backend call succeeds, then call `notifySubscribers()`.
3. **Subscriber pattern**: `subscribe()` returns an unsubscribe closure; subscribers are stored in a `Set<ErrorSubscriber>` and receive the full errors array on every change. Components must unsubscribe on unmount (see `destroy()` for full teardown).
4. **Concurrency guard**: `loadFromBackend` no-ops while `isLoading` is true; it throws on failure (callers decide how to surface it — `ErrorAnalysis.tsx` re-throws to fail loudly).
5. **Backend wiring is effectively client-side only**: the service makes real HTTP calls, but every matching backend endpoint is a stub returning empty lists or canned success, and `reportError` / `getErrorStats` target routes that do not exist in the backend at all. There is no real error persistence or retrieval — the cache will always be empty in practice unless the backend debug router is implemented.

## Related

- `frontend/src/components/features/debugging/ErrorAnalysis.tsx` — **main runtime consumer**. Calls `loadFromBackend()` on mount (re-throws on failure with "BACKEND API NOT AVAILABLE"), subscribes to updates, renders filters + list + detail modal, and invokes `resolveError` / `ignoreError` from Resolve/Ignore buttons.
- `frontend/src/pages/Debugging.tsx` — imports only the `ErrorEntry` **type** (for a local `_activeErrors` state; unused underscore-prefixed); renders `<ErrorAnalysis>` in the "errors" tab.
- `frontend/src/services/domain/__tests__/ErrorTrackingService.test.ts` — unit tests; instantiates `ErrorTrackingService` directly (not the singleton).

## Deprecation / Obsolete Notes

- **No `@deprecated` markers** in the source; the service is not formally deprecated and has active consumers (`ErrorAnalysis.tsx`, unit tests).
- **Backend counterpart is stubbed**: `backend/app/api/v1/debug/router.py` comments say "Stub implementation - returns empty list" / "Can be extended with actual error tracking in the future" — the feature was scaffolded but never implemented server-side.
- **Two frontend calls have no backend route**: `POST /api/v1/debug/errors` (`reportError`) and `GET /api/v1/debug/errors/stats` (`getErrorStats`) will fail against the current backend.
- **Dead instrumentation**: all `traceService.trace(...)` calls are commented out (a commented note says re-enable "when debugging is needed"), and a `frontendLoggingService.info` call in `loadFromBackend` is commented out with a 're-enable when debugging is needed' note (verbatim source comment, not a documentation gap). `ErrorAnalysis.tsx` has the same commented-out debug logging pattern.
- **Watch item**: `Debugging.tsx`'s `_activeErrors` state (fed by `handleErrorResolve`/`handleErrorIgnore` props) is never read — leftover scaffolding around the ErrorAnalysis integration.
