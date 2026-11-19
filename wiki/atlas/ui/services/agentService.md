---
title: agentService (root)
type: atlas-service
path: frontend/src/services/agentService.ts
confidence: high
updated: 2026-09-10
tags: [type/service, domain/atlas-ui]
---
# agentService (root)

**Path**: `frontend/src/services/agentService.ts`
**Type**: service (object singleton)

## Purpose
Agent management and configuration API client — CRUD for agents, metrics, types, capabilities.

## Exported API
```typescript
export const agentService = {
  getAgents(): Promise<ApiResponse<AgentInfo[]>>
  getAgentById(id): Promise<ApiResponse<AgentInfo>>
  getAgentMetrics(id?): Promise<ApiResponse<AgentMetrics>>
  createAgent(config): Promise<ApiResponse<AgentInfo>>
  updateAgent(id, config): Promise<ApiResponse<AgentInfo>>
  // + delete/actions per source
}
```

## Endpoints
- `GET/POST /api/v1/agents`, `GET/PUT/DELETE /api/v1/agents/{id}`
- `GET /api/v1/agents/types`, `GET /api/v1/agents/capabilities`
- `GET /api/v1/agents/{id}/metrics`; lifecycle `POST /api/v1/agents/{id}/start|stop|restart`; `GET /api/v1/agents/{id}/test`

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| apiClient | services/apiClient.ts | Enhanced client (auth/retry) |
| AgentInfo, AgentConfig, AgentMetrics | types | Data shapes |

## Usage Example
```tsx
const res = await agentService.getAgents()
if (!res.error) setAgents(res.data)
```

## Data Flow / Notes
- Root variant — the domains/llm/agentService.ts is a separate, smaller service

## Related
- Re-exported from `services/index.ts` as `legacyAgentService` ("Import legacy services for backward compatibility") — **no direct consumers**.
- The active agent-management hook family (`hooks/useAgents.ts`) wraps the separate `services/domains/llm/agentService.ts`, not this legacy object.