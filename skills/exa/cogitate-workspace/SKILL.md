---
name: cogitate-workspace
description: "Your workspace — the Cogitate-side DESK where you receive workflow products (inbox/), write reports (reports/), and stage work (drafts/, scratch/). Use when asked about your files, where products land, or where to write something for the system."
version: 1.0.0
author: Cogitate Team
tags: [cogitate, workspace, desktop, inbox, exa]
---

# Your Workspace (the Desktop)

You have a workspace in the Cogitate project — your DESK, distinct
from your identity home (`.hermes/` — Hermes state). The split:
`.hermes/` is your brain; `.exa-workspace/` is your desk.

## The layout

- `inbox/` — workflow products LAND here (the `exa-inbox`
  delivery mode files them: the system-check report, monitor
  digests addressed to you, etc.). Check it for new arrivals.
- `reports/` — where you WRITE reports you produce (the audit
  summaries, analysis, findings you're asked to make).
- `drafts/` — work-in-progress files you're still assembling.
- `scratch/` — ephemeral files; safe to discard.

## The conventions

- Products arrive in `inbox/` named `<type>-<date>.md` — read the
  newest one when you're asked what arrived.
- When you write a report, put it in `reports/` (a clear
  filename), not `inbox/` — the inbox is for ARRIVALS.
- The workspace is per-install + gitignored — it is NOT source
  code; never treat it as part of the repo.

## When to use

- Asked "what's in your inbox?" / "did anything arrive?"
- After a workflow runs (the system-audit, the monitors) — check
  `inbox/` for the delivered product.
- Asked to write a report or findings — use `reports/`.

## Common pitfalls

- Writing products INTO `inbox/` — that's the arrival channel,
  not your output channel.
- Confusing the workspace with `.hermes/` — the home is identity
  (memory, config, skills); the workspace is work product.
