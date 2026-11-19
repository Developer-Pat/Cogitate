---
title: AgentToolManager
type: atlas-component
path: frontend/src/components/features/agentTools/AgentToolManager/AgentToolManager.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---

# AgentToolManager

**Path**: `frontend/src/components/features/agentTools/AgentToolManager/AgentToolManager.tsx`
**Last Updated**: 2026-08-01

## Purpose

Table-based management UI for agent-tool associations. Lets a user search and filter the tool catalog, assign/unassign tools to an agent, enable/disable assigned tools, edit per-tool priority, and open a JSON-Schema-driven config modal for tools that define a `config_schema`. Provides bulk enable/disable actions, tag filtering, pagination, and live count summaries. Loads both the agent's current tool associations (`agentToolService.listAgentTools`) and the full tool catalog (`toolService.listTools`) on mount and re-fetches after every mutation. This is the largest file in `agentTools` (725 lines).

## Props Interface

```typescript
export interface AgentToolManagerProps {
  /** Agent ID to manage tools for */
  agentId: string;
  /** Callback when tool configuration is updated */
  onConfigUpdate?: (toolId: string, config: unknown) => void;
  /** Callback when tools are enabled/disabled */
  onToolsChanged?: () => void;
}
```

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `agentToolService` (`../../../../services/domain/AgentToolService`) | singleton service instance | All agent-tool association API calls: list, enable, disable, update (priority/config), bulk disable |
| `toolService` (`../../../../services/domain/ToolService`) | singleton service instance | `listTools()` loads the full tool catalog (5-minute in-memory cache when unfiltered) |
| `AgentToolResponse`, `ToolResponse` (`../../../../types/tools`) | types | State shapes for agent associations and catalog tools |
| `ToolConfigModal` (`./ToolConfigModal`) | child component | Modal for editing a tool's config via generated JSON Schema form or raw JSON |
| `React` (`useState`, `useEffect`, `useMemo`) | React hooks | Local state, data loading, derived filtering/pagination |

### API calls made by this component (via `agentToolService`)

| Call | Endpoint (base `/api/v1/tools/agents/{agentId}`) | Used for |
|---|---|---|
| `listAgentTools(agentId)` | `GET /tools` | Initial load + refresh after every mutation |
| `enableToolForAgent(agentId, { tool_id, priority, config })` | `POST /tools` | Assign or enable a tool |
| `disableToolForAgent(agentId, toolId)` | `POST /tools/{toolId}/disable` | Disable a tool (soft) |
| `updateAgentTool(agentId, toolId, { priority })` | `PUT /tools/{toolId}` | Priority edits (0–100) |
| `updateAgentTool(agentId, toolId, { config })` | `PUT /tools/{toolId}` | Config saves from `ToolConfigModal` |
| `disableAllToolsForAgent(agentId)` | loops `disableToolForAgent` over enabled tools | Bulk disable |

`toolService.listTools()` hits `GET /api/v1/tools` (cached for 5 minutes when called without filters).

## Usage Example

```tsx
import { AgentToolManager } from '../../components/features/agentTools/AgentToolManager/AgentToolManager';

<AgentToolManager
  agentId={agent.id}
  onConfigUpdate={(toolId, config) => {
    frontendLoggingService.info('AgentToolsTab', 'Tool configuration updated', {
      agentId: agent.id, toolId, config,
    });
  }}
  onToolsChanged={() => {
    addNotification({
      type: 'success',
      title: 'Tools Updated',
      message: `Tool assignments for "${agent.name}" have been updated`,
    });
  }}
/>
```

Real consumers: `AgentToolsTab` (`frontend/src/components/AgentProfiles/AgentToolsTab.tsx`) passes all three props; the "Manage Tools" modal in `frontend/src/pages/AgentProfiles.tsx` passes only `agentId` + `onToolsChanged`.

## State Used

All state is local (`useState`); the component reads no global stores.

| State | Type | Purpose |
|---|---|---|
| `agentTools` | `AgentToolResponse[]` | Agent's current tool associations |
| `allTools` | `ToolResponse[]` | Full tool catalog |
| `loading` | `boolean` | Initial-load spinner state |
| `error` | `string \| null` | Load error (renders retry screen) |
| `configModalOpen` | `boolean` | ToolConfigModal visibility |
| `selectedTool` | `AgentToolResponse \| null` | Agent-tool being configured in the modal |
| `bulkOperation` | `'enable' \| 'disable' \| null` | In-flight bulk action (drives button spinner/disabled state) |
| `searchQuery` | `string` | Name/description/tag search filter |
| `selectedTags` | `string[]` | Active tag filters |
| `filterStatus` | `'all' \| 'assigned' \| 'available'` | Status filter |
| `showTagDropdown` | `boolean` | Tag dropdown visibility |
| `currentPage` | `number` | Pagination page (reset to 1 on filter change) |
| `pageSize` | `number` | Rows per page (5/10/20/50, default 10) |

Derived via `useMemo`: `allTags` (unique sorted tags across the catalog), `filteredTools` (search + tag + status filtering), `assignedTools` (paginated catalog rows augmented with `agentTool`, `is_assigned`, `is_enabled`, `priority`, `config` for table rendering). Counts derived inline: `enabledToolsCount`, `disabledToolsCount`, `assignedToolsCount`, `availableToolsCount`.

## Related Components

- `ToolConfigModal` — `frontend/src/components/features/agentTools/AgentToolManager/ToolConfigModal.tsx` (child; JSON-Schema config editing)
- `ToolBrowser` — `frontend/src/components/features/agentTools/ToolBrowser/ToolBrowser.tsx` (sibling; read-only tool catalog browser)
- `ToolCard`, `SearchBar`, `CategoryTree` — `frontend/src/components/features/agentTools/ToolBrowser/` (ToolBrowser subcomponents)
- `AgentToolsTab` — `frontend/src/components/AgentProfiles/AgentToolsTab.tsx` (wrapper adding notifications/logging)
- `AgentProfiles` page — `frontend/src/pages/AgentProfiles.tsx` (hosts this component in a "Manage Tools" modal)
- `index.ts` — `frontend/src/components/features/agentTools/index.ts` (barrel re-exports `AgentToolManager` and `AgentToolManagerProps`)
