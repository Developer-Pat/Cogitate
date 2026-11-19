---
title: ToolService
type: atlas-service
path: frontend/src/services/domain/ToolService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# ToolService

**Path**: `frontend/src/services/domain/ToolService.ts`
**Type**: service (class + singleton)

## Purpose
Tool registry CRUD — list/search tools, get by id/slug, create.

## Exported API
```typescript
export class ToolService {
  listTools(filters?): Promise<Tool[]>
  getTool(id): Promise<Tool>
  getToolBySlug(slug): Promise<Tool>
  createTool(data): Promise<Tool>
}
export const toolService = new ToolService()
```

## Endpoints
- `/api/v1/tools`

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| apiClient | services/apiClient.ts | Requests |
| Tool | types/tools | Data shape |

## Usage Example
```tsx
const tools = await toolService.listTools()
```

## Data Flow / Notes
- Widely used across tool surfaces

## Related
- features/agentTools/ToolBrowser/ToolBrowser.tsx, AgentToolManager.tsx
- features/collections/AddToolsToToolboxModal.tsx
- features/agentInteraction/ToolPicker.tsx, Teams/AddToolsModal.tsx
- pages/AgentProfiles.tsx

## Deprecation / Obsolete Notes
Active (6 consumers). No deprecation markers.