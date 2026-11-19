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
| Overview | Live "doctor" checklist: Local LLM / API keys / Default model / Starter agent, ✅⚠️⏳ statuses from existing endpoints; click to jump |
| Local LLM | Ollama check (test endpoint on provider 1) + install/pull/serve commands |
| API Keys | Reuses `ProviderKeyManager` (writes .env — the secrets store) |
| Default Model | Link to Provider Dashboard picker |
| Agent | Link to Agent Profiles + Chat |

## Help

Per-tab HelpButton contexts: `setup-overview`, `setup-local`,
`setup-keys`, `setup-model`, `setup-agent` → wiki/help/setup-*.md
(5 files). HelpModal machinery reused.

## Notes

- Keys decision: .env is THE secrets store (2026-08-04); the Keys
  tab here is the same component as the dashboard's.
- Tested: `src/pages/__tests__/SetupPage.test.tsx` (5 tests).
