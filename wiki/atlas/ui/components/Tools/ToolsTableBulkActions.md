---
title: ToolsTableBulkActions
type: atlas-component
path: frontend/src/components/Tools/ToolsTableBulkActions.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# ToolsTableBulkActions

**Path**: `frontend/src/components/Tools/ToolsTableBulkActions.tsx`
**Last Updated**: 2026-08-01

## Purpose
Bulk-action bar for the tools table — shows selected count with bulk delete (confirm dialog) and clear-selection.

## Props Interface
```typescript
interface ToolsTableBulkActionsProps {
  selectedCount: number
  onBulkDelete: () => Promise<void>
  onClearSelection: () => void
}
```

## Dependencies
None (window.confirm for delete).

## Usage Example
```tsx
<ToolsTableBulkActions selectedCount={sel.size} onBulkDelete={bulkDelete} onClearSelection={clearSel} />
```

## State Used
None — controlled.

## Related Components
- Tools/ToolsTable.tsx — owner
- Tools/ToolsTableRow.tsx — per-row selection