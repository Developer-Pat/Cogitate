---
title: Exa Capabilities
type: devnote
path: wiki/dev-notes/external-agent/capabilities.md
confidence: high
updated: 2026-08-19
tags: [type/dev-notes, domain/external-agent]
---

# Exa Capabilities

What Exa can do, what it cannot, and how we know — the capability
inventory from the QA probes (2026-08-17). Exa is the external
agent: a Hermes ACP subprocess (`hermes acp`) driven through the
the Exa Agent page or the AcpClient. **Tested on Hermes v0.18.2 with
`deepseek-v4-flash` (deepseek provider).**

## The proven surface (probes 1–4)

| Capability | Probe | Result |
|---|---|---|
| Read live APIs + compose + place + verify | 1 — agents report | PASSED (read the router source for the endpoint shape; composed a roster table; POSTed to /external-agent/report; verified the file on disk) |
| Read the full registry (after the pagination fix) | 2 — agents report re-run | PASSED (all 13 agents; verified the count; added a provider breakdown + deep-agents analysis) |
| Workflow + lifecycle READ | 3 — workflow/lifecycle survey | PASSED (33 templates categorized; the coupling-by-id insight; 13 agents + health) |
| WRITE ops + clean shutdown | 4 — lifecycle round-trip | PASSED (provisioned → verified → archived → attempted restore/re-archive → cleaned up flawlessly; no residue) |
| Failure-mode analysis | 4 | PASSED (found + explained the folder-only archive bug; recommended the unification fix) |

## The failure-mode battery (2026-08-17) — 3/3 fail loudly

| Failure mode | Verdict | What it looked like |
|---|---|---|
| Unknown recipient (the AgentDistributor) | PASS | Loud dead-letter: "No agent named 'X' in the pool. Address by an existing agent name" — STRICT resolution |
| Missing skill (Exa asked to use one that doesn't exist) | PASS | Explicit: "The skill X does [not exist]" — not invented |
| Connection drop (ACP subprocess killed mid-turn) | PASS | TimeoutError surfaced — no hang, no zombie |

The delivery surface + Exa fail loudly with actionable detail.
One limitation: the AgentDistributor is a SYNC-context delivery
path (its asyncio.run cannot nest inside a running event loop) —
production calls it sync; an async caller hits "asyncio.run()
cannot be called from a running event loop".

## What the probes proved

- **The read → compose → place → verify loop works with EXISTING
  tools** — terminal + python3 -c inside it. No purpose-built
  Exa tools were needed for these tasks.
- **Write operations work**: Exa drove the agent lifecycle API
  end-to-end and returned the system to its prior state.
- **It reads source for contracts**: it found endpoint shapes by
  reading the router code + the OpenAPI schema when the API
  contract was unclear.
- **Cleanup discipline**: probe 4's cleanup was verified — no
  probe agent, no stranded folders, prior state restored.

## Known limits

1. **The search-tool regex contract (2026-08-17)**: Hermes's
   search treats a multi-term pattern like `deleted_at|archived_path`
   as a LITERAL string — 0 matches even when both fields exist.
   Exa concluded "these fields don't exist" from the false
   negative. Single-term searches work. The agent cannot detect
   the false negative. **Mitigation**: structured tools (typed
   data) over raw search; single-term searches when searching.
2. **The confident-false-conclusion risk**: when a tool's
   contract is subtly wrong, Exa's reports can carry wrong
   conclusions with full confidence. Verify critical claims with
   a second source (the pagination trap — fixed at the API).
3. **The pagination trap (FIXED 2026-08-17)**: the agents list
   defaulted to page_size=10; Exa reported "10 agents" with
   `total: 14` in the response. Bounded collections now return
   the full list by default.

## What this means

- Exa is **read/write capable** on the Cogitate surfaces tested —
  the Phase D hypothesis (Exa managing workflows + agent
  lifecycle) is plausible; the write path is proven.
- The lifecycle unification fix (the folder-only archive bug,
  probe 4) is a PRE-SHIP must-fix — the shipped system would
  have un-restorable archives.
- Capabilities are model-dependent: the inventory above is
  `deepseek-v4-flash`-specific. A stronger model may close the
  search/verification gaps; a weaker one may open new ones.

## The Exa-Expertise program's additions (2026-08-18/19)

Exa is now the SYSTEM-DOMAIN agent — the first instance of the
expertise pattern (a domain corpus + skills + scoped tools + the
verification loop, provisioned on boot). What the program added:

- **A Cogitate-local home** (`cogitate/.hermes`, HERMES_HOME) —
  fully isolated from the operator's `~/.hermes`; provisioned +
  verified (Phase 1).
- **The seed skills** (8, in the local home) — the system map, the
  API surface, the monitor ops, set-trigger-schedule,
  report-verified-state, ask-before-destructive (Phase 3).
- **The typed tool family** — set-trigger-schedule (hardened with a
  read-back verify), verify-trigger-config, verify-backend-health,
  search-knowledge (the whole-wiki RAG, 506 files/current),
  graph-query (the topology: 690 nodes/2313 edges), restart-backend
  (KEYED — the fix-mode grant gates it; the handler verifies after
  the restart) (Phases 2/4/5).
- **The verification loop** — every verified op records to
  verification_store.db: the verified-facts channel + the track
  record (the Exa restart is a row: claimed success, verified
  broken, outcome mismatched) (Phase 6).
- **The honest spine** — after each run: "Exa claimed:
  X; VERIFIED (read-back): Y" — the DB truth below the claim.

## The reframe (2026-08-19)

The repurpose is the PATTERN, not the tools: Exa holds SYSTEM
expertise; other agents get OTHER domains' expertise (the tool
model translates; the exact tools do not). The system-manager
agent may be a casualty — Exa is the system agent.

## The probe harness (2026-08-17)

The QA probes are now a PERSISTENT script, not throwaways:

    python3 scripts/core/exa_probe.py            # all probes
    python3 scripts/core/exa_probe.py --probe agents   # one probe

Cases: agents (the read+report probe), survey (the workflow/lifecycle
read), lifecycle (the WRITE round-trip — the unification regression),
battery (the failure modes). Exit 0 = all pass, 1 = any failed. The
lifecycle probe cleans up after itself. Run against a live backend
on :8000.

## Related

- [[dev-notes/external-agent/known-issues|Exa Known Issues]] — the
  reliability issue register (the failure classes + the guards)
- [[dev-notes/known-issues|Known Issues]] — the tool-contract traps
- [[dev-notes/workflows/product-distribution|Workflow Product Distribution]]
- [[atlas/ui/pages/SetupPage|Setup Page]] — the Exa Config surface
