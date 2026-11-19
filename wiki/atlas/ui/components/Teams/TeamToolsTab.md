---
title: TeamToolsTab
type: atlas-component
path: frontend/src/components/Teams/TeamToolsTab.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# TeamToolsTab

**Path**: `frontend/src/components/Teams/TeamToolsTab.tsx`
**Last Updated**: 2026-08-01

## Purpose
Team tools tab — lists the team's tools grouped by source (direct vs. toolbox), with add-tools/add-toolboxes entry points and per-tool remove.

## Props Interface
```typescript
interface TeamToolsTabProps {
  team: Team
  onAddTools: () => void
  onAddToolboxes: () => void
  onRemoveTool: (toolId: string, sourceType?: 'direct' | 'toolbox') => Promise<void>
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| Team | types | Team data (tools with source_type) |

## Usage Example
```tsx
<TeamToolsTab team={team} onAddTools={openAddTools} onAddToolboxes={openAddToolboxes} onRemoveTool={remove} />
```

## State Used
None — controlled.

## Related Components
- Teams/AddToolsModal.tsx — add-tools flow
- Teams/AddToolboxesModal.tsx — add-toolboxes flow
- pages/TeamDetail.tsx — tab host