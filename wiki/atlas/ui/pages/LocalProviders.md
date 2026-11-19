---
title: LocalProviders
type: atlas-page
path: frontend/src/pages/LocalProviders.tsx
confidence: high
updated: 2026-10-07
tags: [type/page, domain/atlas-ui]
---

# LocalProviders

**Component**: `frontend/src/pages/LocalProviders.tsx`
**Route**: `/providers/local` (protected, `requiresAuth: true`, icon `server`, breadcrumb `Local
Providers`) — registered in `frontend/src/config/routes.ts`; the sidebar's **Configuration** section in
`App.tsx` (nav label "Local Providers").

## Purpose

The LOCAL-class roof of the provider split. Where the cloud page manages the SaaS catalog (curated
models + browse + keys), this page is about the daemons the user runs: what is installed, whether the
daemon is reachable, and what is loaded right now. **No curated manager and no keys — by class
design**, not by omission.

The page filters the provider list by class itself: `providerLocationOf(p) === 'local'` (memoized,
because the probe effect keys on the array and a fresh array each render would re-probe on every
render).

## Two tabs

| tab | what it answers |
|---|---|
| **Occupancy** (default) | which daemon serves right now, and what each holds |
| **Daemons** | the local provider cards — reachability, the live probe, the settings |

Occupancy leads because the live state is why the page exists; daemon management is the second view.

## Occupancy — the read side

`fetchLocalOccupancy()` → `GET /api/v1/providers/local/occupancy`, answering
`{daemons[], running[], generated_at}`. Each daemon carries `state`:

- `healthy` → a `Serving` badge on the card, with the **loaded models** under the name;
- `down-by-occupancy` → `Swapped out`, a **choice, not an alert** — the title names who holds the GPU;
- `down` → `Stopped`.

The idle line (`No local daemon is running`) renders **only** when nothing runs: when a daemon serves,
its own card carries the state, so no headline duplicates the grid. `Refresh` re-runs the probe;
an occupancy read that fails says so in place rather than showing an empty grid.

## Daemons — the live probe

One card per local provider, auto-probed when the tab opens (the probes are local and fast). Each card
carries its OWN probe result — the single health system, no separate health dashboard:

- the status badge (`Connected` / `Unreachable` / the raw status), the latency in ms, the model count,
  and the message when the probe did not connect;
- **Edit** (the config modal), **Check** (re-run that card's probe), **Models**
  (`/providers/{id}/models`).

`Add Provider` opens `ProviderConfigModal` with `location="local"`, so the modal is limited to the
local types.

## The swap — the write side

**The page ASKS; the system agent RUNS.** `Start` / `Start instead` opens an authorize modal that
states the tradeoff first — starting a daemon while another serves stops that one and unloads what it
has loaded, and with nothing running it simply starts. Confirming calls `queueSwapRequest` (a
`localStorage` entry, `cogitate-swap-request`) and opens `/exa` in a new tab; the request is sent from
the Exa chat, by the user. Nothing is executed from this page.

## Data flow

| call | endpoint | notes |
|---|---|---|
| `useProviderConfig().providers` | `GET /api/v1/providers/config?include_inactive=true` | the class filter is applied here |
| `useProviderConfig().testProvider(id)` | `POST /api/v1/providers/config/{id}/test` | the one health check, per card |
| `useProviderConfig().createProvider/updateProvider` | `POST` / `PUT /api/v1/providers/config[...]` | through the config modal |
| `fetchLocalOccupancy()` | `GET /api/v1/providers/local/occupancy` | the occupancy read |
| `queueSwapRequest(text)` | none — `localStorage` | the handoff to the Exa chat |

## State management

Local `useState` plus the `useProviderConfig` hook: `activeTab`, `occupancy` (+ loading/error),
`probeResults` (per provider id), `probingIds`, the modal's `showConfigModal`/`modalMode`
/`editingProvider`, and `swapTarget`. No store — the swap handoff is the only cross-surface
communication and it goes through storage, not state.

## Related pages

- [[atlas/ui/pages/ProviderCapabilities|ProviderCapabilities]] — which service each capability uses, and its fallbacks
- [[atlas/ui/pages/ProviderModelsBrowser|ProviderModelsBrowser]] — the installed models a card links to
- [[atlas/ui/pages/ProviderDashboard|ProviderDashboard]] — the cloud class of the same split
- [[atlas/ui/pages/ExaChat|ExaChat]] — where a queued swap request is sent
- [[atlas/ui/hooks/useProviderConfig|useProviderConfig]] — the list/create/update/test hook this page drives
- [[atlas/ui/components/features/providers/ProviderConfigModal|ProviderConfigModal]]
- [[atlas/api/routers/providers|Providers API]]
