---
title: Provider Dashboard
type: atlas-page
path: frontend/src/pages/ProviderDashboard.tsx
confidence: high
updated: 2026-09-29
tags: [type/page, domain/atlas-ui]
---
# Provider Dashboard

**Component**: `frontend/src/pages/ProviderDashboard.tsx`
**Route**: `/providers` (the cloud roof — the local daemons are `frontend/src/pages/LocalProviders.tsx` at `/providers/local`)
**Last Updated**: 2026-09-29

## Purpose

Manages the **cloud-class** providers: configure them, check one on demand, see their usage, manage
the human-owned curated model list, set the default provider, and browse a provider's model
catalogue.

## The tabs — five, in the URL

**Curated (the one that opens) · Overview · Default · Usage · Keys.**

The active tab lives in the URL (`?tab=usage`), so a reload, a shared link or a Back/Forward move
lands on the same tab; an absent or unrecognised value falls back to Curated. Switches use `replace`,
so Back leaves the page rather than walking the tabs visited. `TAB_KEYS` is the union the validator
reads, and `HELP_CONTEXT` is a `Record<ProviderTab, string>` — a tab added or removed without a help
case is a **type error**, where a chained ternary used to fall through to its last branch.

| Tab | Renders | Help context |
|---|---|---|
| Curated | `CuratedModelsManager` | `providers-curated` |
| Overview | the provider cards and their actions | `providers-overview` |
| Usage | `UsageDashboard` | `providers-usage` |

**Above the tabs sit the setup TILES** — [[atlas/ui/components/features/providers/SetupTiles|SetupTiles]]
renders the readiness items (provider + key, chat model, agents, and the optional runtime) as cards
whose `href` is the item's own. The two setup ACTS are not tabs on this page: the provider keys and
the default chat model live on the Setup page (`/setup?tab=keys`, `/setup?tab=model`), one
implementation each, and the readiness verdict's doors point there.

The header's `HelpButton` opens the active tab's context from `wiki/help/`. The header also carries the
cross-link into the capability surface — a line under the subtitle reading *"Which service each
capability uses, and its fallbacks — see Capabilities"*, pointing at `/providers/capabilities` (the
cloud and local roofs and the Local Services card each carry one).

## An Overview provider card

Name and type, an Active / API-Key badge pair, the base URL, and its actions:

- **Edit** — `ProviderConfigModal` (display name, base URL, API key, active, priority).
- **Health** — opens [[atlas/ui/components/features/providers/ProviderHealthModal|ProviderHealthModal]],
  which runs the live check on open.
- **Models** — opens the Model Browser panel.
- **Sync Settings** — expands `ModelSyncScheduler` for that provider.

The cards list only `providerLocationOf(p) === 'cloud'`, so a local daemon cannot appear here.

## The modal shell

Both modals on this page render through
[[atlas/ui/components/features/providers/ProviderModal|ProviderModal]]: a native
`<dialog className="modal">` opened with `showModal()`, holding the house PLAIN panel
(`--dialog-width-*` + `p-6`) and **never** `modal-box`. Native supplies Escape, focus containment,
focus return and the top layer; the panel takes the caret on open; `dialog.modal::backdrop` in
`styles/index.css` supplies the house dim. The Model Browser takes the `xl` token (1000px), the health
modal the `md` token (600px).

## Model browser

Rendered inside `ProviderModal` (`xl`): `ModelFilters` (search, sort, free-only, capabilities) over
`ModelTable` (paginated). Selecting a model writes it to `sessionStorage.selectedModel` and closes
the panel.

## Components used

| Component | Path | Purpose |
|---|---|---|
| PageContainer | `components/ui/PageContainer.tsx` | Layout wrapper |
| PageBanner | `components/ui/PageBanner.tsx` | Error banner |
| Tooltip | `components/ui/Tooltip.tsx` | Tab and action tooltips |
| HelpButton | `components/help/HelpButton.tsx` | Header help, per-tab context |
| ProviderConfigModal | `components/features/providers/ProviderConfigModal.tsx` | Provider CRUD |
| ProviderModal | `components/features/providers/ProviderModal.tsx` | The modal shell |
| ProviderHealthModal | `components/features/providers/ProviderHealthModal.tsx` | The live health report |
| ModelSyncScheduler | `components/features/providers/ModelSyncScheduler.tsx` | Sync schedule per provider |
| DefaultProviderConfig | `components/features/providers/DefaultProviderConfig.tsx` | Default provider + model |
| CuratedModelsManager | `components/features/providers/CuratedModelsManager.tsx` | The curated list |
| UsageDashboard | `components/features/providers/UsageDashboard.tsx` | Usage stats |
| ProviderKeyManager | `components/features/providers/ProviderKeyManager.tsx` | API key sources |
| ModelFilters / ModelTable | `components/features/providers/ModelBrowser/` | The model browser panel |

## Hooks used

| Hook | Path | Purpose |
|---|---|---|
| useProviderConfig | `hooks/useProviderConfig.ts` | Provider list + CRUD |
| useDefaultProvider | `hooks/useDefaultProvider.ts` | Default provider state |
| useUsage | `hooks/useUsage.ts` | Usage metrics |
| useSyncSchedule | `hooks/useSyncSchedule.ts` | Sync schedule |
| usePageTitle | `hooks/usePageTitle.ts` | Document title |

## Data flow

- Providers: `GET /api/v1/providers/config` (via `providerConfigService`), filtered to the cloud class
- Health: `POST /api/v1/providers/config/{id}/test` — from the health modal's own call
- Default: `GET/PUT /api/v1/providers/config/default`
- Usage: `GET /api/v1/providers/usage`
- Sync: `GET/PUT /api/v1/providers/config/{id}/sync-schedule`
- Models: `modelBrowserService` over `GET /api/v1/providers/models`

## State

Component state holds the selected provider, the config modal's mode, the modal-browser filters and
page, the default provider's pending selection, and which surface is open (`healthProvider`). The
active tab is **not** state — it is the URL. Toasts for CRUD outcomes come from `notificationStore`.

## Related pages

- `frontend/src/pages/LocalProviders.tsx` — the local counterpart, which presents the same
  `POST /{id}/test` check on its cards (no modal).
- [[atlas/ui/pages/ProviderModelsBrowser|ProviderModelsBrowser]] — a standalone model browser.
