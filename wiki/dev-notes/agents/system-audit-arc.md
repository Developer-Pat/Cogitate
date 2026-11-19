---
title: The System Audit & Verification
type: atlas-devnote
path: wiki/dev-notes/agents/system-audit-arc.md
category: dev-notes
order: 2
confidence: high
updated: 2026-08-24
tags: [type/dev-notes, domain/agents, feature/audit, domain/system]
---

# The System Audit & Verification

> The read-only system checks + the tools + the workflow chain.
> The sweep that RUNS them + the delivery + the scrub live in
> [[dev-notes/agents/system-sweep|The System Sweep]].

## The consistency audit (the read)

`ConsistencyAudit` (backend/app/domain/audit/) walks the reference
graph and reports every DANGLING edge — rows pointing at agents,
tools, or workflows that no longer exist:

| Check | What it finds |
|---|---|
| `agent_references` | tool links / usage logs / collection items / chat sessions → missing agent ids |
| `grant_references` | tool grants for missing agents (the `external` pseudo-id is the Exa surface's legit grant — excluded) |
| `collection_items` | collectives holding deleted tools / workflows |
| `orphaned_collections` | empty collectives |
| `workflow_name_references` | workflow configs naming missing agents (the class an id-walk CANNOT catch) |

**READ-ONLY by contract**: it reports; repair is a separate
explicit action (the house rule for destructive transforms).
Defensive: tolerates missing tables (a fresh schema).

**Surfaces:**
- The `audit-consistency` tool (GRAS, `system-diag`) — Exa's
  system check
- `GET /api/v1/system/audit/consistency` — the debug surface

## verify-http-evidence (the claim check)

Given method + path (+ optional since timestamp), search the
access-evidence journal for the matching request — the EVIDENCE
for a claim, not a guess.

**The access-evidence journal** (backend/logs/access.log): a
lightweight middleware (core/access_evidence.py) appends
`method path status timestamp` per request to a ROTATING file
(10MB x 3) — the journal is the tool's robust source, decoupled
from the process lifecycle.

## The workflow chain (the structural verification)

    audit → verify → analyze → report

- **audit**: run the ConsistencyAudit + the integrity checks
  (read-only)
- **verify**: RE-RUN the audit + COMPARE (status + total_findings
  stable) — the READ-BACK, strong evidence (a re-run proves
  reproducibility). Records to the verification store.
- **analyze**: summarize the findings into the report
- **report**: the product lands in the display channel

The verify node is structural: UNATTENDED runs have nobody
watching — verification is a NODE in the graph, not a habit.

**The kind**: `system-audit` (registry.py). Template id
`system-audit`, category `monitoring`.

**The trigger paths:**
1. **The scheduled sweep** — the one-shot ~60s after startup (see
   [[dev-notes/agents/system-sweep|The System Sweep]])
2. **Exa-triggered** — `POST /api/v1/workflows/execute`
   `{"template_id": "system-audit"}`
3. **User-requested** — the same execute endpoint (the template
   is in the workflow library)
