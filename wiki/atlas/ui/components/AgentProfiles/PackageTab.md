---
title: PackageTab
type: atlas-component
path: frontend/src/components/AgentProfiles/PackageTab.tsx
confidence: high
updated: 2026-08-25
tags: [type/component, domain/agent-profiles]
---

# PackageTab

The agent profile's PACKAGE tab (the package's UI half,
2026-08-25 — the proposal: local/agent-package/03-ui-half-proposal.md).

## The purpose

The agent's package (the blueprint) is invisible in the UI without
this tab: it shows the provenance + the contents + the adopt flow.

## The structure

- **The Current package card** — the provenance (the package_id's
  lookup; the honest 'No package — not provisioned from a
  blueprint' fallback).
- **The packages table** — the collections-style rows (Name /
  Toolkit (the RESOLVED collection names — the UUIDs are
  unreadable!) / Skills count / LLM spec summary); the row click
  opens the detail modal; the 'current' badge on the agent's
  package.
- **The detail modal** — the full contents (kit + skillset +
  llm_spec) + the Adopt this package + the Close. THE SCHEDULER
  MODAL PATTERN (no modal-box — the 48px rule!).
- **The confirm modal** — the Now vs After (the current kit/skills
  vs the package's) + the explicit Adopt/Cancel — the
  destructive-transform discipline.

## The data

- `agentPackagesService.list()` — the packages.
- `collectionsService.getCollection()` — the kit's name.
- `agentPackagesService.adopt(agentId, packageId)` — the
  POST /agents/{id}/adopt-package (the agent owns its copies; the
  package's the blueprint).
- The success refreshes via `profileService.loadFromBackend()`.

## The modals' pattern

THE PROCEDURE — wiki/dev-notes/frontend/modal-dialogs.md (the
copy-paste template; the 4th/5th recurrence's lesson — never
modal-box, the width var + p-6, the measure-verify).
