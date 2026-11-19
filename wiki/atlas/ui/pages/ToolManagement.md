---
title: Tool Management
type: atlas-page
path: frontend/src/pages/ToolManagement.tsx
confidence: high
updated: 2026-07-31
tags: [type/page, domain/atlas-ui]
---
# Tool Management

**Component**: `frontend/src/pages/ToolManagement.tsx`
**Route**: `/tools`
**Last Updated**: 2026-07-31

## Purpose
Compact table-based tool management page — list, select, and delete agent tools.

## Key Features
- Loads tools from backend on mount (spinner while loading)
- **ToolsTable**: multi-select rows, duplicate action (not yet implemented — toast), delete action
- Error alert with dismiss on load failure

## Components Used
| Component | Path | Purpose |
|-----------|------|---------|
| ToolsTable | `components/Tools/` | Tool table with selection/actions |

## Hooks Used
| Hook | Path | Purpose |
|------|------|---------|
| usePageTitle | `hooks/usePageTitle.ts` | Sets document title |

## Data Flow
- **Load**: `toolService.listTools()` -> `GET /api/v1/tools` -> `setTools(response.tools)`
- **Delete**: `toolService.deleteTool(id)` -> `DELETE /api/v1/tools/{id}` -> reload list + success toast
- **Duplicate**: placeholder — shows 'not yet implemented' toast

## State Management
- `notificationStore` — toasts for load errors / delete results
- Local state: tools array, selectedToolIds set, loading, error

## API Endpoints Called
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v1/tools` | List tools |
| DELETE | `/api/v1/tools/{id}` | Delete tool |

## Related Pages
- ToolCollectionsManagement — collection-level tool management
- AgentProfiles — per-agent tool assignment (AgentToolManager)