---
title: AgentToolService
type: atlas-service
path: frontend/src/services/domain/AgentToolService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# AgentToolService

**Path**: `frontend/src/services/domain/AgentToolService.ts`
**Type**: service (class + singleton)

## Purpose
Per-agent tool management — list agent tools, enable/update/disable tools for an agent.

## Exported API
```typescript
export class AgentToolService {
  listAgentTools(agentId): Promise<AgentTool[]>
  getAgentTool(agentId, toolId): Promise<AgentTool>
  enableToolForAgent(agentId, toolId): Promise<AgentTool>
  updateAgentTool(agentId, toolId, data): Promise<AgentTool>
  disableToolForAgent(agentId, toolId): Promise<AgentTool>
}
export const agentToolService = new AgentToolService()
```

## Endpoints
- `/api/v1/tools/agents` (+ /{agentId}/tools variants)

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| apiClient | services/apiClient.ts | Requests |
| AgentTool types | types | Data shapes |

## Usage Example
```tsx
await agentToolService.enableToolForAgent(agentId, toolId)
```

## Data Flow / Notes
- Active consumers: ToolBrowser, AgentToolManager, ToolPicker

## Related
- features/agentTools/ToolBrowser/ToolBrowser.tsx — consumer
- features/agentTools/AgentToolManager/AgentToolManager.tsx — consumer
- features/agentInteraction/ToolPicker.tsx — consumer

## Deprecation / Obsolete Notes
Active service — 3 consumers. No deprecation markers.