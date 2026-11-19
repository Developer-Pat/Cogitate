---
title: ProviderCapabilities
type: atlas-page
path: frontend/src/pages/ProviderCapabilities.tsx
confidence: high
updated: 2026-10-09
tags: [type/page, domain/atlas-ui]
---

# ProviderCapabilities

**Component**: `frontend/src/pages/ProviderCapabilities.tsx`
**Route**: `/providers/capabilities` (title "Capabilities", icon `server`, breadcrumb "Capabilities") —
registered in `frontend/src/config/routes.ts`; the sidebar's **Configuration** section in `App.tsx`
(nav label "Capabilities", listed after Local Providers).
**Last Updated**: 2026-10-09.

## Purpose

One page answers the service-capability arc's exit criterion — **which service does each capability
use, what are its backups, and WHY that answer** — and it is also each capability's EDIT path. The
read-out is served by the ONE resolver (`GET /api/v1/providers/capabilities`), not by describing the
default provider row.

The page's own blurb states what a capability is, that its chain is tried in order, and the two
reasons to configure one (prefer a local engine, or have a fallback). The long form for end users is
`wiki/help/providers-capabilities.md`, opened by the banner's `HelpButton`
(`context="providers-capabilities"`).

## ⚠️ The two chains — the contract this page must not collapse

Both lists are shown **on purpose**, and they answer different questions:

| list | field | what it is |
|---|---|---|
| the **RESOLUTION** | `primary` + `backups` | what ANSWERS. Can come from an agent's own declaration, expands a class candidate into every row it matches, and filters out rows switched off |
| the **STORED** chain | `configured` | what this capability's own rows SAY. What the EDITOR reads and writes |

The read-out is the **sessionless** view (no agent on the ladder). Sending the resolution back as a
write would drop a disabled row and rewrite expanded rows as if they were the ones stored — so the
editor's payload is built from `configured` (`draftFromStored`, in
[[atlas/ui/components/features/providers/CapabilityEditModal|CapabilityEditModal]]), never from
`primary`/`backups`.

## Key features

- **A card per capability** — the label, its kind badge (`llm` / `speech` / `process` / `embedding`), the rung that
  answered, the `key` (mono, right-aligned, carrying `aria-label="Capability key: …"`), and **Edit**.
- **The chain rows** — each attempt shows its RESOLVED role (`primary`, `backup #n`) beside its stored
  ordinal when the two differ, the service (`provider/model`, or a named engine), the availability
  badge, and when that was checked. The rows stay on the card while the editor is up, so dismissing
  the editor returns to the list as it was.
- **The agent picker** ("Resolve for") — re-asks the read-out through the ladder's AGENT rung for one
  agent. The backend applies it only to the capabilities a live consumer passes an agent for, so no
  card shows a chain the capability would not use.
- **The editor** — one capability per modal, opened by the card's **Edit** and rendered by
  [[atlas/ui/components/features/providers/CapabilityEditModal|CapabilityEditModal]] in the house
  shell ([[atlas/ui/components/features/providers/ProviderModal|ProviderModal]], `xl`). The three ways
  an attempt can name its service (`provider_id`, `require_location` as "Prefer a class",
  `service_name` as a named engine/process), plus a **model picker** offering the curated list for that
  provider (free text when it has none), `thinking`, reorder (`Up`/`Down`), remove, add, and the
  capability's own **Off** switch.

## Data flow

| call | endpoint | notes |
|---|---|---|
| `capabilitiesService.getCapabilities(agentId?)` | `GET /api/v1/providers/capabilities[?agent_id=N]` | the whole read-out: `{capabilities, kinds, total}` |
| `capabilitiesService.updateCapability(key, update)` | `PUT /api/v1/providers/capabilities/{key}` | **a REPLACE, not a patch**: `candidates` is required and a candidate's position IS its ordinal. Answers the updated `CapabilityReadout` |
| `providerConfigService.getProviders(true)` | the provider list | the editor's picker options — its OWN load, so a provider failure does not blank the read-out |
| `agentRosterService.listAgents()` | the roster | the agent picker's options — its own load too |
| `fetchCuratedModels()` | `GET /api/v1/curated-models` | the editor's **model picker** options, keyed by provider NAME (an attempt names its provider by row id) — its own load, and a failure there only drops the model field back to free text ([[atlas/ui/services/domains/providers/curatedModelsService|curatedModelsService]]) |

Four loads, four error states, deliberately independent. A **save** updates the card in place from
the response and re-reads the whole read-out **when an agent is in view**, because the response
carries the SESSIONLESS resolution and would otherwise disagree with the picker.

## Availability (group 5)

Each candidate carries the ONE availability read's last answer: `availability_state`
(`available` · `down-by-occupancy` · `down` · `unconfigured` · `unknown`), `available`, `
availability_reason`, `checked_at`.

The rendering rule: `available === true` → a `badge-success` **up**; `available === false` → a
`badge-error` with the state's own words (keyed by `AVAILABILITY_LABELS`: down-by-occupancy reads
"in use elsewhere" — a CHOICE, not an incident); **`null`/`unknown` draws NOTHING**, so a service
nobody probed is never painted as broken. `checked_at` renders as a local time beside the badge, and
the full value rides in the badge's `aria-label`.

**The disabled-control rule, as the editor implements it:** the end-row `Up`/`Down` are disabled, and a
disabled button fires no hover — so `MoveButton` (in
[[atlas/ui/components/features/providers/CapabilityEditModal|CapabilityEditModal]]) moves the tooltip
onto a wrapper for exactly that state, where it says WHY ("Already first" / "Already last") rather
than repeating an action that cannot be taken. Enabled, the tip stays on the button and no wrapper is
rendered.

## State management

Local `useState` only — no store. `readout`, `error`, `loading`; `providers` + `providersError`;
`agents` + `agentsError`; `selectedAgentId`; and per card, whether its editor is up. The editor's
draft (`DraftRow[]`) lives inside
[[atlas/ui/components/features/providers/CapabilityEditModal|CapabilityEditModal]] and is seeded from
`configured`.

## Related pages

- [[atlas/ui/components/features/providers/CapabilityEditModal|CapabilityEditModal]] — the editor
- [[atlas/ui/pages/ProviderDashboard|ProviderDashboard]] — the providers themselves
- [[atlas/ui/pages/ProviderModelsBrowser|ProviderModelsBrowser]] — the model catalogue
- [[atlas/ui/pages/Speech|Speech]] — the speech surfaces that link here for the engine
- [[atlas/api/routers/providers|Providers API]] — the sub-area's endpoints
