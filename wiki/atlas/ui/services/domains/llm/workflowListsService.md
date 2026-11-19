---
title: workflowListsService
type: atlas-service
path: frontend/src/services/domains/llm/workflowListsService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# workflowListsService

**Path**: `frontend/src/services/domains/llm/workflowListsService.ts`
**Type**: service (object singleton)

## Purpose
Workflow lists CRUD — lists of workflows with tag filtering.

## Exported API
```typescript
export const workflowListsService = {
  // lists CRUD + tag filter methods — exact signatures from source
}
```

## Endpoints
- `/api/v1/workflow-lists`

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| apiClient | services/apiClient.ts | Requests |

## Usage Example
```tsx
await workflowListsService.createList({ name, tags })
```

## Data Flow / Notes
- Backs the workflow lists UI

## Related
- hooks/useWorkflowLists.ts — consumer
- pages/WorkflowExecution.tsx — consumer

## Deprecation / Obsolete Notes
Active (2 consumers). No deprecation markers.