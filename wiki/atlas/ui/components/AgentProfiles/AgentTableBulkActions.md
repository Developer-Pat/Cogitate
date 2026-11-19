---
title: AgentTableBulkActions
type: atlas-component
path: frontend/src/components/AgentProfiles/AgentTableBulkActions.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# AgentTableBulkActions

**Path**: `frontend/src/components/AgentProfiles/AgentTableBulkActions.tsx`
**Last Updated**: 2026-08-01

## Purpose
Bulk-action bar for the agents table — selected count with bulk delete (confirm dialog) and clear-selection.

## Props Interface
```typescript
interface AgentTableBulkActionsProps {
  selectedCount: number
  onBulkDelete: () => Promise<void>
  onClearSelection: () => void
}
```

## Dependencies
None (window.confirm for delete).

## Usage Example
```tsx
<AgentTableBulkActions selectedCount={sel.size} onBulkDelete={bulkDelete} onClearSelection={clearSel} />
```

## State Used
None — controlled.

## Related Components
- AgentProfiles/AgentTable.tsx — owner
- Tools/ToolsTableBulkActions.tsx — parallel pattern