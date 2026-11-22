---
title: SetupTiles
type: atlas-component
path: frontend/src/components/features/providers/SetupTiles.tsx
confidence: high
updated: 2026-11-22
tags: [type/component, domain/atlas-ui]
---

# SetupTiles

The setup cards at the top of the cloud-providers page: where the install stands, and the door to
the one page that changes it.

## What it renders

One card per **readiness item** from `GET /api/v1/setup/readiness` — provider + key, chat model,
agents, and the optional external-agent runtime. Each card carries:

- the item's `label` and a state badge (`ready` / `to do` / `waiting` / `optional`),
- the item's own `detail` line (the verdict's sentence, not a paraphrase),
- a link whose `href` **is the item's** — so a card cannot point anywhere the verdict does not.

The badge is the only state on the card: nothing above the grid restates it. `blocked` reads
`waiting` rather than an instruction, because the step it waits on is not the reader's to press yet;
`optional` is never counted in the install's remaining number.

## Why it is not a second verdict

The measurement lives in the backend (`domain/providers/readiness.py`); this component renders the
payload and nothing else. If the read fails the grid renders **nothing** rather than inventing a
state — an unmeasured setup is not a passing one.

## Related

- [[atlas/ui/pages/ProviderDashboard|ProviderDashboard]] — hosts it above the tabs.
- The Dashboard's verdict card renders the same payload (`components/dashboard/ReadinessCard.tsx`).
