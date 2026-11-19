---
name: audit-consistency
description: "Run the Cogitate system consistency audit — every dangling reference (tool links, usage logs, sessions, grants, collections, workflow configs naming missing agents). Use when asked to check the system's health/integrity, before or after agent deletions, or to rationalize the system state."
version: 1.1.0
author: Cogitate Team
tags: [cogitate, audit, consistency, health, system]
---

# Audit System Consistency

Report the system's ACTUAL consistency state, never a guess.

## The check — the typed HTTP API

Fetch `GET http://localhost:8000/api/v1/system/audit/consistency`
(your HTTP/web tools — the typed API is the VERIFIED path; never
read the source or run the handler directly).

Expect the JSON audit report:
- `status`: `clean` or `inconsistent`
- `total_findings`: the count
- `checks`: the per-check breakdown
  - **agent_references** — tool links / usage logs / collection
    items / chat sessions pointing at agent ids that no longer
    exist (legacy residue from pre-BOM deletes)
  - **grant_references** — tool grants for missing agents (the
    `external` pseudo-id is the Exa surface's legit grant — NOT
    a finding)
  - **collection_items** — collectives holding deleted tools or
    workflows
  - **orphaned_collections** — empty collectives
  - **workflow_name_references** — workflow configs naming agents
    that no longer exist

## Interpretation

- `status: clean` → the reference graph is consistent (verified).
- `status: inconsistent` + `total_findings: N` → the system
  carries dangling references. Report the per-check breakdown —
  the USER decides whether to repair; the audit itself does NOT
  repair (repair is a separate explicit action).

## When to use

- Asked about system health / integrity / consistency.
- Before or after retiring an agent (delete-agent) — the audit
  shows whether the delete left residue.
- **AFTER you make a change** (delete-agent, restore-agent,
  set-trigger-schedule, restart-backend): run the audit to verify
  the change left no residue — the read-back is your proof.
- As a routine system-up sanity check.

## The full workflow run (2026-08-20)

The standalone API call (above) is the quick check. The FULL
**system-audit workflow** adds the structural verification — it
RE-RUNS the audit + compares + delivers the report product:

`POST http://localhost:8000/api/v1/workflows/execute`
with `{"template_id": "system-audit"}` — the report lands in
your workspace `inbox/` (`.exa-workspace/inbox/`).

Use the workflow run when you want the VERIFIED report + the
delivery; use the standalone API call for a fast read.

## Common pitfalls

- Confusing the audit with a repair — it REPORTS; it never
  deletes or mutates.
- Flagging the `external` grant pseudo-id — it is legitimate.
- Claiming the system is consistent without running the audit —
  the dangling rows are invisible from the surface.
- Reading the source / invoking the handler directly instead of
  the typed API (2026-08-19 lesson: Exa did exactly this — the
  HTTP endpoint is the VERIFIED path).
