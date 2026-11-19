---
title: ToolsTableRow
type: atlas-component
path: frontend/src/components/Tools/ToolsTableRow.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# ToolsTableRow

**Path**: `frontend/src/components/Tools/ToolsTableRow.tsx`
**Last Updated**: 2026-08-01

## Purpose
Single tool row — selection, name, category, type, tags, permission badge (currently a placeholder default badge), hover-revealed actions (duplicate + more via ToolsTableActions).

## Props Interface
```typescript
interface ToolsTableRowProps {
  tool: Tool
  isSelected: boolean
  onSelect: () => void
  onDuplicate: () => void
  isLoading: boolean
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| ToolsTableActions | Component (local) | Row action menu |
| PermissionBadge | Tools/PermissionBadge.tsx | Default permission display (placeholder per code comment) |
| Tool | types/tools | Tool data |

## Usage Example
```tsx
<ToolsTableRow tool={t} isSelected={sel} onSelect={...} onDuplicate={dupe} isLoading={false} />
```

## State Used
- showActions (hover state)

## Related Components
- Tools/ToolsTable.tsx — owner
- Tools/ToolsTableActions.tsx — action menu