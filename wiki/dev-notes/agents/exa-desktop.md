---
title: The Exa Desktop (Workspace + Delivery)
type: atlas-devnote
category: agents
order: 3
confidence: high
updated: 2026-08-21
tags: [type/dev-notes, domain/agents, feature/external-agent, feature/workspace]
---

# The Exa Desktop (the workspace + the delivery)

The home/workspace split (2026-08-20 — the OpenClaw pattern:
HOME = identity, WORKSPACE_DIR = work area):

- **.hermes/** — Exa's IDENTITY home (Hermes state: memory,
  config, skills, sessions). The brain.
- **.exa-workspace/** — Exa's DESK. Where the system agent puts
  reports, receives workflow products, and stages files. The
  work area.

The desk is NOT the brain: products land on the desk; identity
lives in the home.

## The layout

```
.exa-workspace/          ← the desk (gitignored, per-install)
  inbox/                 ← workflow products land here (the exa-inbox delivery)
  reports/               ← where Exa writes its reports
  drafts/                ← work-in-progress
  scratch/               ← ephemeral
```

`Paths.exa_workspace` (the locator — the ONE-resolver rule).

## The exa-inbox delivery mode

`AgentDistributor` gains the exa-inbox mode: `recipient_agent` in
(exa, Exa, external) → the product FILE-ITS into
`.exa-workspace/inbox/` — NO registry resolution (Exa is not a
DB row; the white pages stay strict). This is the answer to
"how does the product reach Exa?":

- **Option A (this)** — file-it into the workspace: buildable,
  clean, no fake DB row
- Option B (WS bridge) — rejected: a workflow can't hold a live
  connection
- Option C (synthetic registry entry) — rejected: contaminates
  the strict white pages

**Live-verified (2026-08-20)**: the system-check product landed
in the inbox (`system-check-2026-08-20.md`); the startup hook's
run landed `system-check-2026-08-21.md` — the boot state reaches
the system agent automatically.

## The skill

`cogitate-workspace` (skills/exa/) teaches Exa its desk: the
inbox is for ARRIVALS (read the newest), reports/ is the OUTPUT
channel (never write INTO the inbox), the workspace is per-install
+ gitignored (not source).

## The user account (BACK BURNER — recorded, not built)

A sandboxed `exa` OS user only contains Exa if the WHOLE stack
runs under it (the ACP subprocess inherits the backend's OS
identity) — the systemd / service-account deployment story for
the industrial fork. The workspace folder is the portable part:
whatever user runs it, the layout is the same.
