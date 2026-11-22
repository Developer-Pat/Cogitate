---
title: SetupPage
type: atlas-component
path: frontend/src/pages/SetupPage.tsx
confidence: high
updated: 2026-08-04
tags: [type/component, domain/atlas-ui]
---

# SetupPage

First-run setup page (tabbed, not a wizard). Design locked in
`local/roadmaps/setup-page-proposal.md` (v2, 2026-08-04).

## Location & integration

- Route `/setup` (routes.ts) + sidebar link (App.tsx, Utilities)
- First-run auto-redirect: `FirstRunRedirect` component (App.tsx,
  inside Router) — redirects to /setup when zero working keys AND
  zero chat history; localStorage flag prevents re-fire; never fires
  once configured

## Tabs

| Tab | Content |
|---|---|
| Overview | The readiness verdict: `GET /api/v1/setup/readiness` (one call, measured in `domain/providers/readiness.py`) → four items — provider+key, chat model, agents, Exa's runtime (optional, never counted). Each item links to where it is fixed; a failed call says it cannot say |
| Local LLM | Instructions only (install / pull / serve) — the old test-endpoint probe on provider id 1 is gone |
| API Keys | Reuses `ProviderKeyManager` (writes .env — the secrets store) |
| Default Model | The ACT: [[atlas/ui/components/features/setup/SetupDefaultModel|SetupDefaultModel]] — provider + model, pending until Save |
| Agent | Link to Agent Profiles + Chat |

## Help

Per-tab HelpButton contexts: `setup-overview`, `setup-local`,
`setup-keys`, `setup-model`, `setup-agent` → wiki/help/setup-*.md
(5 files). HelpModal machinery reused.

## Notes

- Keys decision: .env is THE secrets store (2026-08-04); the Keys
  tab here reuses `ProviderKeyManager`, and the cloud-providers page no
  longer hosts a Keys or Default tab of its own (ruled 2026-11-22, option 2:
  a setup act lives on the Setup page).
- THE VERDICT MOVED TO THE BACKEND (2026-11-20): the page computes
  nothing of its own (no POST to provider id 1, no `agentReady`).
- Tested: `src/pages/__tests__/SetupPage.test.tsx` (7 tests).
