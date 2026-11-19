---
title: NavigationCards
type: atlas-component
path: frontend/src/components/dashboard/NavigationCards.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# NavigationCards

**Path**: `frontend/src/components/dashboard/NavigationCards.tsx`
**Last Updated**: 2026-08-01

## Purpose
Dashboard 'Quick Navigation' section — a static grid of 4 nav cards (Agent Chat, Sessions, Logs, Wiki) linking to core pages.

## Props Interface
None — static card config, no props.

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| NavigationCard | Component (local) | Renders each card |

## Usage Example
```tsx
<NavigationCards />  // in Dashboard page
```

## State Used
None — static.

## Related Components
- dashboard/NavigationCard.tsx — the card primitive
- dashboard/QuickStats.tsx — sibling stats section