---
title: ragService
type: atlas-service
path: frontend/src/services/ragService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# ragService

**Path**: `frontend/src/services/ragService.ts`
**Type**: service (object singleton)

## Purpose
RAG pipeline status + ingest control — get status, trigger ingest, poll ingest job status.

## Exported API
```typescript
export const ragService = {
  getStatus(): Promise<ApiResponse<RagStatus>>
  triggerIngest(options?): Promise<ApiResponse<...>>
  getIngestJobStatus(jobId): Promise<ApiResponse<...>>
}
```

## Endpoints
- `GET /api/v1/rag/status`, `POST /api/v1/rag/ingest`, `GET /api/v1/rag/ingest/status`

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| apiClient | services/apiClient.ts | Requests |

## Usage Example
```tsx
const status = await ragService.getStatus()
```

## Data Flow / Notes
- RAG ingest is deferred in todo (per-agent specialization planned); service exists for SystemInfo tab

## Related
- pages/SystemInfo.tsx — consumer (RAG tab)
- RAG redesign (Option B, per-agent) — planned; not built

## Deprecation / Obsolete Notes
Active (1 page consumer). No deprecation markers. RAG system itself is a deferred/future item.