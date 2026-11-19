---
title: ProviderHealthModal
type: atlas-component
path: frontend/src/components/features/providers/ProviderHealthModal.tsx
confidence: high
updated: 2026-09-29
tags: [type/component, domain/atlas-ui]
---
# ProviderHealthModal

**Path**: `frontend/src/components/features/providers/ProviderHealthModal.tsx`

## Purpose

One provider's **live check**, reported in the house modal shell. The check runs when the modal
opens and again on **Check again**; the panel is a report, so a provider the check cannot reach says
so in its own words rather than throwing.

The call is `POST /api/v1/providers/config/{id}/test` through
[[atlas/ui/services/domains/providers/providerConfigService|providerConfigService]] — the provider's
own `base_url` and key probing its `/models` endpoint. The component calls the **service**, not
`useProviderConfig`, so opening a health modal does not mount a second providers fetch.

Presented with the sibling local-providers page's vocabulary (`frontend/src/pages/LocalProviders.tsx`
shows the same call on its cards): a status badge, the message, latency in ms, the model count.
`STATUS_LABEL` spells the endpoint's statuses (`connected` · `not_configured` · `unreachable` ·
`error` · `unknown_provider`) and prints anything else as it arrives; the badge colours are success
for connected, error for `unreachable`/`error`, warning otherwise. Latency and model count render
only when the response carries them. A failure of the request itself (not the provider) shows as an
error line.

## Props

```typescript
interface ProviderHealthModalProps {
  provider: ProviderConfig      // the provider to check; its own base_url is what gets probed
  onClose: () => void
}
```

Internal state is the check's own: `result`, `error`, `checking` — the page holds only which provider
is being looked at.

## Used by

[[atlas/ui/pages/ProviderDashboard|Provider Dashboard]] — the **Health** action on an Overview
provider card, replacing the page's earlier toast-only test and its separate Health tab (whose
component was deleted; see
[[atlas/ui/components/features/providers/ProviderHealthDashboard|ProviderHealthDashboard (REMOVED)]]).

## Related

- [[atlas/ui/components/features/providers/ProviderModal|ProviderModal]] — the shell it renders in
  (`md`, 600px).
- `backend/app/api/v1/providers/config_router.py` — `POST /{provider_id}/test`, the endpoint.
