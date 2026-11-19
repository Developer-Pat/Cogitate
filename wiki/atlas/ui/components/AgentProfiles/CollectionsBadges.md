---
title: CollectionsBadges
type: atlas-component
path: frontend/src/components/AgentProfiles/CollectionsBadges.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# CollectionsBadges

**Path**: `frontend/src/components/AgentProfiles/CollectionsBadges.tsx`
**Last Updated**: 2026-08-01

## Purpose
Badge row showing which collections contain a profile/agent — fetches membership by profileId and renders icon+name+count badges.

## Props Interface
```typescript
interface Collection {
  id: string
  name: string
  icon: string
  item_count: number
}

// Component prop
{ profileId: string }
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| collectionsService | Service | Membership fetch by profileId (trace actual import) |

## Usage Example
```tsx
<CollectionsBadges profileId={agent.id} />
```

## State Used
- collections, loading (refetch on profileId change)

## Related Components
- AgentProfiles/ProfileDetail.tsx — consumer
- AgentProfiles/CollectionsTab.tsx — full tab variant