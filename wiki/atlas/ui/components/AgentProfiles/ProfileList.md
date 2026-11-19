---
title: ProfileList
type: atlas-component
path: frontend/src/components/AgentProfiles/ProfileList.tsx
confidence: high
updated: 2026-09-10
tags: [type/component, domain/atlas-ui]
---
# ProfileList

**Path**: `frontend/src/components/AgentProfiles/ProfileList.tsx`
**Last Updated**: 2026-09-10

## Purpose
Agent profile list — selectable rows (or table view), create-new/duplicate actions, team filtering, view-mode toggle.

## Props Interface
```typescript
interface ProfileListProps {
  profiles: Profile[]
  selectedProfileId?: string
  onSelectProfile: (profile: Profile) => void
  onCreateNew: () => void
  onDuplicate?: (profile: Profile) => void
  isLoading?: boolean
  viewMode?: 'list' | 'table'
  onViewModeChange?: (mode: 'list' | 'table') => void
  // Team filtering
  teams?: Collection[]
  selectedTeamId?: string | 'all'
  onTeamChange?: (teamId: string | 'all') => void
  loadingTeams?: boolean
  totalProfiles?: number
  // Archived section (2026-08-19): archivedAgents, onRestoreAgent,
  // onHardDeleteAgent, showArchived, onToggleArchived
  // ... additional props from source
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| Profile | types | Agent profile shape |
| Collection | types/collections | Team filter data |

## Usage Example
```tsx
<ProfileList profiles={profiles} selectedProfileId={sel?.id} onSelectProfile={select} onCreateNew={create} viewMode={vm} onViewModeChange={setVm} teams={teams} selectedTeamId={selectedTeamId} onTeamChange={setSelectedTeamId} loadingTeams={loadingTeams} totalProfiles={profiles.length} />
```

## State Used
Local `useState`: `searchQuery` (client-side name/description filter), `duplicatingId`, `addingToCollectionProfile` (the add-to-collection modal target). The team filter and view mode are controlled from the parent.

## Related Components
- AgentProfiles/AgentTable.tsx — table view variant
- pages/AgentProfiles.tsx — owner page