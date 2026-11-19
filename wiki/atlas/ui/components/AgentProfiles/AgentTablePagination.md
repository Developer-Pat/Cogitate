---
title: AgentTablePagination
type: atlas-component
path: frontend/src/components/AgentProfiles/AgentTablePagination.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# AgentTablePagination

**Path**: `frontend/src/components/AgentProfiles/AgentTablePagination.tsx`
**Last Updated**: 2026-08-01

## Purpose
Agents-table pagination — page buttons, prev/next, page-size selector, item-range display.

## Props Interface
```typescript
interface AgentTablePaginationProps {
  currentPage: number
  pageSize: number
  totalItems: number
  onPageChange: (page: number) => void
  onPageSizeChange: (pageSize: number) => void
}
```

## Dependencies
None (pure JSX).

## Usage Example
```tsx
<AgentTablePagination currentPage={page} pageSize={size} totalItems={total} onPageChange={setPage} onPageSizeChange={setSize} />
```

## State Used
None — controlled.

## Related Components
- AgentProfiles/AgentTable.tsx — owner
- Tools/ToolsTablePagination.tsx — parallel pattern