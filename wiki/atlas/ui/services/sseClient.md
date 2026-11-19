---
title: sseClient
type: atlas-service
path: frontend/src/services/sseClient.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# sseClient

**Path**: `frontend/src/services/sseClient.ts`
**Type**: service (SSEClient class + SSEClientFactory)

## Purpose
Server-Sent Events client — EventSource wrapper with auto-reconnect, JSON parse, and a factory for the app's four stream types.

## Exported API
```typescript
interface SSEOptions {
  url: string; headers?: Record<string, string>; withCredentials?: boolean;
  retryInterval?: number;  // default 3000
  maxRetries?: number;     // default 5
  onOpen?: (event: Event) => void; onMessage?: (event: SSEEvent) => void;
  onError?: (event: Event) => void; onClose?: (event: Event) => void;
}
interface SSEEvent { id?: string; event?: string; data: string; retry?: number }

class SSEClient {
  constructor(options: SSEOptions)
  connect(): void
  disconnect(): void
}

class SSEClientFactory {
  static createLLMStreamClient(sessionId, onMessage): SSEClient      // /api/v1/chat/stream?session_id=..
  static createWorkflowProgressClient(workflowId, onMessage)          // /api/v1/workflows/{id}/progress
  static createSystemMetricsClient(onMessage)                         // /api/v1/system/metrics
  static createLogStreamClient(onMessage)                             // /api/v1/system/logs/stream
}
```

## Endpoints
- `/api/v1/chat/stream`, `/api/v1/workflows/{id}/progress`, `/api/v1/system/metrics`, `/api/v1/system/logs/stream`

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| frontendLoggingService | services | Connection/error logging |
| EventSource | Browser API | SSE transport |

## Usage Example
```tsx
const client = SSEClientFactory.createLLMStreamClient(sessionId, onMsg)
client.connect()
```

## Data Flow / Notes
- Retry with backoff (retryInterval, maxRetries); data auto-JSON-parsed when possible

## Related
- hooks/useSSE.ts — React wrapper (useLLMStream/useWorkflowProgress/useSystemMetrics/useLogStream)
- services/domain/StreamingService.ts — chat streaming engine