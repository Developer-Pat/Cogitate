---
title: apiClient
type: atlas-service
path: frontend/src/services/apiClient.ts
confidence: high
updated: 2026-09-04
tags: [type/service, domain/atlas-ui]
---
# apiClient

**Path**: `frontend/src/services/apiClient.ts`
**Type**: service (class singleton)

## Purpose
Enhanced API client for the backend — comprehensive error handling, auth token support, request/response interceptors, retry logic, timeouts, and a streaming endpoint. Singleton instance `apiClient`.

## Exported API
```typescript
class EnhancedApiClient {
  constructor(baseUrl?: string)  // default VITE_API_URL || http://localhost:8000
  setAuthToken(token: string): void
  clearAuth(): void
  get<T>(endpoint, options?: RequestOptions): Promise<ApiResponse<T>>
  post<T>(endpoint, data?, options?): Promise<ApiResponse<T>>
  put<T>(endpoint, data?, options?): Promise<ApiResponse<T>>
  patch<T>(endpoint, data?, options?): Promise<ApiResponse<T>>
  delete<T>(endpoint, options?): Promise<ApiResponse<T>>
  stream(endpoint, data?, options?): Promise<Response>  // 60s timeout, for SSE
}

interface RequestOptions extends RequestInit {
  timeout?: number   // default 10000
  retries?: number   // default 3
  requireAuth?: boolean  // default true
}
```

## Endpoints
- N/A — generic client; all endpoints via method + path

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| ApiResponse, ApiError | types | Response envelope |
| useUserStore | stores/userStore.ts | clearUser on 401 |

## Usage Example
```tsx
const res = await apiClient.get<LogEntry[]>('/api/v1/logs', { timeout: 5000 })
if (!res.error) setLogs(res.data)
```

## Data Flow / Notes
- Retries up to `retries` times; 429 waits for Retry-After; 401 clears auth + redirects /login
- AbortError (timeout) not retried; FormData skips Content-Type (browser sets boundary)
- Auth token from localStorage 'auth_token'; Bearer header when requireAuth

## The ONE client (2026-09-04, the _34 consolidation)

The duplicate `domains/shared/apiClient.ts` was DELETED — its
machinery (the failure tracker + the 3rd-consecutive notification
+ the recovery toast + the real params support + the final-error
log) was ported INTO this file; the ~51 direct consumers + the 10
domains services all import THIS file. THE BUS EDGE: the client
sits at the bottom of the logging + notification stacks — its
failure edges fire through `services/notifyBus.ts` (a leaf,
registered at the boot in main.tsx), never a direct import (the
cycle doctrine). Full current-state: the api-client dev-note
[[dev-notes/frontend/api-client]].

## Related
- Most services — use apiClient for requests
## API_BASE_URL — the frontend's path locator (2026-08-17)

The exported constant (`VITE_API_URL || http://localhost:8000`)
is the ONE source for the backend base URL. Services and fetch
sites import it; hardcoded `http://localhost:8000` fetch calls
are banned (5 sites fixed). See
[[dev-notes/architecture/Paths and Path Resolution]].
