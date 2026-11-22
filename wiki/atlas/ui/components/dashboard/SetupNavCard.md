---
title: SetupNavCard
type: atlas-component
path: frontend/src/components/dashboard/SetupNavCard.tsx
confidence: high
updated: 2026-11-22
tags: [type/component, domain/atlas-ui]
---

# SetupNavCard

The **Setup** tile in the Dashboard's Quick Navigation: the door to `/setup` plus the one measured
state, so a reader can see whether the install still needs them without opening the page.

## What it shows

- **`ready`** (badge-success) when `remaining` is 0, **`N left`** (badge-warning) otherwise — both
  read from `GET /api/v1/setup/readiness`, the same verdict the card above it renders.
- **Nothing** when the verdict cannot be read: an unmeasured setup is not a passing one, and this
  tile never invents a state.

It is composed as a plain `NavigationCard` with an optional `badge`, so the tile keeps the grid's
shape rather than introducing a second card style on the page.

## Related

- [[atlas/ui/components/dashboard/NavigationCards|NavigationCards]] — the grid it joins.
- [[atlas/ui/components/dashboard/NavigationCard|NavigationCard]] — the shell, now with `badge?`.
