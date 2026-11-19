---
title: agentService (llm)
type: atlas-service
path: frontend/src/services/domains/llm/agentService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# agentService (llm)

**Path**: `frontend/src/services/domains/llm/agentService.ts`
**Type**: service (object, domain facade)

## Purpose
LLM-domain agent service — agent listing for chat/sessions surfaces (IAgentService interface).

## Exported API
```typescript
export const agentService: IAgentService = {
  // agent fetch methods (getAgents etc.) — exact signatures from source
}
```

## Endpoints
- `/api/v1/agents`

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| apiClient | services/apiClient.ts | Requests |

## Usage Example
```tsx
import { agentService } from '../../services'
const agents = await agentService.getAgents()
```

## Data Flow / Notes
- Re-exported via services/index.ts + ServiceFactory.getAgentService()

## Related
- components/sessions/SessionFilters.tsx, SessionTable.tsx, SessionDetailsModal.tsx — consumers
- components/Teams/TeamMembersTab.tsx — consumer
- hooks/useAgents.ts — consumer

## Deprecation / Obsolete Notes
Active (5 consumers). No deprecation markers.