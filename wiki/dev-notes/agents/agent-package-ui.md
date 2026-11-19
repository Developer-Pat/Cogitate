---
title: The Agent Package's UI
type: dev-note
path: frontend/src/components/AgentProfiles/PackageTab.tsx
created: 2026-08-25
tags: [type/dev-note, domain/agent-packages]
---

# The Agent Package's UI

The package's UI half (the backend's phases 1-5 done 2026-08-24;
the UI's 2026-08-25 — the proposal: local/agent-package/
03-ui-half-proposal.md).

## The flow

The profile's Package tab (the edit view's tabs): the current
package + the packages table + the detail modal (the full
contents!) + the Adopt (the confirm's Now vs After).

## The rules (the hard-won lessons)

- **The kit's NAME, not the UUID** — the collections API resolves
  the id -> the collection's name (the user: "the toolkit id is
  unreadable").
- **The modals: the SCHEDULER PATTERN, never modal-box** — the
  48px rule (the 4th/5th recurrence, 2026-08-25!). The
  copy-paste template: wiki/dev-notes/frontend/modal-dialogs.md.
- **The ownership rule** — the agent owns its copies; the package
  never owns the agent. The adopt copies, the package_id's the
  provenance only.

## The future

The Luminosity Scale's min_driver rides the llm_spec (the
advisory contract's the natural home); the provisioning study's
the consumer.
