---
title: TeamsTable
type: atlas-component
path: frontend/src/components/Teams/TeamsTable.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# TeamsTable

**Path**: `frontend/src/components/Teams/TeamsTable.tsx`
**Last Updated**: 2026-08-01

## Purpose
Teams listing table — team rows with open/edit/delete actions (teams are modeled as Collections with a team entity type).

## Props Interface
```typescript
interface TeamsTableProps {
  teams: Collection[]
  onOpen: (id: string) => void
  onEdit: (team: Collection) => void
  onDelete: (team: Collection) => void
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| Collection | types/collections | Team-as-collection data |

## Usage Example
```tsx
<TeamsTable teams={teams} onOpen={open} onEdit={edit} onDelete={del} />
```

## State Used
None — stateless.

## Related Components
- pages/TeamsManagement.tsx — owner page
- pages/TeamDetail.tsx — detail page opened via onOpen