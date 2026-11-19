---
title: ProviderHealthDashboard (REMOVED)
type: atlas-component
path: frontend/src/components/features/providers/ProviderHealthDashboard.tsx (DELETED 2026-09-29)
confidence: high
updated: 2026-09-29
tags: [type/component, domain/atlas-ui]
---
# ProviderHealthDashboard (REMOVED)

**Path**: `frontend/src/components/features/providers/ProviderHealthDashboard.tsx` — **DELETED 2026-09-29**
**Type**: component (presentational health-card grid — removed)

## Purpose

It rendered one health card per provider with a status dot, a status badge, latency, success rate,
rate-limit quota and the last error. It was **presentational and controlled**: it fetched nothing and
took `providers`, an optional `healthData`, `onRefresh` and `loading` as props, so the parent owned
every value on screen.

## What happened

- **Removed 2026-09-29** (the cloud-providers arc's tab restructure). The component's own
  `healthData` prop was never passed by the page — the page rendered it with `providers`, `loading`
  and `onRefresh` only — so `getHealthData()` returned `undefined` on every row and each card read
  `unknown` with `Latency: N/A` and `Success Rate: N/A`: a grid of identical empty cards holding a
  tab of the page.
- The live check it delegated to (`POST /api/v1/providers/config/{id}/test`, through
  `providerConfigService.testProvider`) is now reported by
  [[atlas/ui/components/features/providers/ProviderHealthModal|ProviderHealthModal]], opened from the
  **Health** action on an Overview provider card — one provider at a time, on demand. The tab, the
  "Refresh All" sweep and the `providers-health` help page went with it.
- The health-card *vocabulary* survives where the check is shown: status badge, latency in ms, model
  count. The sibling local-providers page (`frontend/src/pages/LocalProviders.tsx`) presents the same
  call on its own cards.

## Related

- [[atlas/ui/pages/ProviderDashboard|Provider Dashboard]] — the page it lived on; its tab set no
  longer includes Health.
- [[atlas/ui/components/features/providers/ProviderHealthModal|ProviderHealthModal]] — where the
  check reports now.
- [[atlas/ui/services/domains/providers/providerConfigService|providerConfigService]] — the service
  behind the check.
