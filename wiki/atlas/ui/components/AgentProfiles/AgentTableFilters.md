---
title: AgentTableFilters
type: atlas-component
path: frontend/src/components/AgentProfiles/AgentTableFilters.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# AgentTableFilters

**Path**: `frontend/src/components/AgentProfiles/AgentTableFilters.tsx`
**Last Updated**: 2026-08-01

## Purpose
Agents-table filter bar — search input, multi-select provider dropdown, and All/Active/Inactive status segmented control.

## Props Interface
```typescript
interface AgentTableFiltersProps {
  searchQuery: string
  providers: string[]
  providerFilter: string[]
  statusFilter: 'all' | 'active' | 'inactive'
  onSearch: (query: string) => void
  onProviderFilter: (providers: string[]) => void
  onStatusFilter: (status: 'all' | 'active' | 'inactive') => void
}
```

## Dependencies
None (pure JSX, controlled).

## Usage Example
```tsx
<AgentTableFilters searchQuery={q} providers={provs} providerFilter={pf} statusFilter={sf} onSearch={setQ} onProviderFilter={setPf} onStatusFilter={setSf} />
```

## State Used
None — fully controlled.

## Related Components
- AgentProfiles/AgentTable.tsx — owner
- pages/AgentProfiles.tsx — page wiring