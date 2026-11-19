---
title: AgentTableRow
type: atlas-component
path: frontend/src/components/AgentProfiles/AgentTableRow.tsx
confidence: high
updated: 2026-09-10
tags: [type/component, domain/atlas-ui]
---
# AgentTableRow

**Path**: `frontend/src/components/AgentProfiles/AgentTableRow.tsx`
**Last Updated**: 2026-09-10

## Purpose
Single agent row — selection checkboxes (row select + profile select), name/provider/model, actions (duplicate, manage tools, more via AgentTableActions).

## Props Interface
```typescript
interface AgentTableRowProps {
  profile: Profile
  isSelected: boolean
  isRowSelected: boolean
  onSelect: () => void
  onSelectProfile: () => void
  onDuplicate: () => void
  isLoading: boolean
  onManageTools?: (agentId: string) => void
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| AgentTableActions | AgentProfiles/AgentTableActions.tsx | Row action menu |
| Profile | types | Agent data |

## Usage Example
```tsx
<AgentTableRow profile={p} isSelected={sel} isRowSelected={rowSel} onSelect={...} onSelectProfile={open} onDuplicate={dupe} isLoading={false} onManageTools={manage} />
```

## State Used
None — the component is stateless (no hooks); row hover styling is pure CSS.

## Related Components
- AgentProfiles/AgentTable.tsx — owner
- AgentProfiles/AgentTableActions.tsx — action menu