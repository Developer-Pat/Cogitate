---
title: The Honesty Loop
type: devnote
path: wiki/dev-notes/design/honesty-loop.md
confidence: high
updated: 2026-08-19
tags: [type/dev-notes, domain/design]
---

# The Honesty Loop

The verification loop: how Cogitate makes agent claims *checked*
instead of trusted. The framework insight it embodies:

> **Honesty is a property of the loop, not the model.**
> Trust = f(verification coverage).

An agent's self-report is an *endpoint* — the moment it stops
reasoning and asserts. The loop's claim: the assertion should
never be the final word. Every operation gets a check, the check's
result is what gets recorded, and the record is what the system
(and the user) sees.

## Why this exists

The loop is built on a real incident (2026-08-18): Exa was asked to
restart the backend. It **reported success** — and left the backend
dead with a hung `hermes` process squatting on the port. The
self-report was confident, wrong, and harmless-looking. That is the
failure class the loop exists to bound: **confident false
conclusions from an agent that cannot see its own blind spot.**

The loop does not make the agent honest. It makes the SYSTEM
verify — and the system's verification is what the next decision
(and the user) relies on.

## How it's implemented

The shape: **operate → verify → record → report.**

### 1. The verify tools (operate + verify)

The tool family (backend/app/domain/tools/registry.py) owns the
checks. Every tool that changes state VERIFIES after the write and
returns `verified: true` or a loud failure:

- `set-trigger-schedule` — writes the cron, then **reads it back**
  from the DB; the returned config IS the read-back, not the claim
- `verify-trigger-config` — the DB read-back of a trigger's config
- `verify-backend-health` — hits the health endpoint; reports the
  actual HTTP status
- `restart-backend` — KEYED (the fix-mode grant gates it); restarts
  then health-checks, reporting the ACTUAL state (the incident's
  operation, made safe)

### 2. The verification store (record)

`backend/app/domain/verification/store.py` — a dedicated sidecar DB
(`data/verification_store.db`, the pipeline_traces pattern: WAL,
schema-on-connect, locator-resolved, TTL-pruned). Two tables:

- **`verified_facts`** — written ONLY after a check: `{claim,
  verified_by, verified_when, source, detail}`. The fact enters
  memory only with its verification attached.
- **`track_record`** — per-agent operation outcomes: `{agent,
  operation, claimed, verified, outcome}`. The raw material for
  reliability routing (research, but the data is cheap to record
  now). `reliability(agent)` summarizes it.

The store is fail-safe: a recording failure never breaks the
operation (wrapped, logged).

### 3. The panel surface (report)

The Exa schedule panel shows BOTH sides after every run:

    Exa claimed: schedule set to 0 */6 * * *
    ✔ VERIFIED (read-back): RSS Monitor=0 */6 * * * · ...

The claim above, the DB truth below. The panel directive also
instructs Exa to verify ("Verifying persistence with a fresh
GET") — the loop shapes the agent's behavior, and the system's
read-back is what the user sees regardless.

## The expansion path

A new agent joins the loop by using the verify tools (or its own
domain's verify counterparts); a new tool joins by verifying after
its writes and recording to the store. The Phase-7 pattern: the
tool model (capability/tier/grant + verification) translates to
domain-expert agents — the exact tools don't, the loop does.

## The honest limits

- **Machine-checkable claims only.** The loop verifies what a
  deterministic check can verify (DB reads, health checks, file
  existence). Where no check exists, the loop cannot certify — and
  it says nothing rather than pretending.
- **Semantic verification is the research frontier.** Deciding what
  "verified" means for a claim with no deterministic check is one
  of the framework's open questions — one question among many, not
  the whole of it.
- **The loop doesn't remove the need for judgment.** It changes
  WHERE the trust decision lands: on the verification coverage,
  not on the agent's confidence.

## Related

- [[dev-notes/external-agent/capabilities|Exa Capabilities]] — the
  program that built the loop
- [[dev-notes/configuration/database-topology|Database Topology]] —
  the verification_store.db entry
- [[dev-notes/tools/tools-architecture|Tools Architecture]] — the
  tooling paradigm the verify tools follow
- [[dev-notes/design/research-framework|The Research-Framework
  Identity]] — the factoring hypothesis (the loop is its machinery)
- The study (local, untracked): `local/honesty-verification-study/`
  + `local/exa-expertise-implementation/07-verification-loop.md`
