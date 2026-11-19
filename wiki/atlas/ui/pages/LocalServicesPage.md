---
title: LocalServicesPage
type: atlas-page
path: frontend/src/pages/LocalServicesPage.tsx
confidence: high
updated: 2026-10-07
tags: [type/page, domain/atlas-ui]
---

# LocalServicesPage

**Component**: `frontend/src/pages/LocalServicesPage.tsx`
**Route**: `/local-services` (icon `server`, breadcrumb `Local Services`) — registered in
`frontend/src/config/routes.ts`; the sidebar's **Configuration** section in `App.tsx` (nav label
"Local Services").

## Purpose

The capability-driven surface for LOCAL services, in the model the Speech page set: a section per
concern, each answering its own question rather than pooling every local engine into one panel.

1. **Local service providers** — reachability and a test, per provider.
2. **Session titles** — the one capability this page owns: which model names sessions, whether it runs
   automatically, and a test that runs the rename end to end.

**Availability doctrine:** an unavailable local service shows its state, never a silent empty, and its
test surfaces the error.

## What counts as "local"

`isLocalProvider(p)` matches the provider's **`base_url`** against `localhost` / `127.0.0.1` /
`0.0.0.0`. The abstraction is keyed on where the service lives, **not** on `provider_type`: the
`llama` row is `provider_type: 'openai'` and local.

## Section 1 — local service providers

One row per local provider: the display name, the `base_url` in mono, the test read-out, and **Test**.
The test is a four-state machine per provider (`idle` → `testing` → `ok` / `error`):

- `idle` reads `Unknown — test to check reachability` (an untested service is never painted healthy),
- `ok` reads `Reachable ✓` with the response's message,
- `error` reads `Unavailable —` with the message or the thrown error, so the reason is on the row.

## Section 2 — session titles

The title preference is stored in `settings.general` and read back here:

- **Title Generation Model** — `agent` (the agent's own model), `backend_default` (no override: the
  title capability answers), or `custom` (a model string, the input appearing only for that choice).
  The helper text states the rule: an override picks who answers FIRST for that rename; with none, the
  capability answers.
- **Auto-title** — off means the user renames deliberately.

**The resolved-state panel reads the CAPABILITY first, then the service.** `GET
/api/v1/chat/title-service/status` answers both, and the capability's line
(`default_provider.name/model`) is rendered first because it always exists, while the service's own
pair (`resolved_provider`, `resolved_model`, `reasoning_effort`) stays null until the lazy service
loads its config. When the capability is not ready, its `default_provider_issues` are printed beside a
`Not ready` warning rather than left as an empty pair.

**Save** writes `settings.general` through the settings store and confirms with a toast; **Test
rename** POSTs a fixed sentence to `/api/v1/chat/generate-title` and reports the title it returned —
the end-to-end check of the capability, not a reachability probe.

The chains behind the title capability (its primary and backups) live on
[[atlas/ui/pages/ProviderCapabilities|ProviderCapabilities]], which this page links to rather than
duplicating.

## Data flow

| call | endpoint | notes |
|---|---|---|
| `providerConfigService.getProviders(true)` | `GET /api/v1/providers/config?include_inactive=true` | filtered to the local ones here |
| `providerConfigService.testProvider(id)` | `POST /api/v1/providers/config/{id}/test` | the per-provider test |
| `apiClient.get` | `GET /api/v1/chat/title-service/status` | the capability's answer + the service's own pair |
| `apiClient.post` | `POST /api/v1/chat/generate-title` | the rename test |
| `useSettingsStore().updateSettings` | `PUT` settings | the preference + the auto-title toggle |

## State management

Local `useState` for `providers`, the per-provider `tests` map, `titleStatus`, `testRename` and
`saving`; the title preferences are form state over `useSettingsStore`'s `settings.general` (so a save
is an explicit action, not every keystroke). Failures go to the notification store.

## Related pages

- [[atlas/ui/pages/ProviderCapabilities|ProviderCapabilities]] — the capability chains this page defers to
- [[atlas/ui/pages/Speech|Speech]] — the section model this page follows
- [[atlas/ui/pages/LocalProviders|LocalProviders]] — the daemon-class roof and its occupancy
- [[atlas/ui/pages/Settings|Settings]] — the settings store the preferences land in
- [[atlas/api/routers/chat|Chat API]] — the title-service endpoints
- [[atlas/api/routers/providers|Providers API]]
