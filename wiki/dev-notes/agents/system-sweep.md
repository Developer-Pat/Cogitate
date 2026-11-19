---
title: The System Sweep
type: atlas-devnote
path: wiki/dev-notes/agents/system-sweep.md
category: dev-notes
order: 3
confidence: high
updated: 2026-08-24
tags: [type/dev-notes, domain/agents, domain/system]
---

# The System Sweep

> The periodic, self-checking integrity sweep. It runs the
> read-back-verified consistency audit + the integrity checks,
> files the report to the Exa inbox, notifies the user, and backs
> the guarded orphan scrub. The design + roadmap: `local/system-sweep/`.

## The schedule

The sweep runs as a ONE-SHOT ~60 seconds after startup (the boot
path only registers the job — startup stays lean). The delay is
configurable via `SYSTEM_SWEEP_DELAY_SECONDS` (300 when tuned for
production).

## The checks (read-only — reported, never repaired)

The sweep runs TWO audits, both read-only:

| Audit | What it finds |
|---|---|
| **ConsistencyAudit** | dangling references — rows pointing at missing agents/tools/workflows; empty collections; workflow configs naming missing agents |
| **IntegrityAudit** | the ghost-history class — FK targets that don't exist (a write to the table fails), orphaned rows (FK target rows missing), INTEGER-PK tables without AUTOINCREMENT (id reuse — harmless once orphans are gone), rotated logs that may need rolling |

**The verify node** re-runs the audit + compares (a stable status
+ finding count proves the report is real, not a hallucination) —
the read-back, recorded in the verification store.

## The delivery + the notification

- The report files to the **Exa inbox** (`.exa-workspace/inbox/
  system-check-<date>.md`) — Exa's channel.
- The sweep publishes **`notify:system-sweep`** on the messaging
  bus — the toaster renders it ("Sweep complete: N findings — the
  report is in the Exa inbox"). The outcome is NEVER silent.

## The orphan scrub (the guarded repair)

The sweep REPORTS; the scrub REPAIRS — a separate, explicit,
guarded surface (`POST /api/v1/system/audit/scrub-orphans`):

1. **Dry-run by default** — returns the would-delete, touches nothing
2. **The typed confirm** — the real run requires the counts to
   match the live truth (a mismatch = "re-propose, don't guess")
3. **A DB backup** before the real run
4. **The outcome reported** — the deleted counts + the re-audit

Scope: the orphan class ONLY (rows whose FK target is gone). The
audit's own report is the proposal; the user approves; Exa can
drive the flow through the endpoint (no tool-surface change — the
HTTP surface is the invocation).

## The API surface

- `GET /api/v1/system/audit/consistency` — the consistency audit
- `POST /api/v1/system/audit/scrub-orphans` — the guarded scrub

## The workflow

The sweep is the `system-audit` workflow kind (audit → verify →
analyze → report), executed by the one-shot schedule; the same
graph runs on demand. The report is a `system-check` WorkflowProduct.

## The checks (2026-08-25)

The integrity run covers six checks:
- **cascade_audit** — the declared FKs' targets exist + the pragma
  watch
- **orphan_scan** — rows pointing at the missing parents
- **id_reuse_watch** — the no-AUTOINCREMENT tables (the deleted ids
  can be reused — watched)
- **log_roll_check** — the rotated log sizes/ages
- **app_zombie_check** — stray backend processes reparented to init
  (the restart-churn class): reports pid/age/command, NEVER
  auto-kills; self-excludes the sweep's own pid + hints to verify
  /health before acting (the flagged pid may be the live server)
- **db_ghost_check** — messages that PREDATE their session (the
  id-reuse ghost class, beyond the orphan scan)

Report-only: the sweep reports, the scrub repairs.
