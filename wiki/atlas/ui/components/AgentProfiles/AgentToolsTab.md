---
title: AgentToolsTab
type: atlas-component
path: frontend/src/components/AgentProfiles/AgentToolsTab.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# AgentToolsTab

**Path**: `frontend/src/components/AgentProfiles/AgentToolsTab.tsx`
**Last Updated**: 2026-08-01

## Purpose
Agent tools management tab — hosts the AgentToolManager for a specific agent, with toast feedback on config updates.

## Props Interface
```typescript
interface AgentToolsTabProps {
  agentId: string    // Agent/Profile ID to manage tools for
  agentName: string  // For display purposes
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| AgentToolManager | features/agentTools/AgentToolManager | Tool management UI |
| useNotificationStore | Store | Config-update toasts |

## Usage Example
```tsx
<AgentToolsTab agentId={agent.id} agentName={agent.name} />
```

## State Used
None directly (delegates to AgentToolManager).

## Related Components
- features/agentTools/AgentToolManager/AgentToolManager.tsx — hosted manager
- pages/AgentProfiles.tsx — tab host