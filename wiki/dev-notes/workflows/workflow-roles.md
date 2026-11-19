---
title: Workflow Roles
type: atlas-devnote
category: workflows
order: 8
confidence: high
updated: 2026-09-10
tags: [type/dev-notes, domain/workflows, domain/llm]
---

# Workflow Roles

The cast of a workflow: who reasons, who transforms, who coordinates,
and what happens when the model in front is unavailable. This
vocabulary is normative for new workflows; the code's older names are
listed at the end so the mismatch is not a surprise.

## The cast

| role | what it does | how many | LLM? |
|---|---|---|---|
| **Boss** | the reasoning/review call — sees the whole picture, decides | one per run | yes |
| **Worker** | the transform call — sees one unit, returns one result | one per unit (fan-out) | yes |
| **Orchestrator** | discovery, batching, merging, counting, pacing | one per run | no |

**The LLM lives at the edges.** Everything between the edges is
deterministic code. That is what makes a fan-out inspectable, its output
reproducible, and its cost predictable.

## The chain — the per-role model pick

Each role carries its **own** ordered chain. The first step is the
**starter**; the ones after it are the **bench**, tried in order when the
step ahead fails. Which step actually answered is recorded per call as
`served_by`, so a mixed run stays auditable.

| term | meaning |
|---|---|
| **starter** | the first-choice model for a role |
| **bench** | the ordered alternates behind it |
| **spec** | the named role definition (a pseudo-agent): prompt + chain + sampling params |
| **`served_by`** | the provenance — which chain step answered |

Because the chain is per-role, the Boss can run on a stronger model than
the Workers without either changing.

## Current assignments

| role | spec | starter | bench 1 | bench 2 |
|---|---|---|---|---|
| **Boss** | `tag-boss` | `inclusionai/ling-3.0-flash-sante:free` (OpenRouter, free) | **the Bonsai** — the local 27B Q1_0 at `127.0.0.1:8080` | `deepseek-v4-flash` (direct) |
| **Worker** | `tag-worker` | the same | the same | the same |

Both roles share one chain today, by choice: the free route first, the
always-up local model second, the paid brain last. The local model is a
real fallback, not a placeholder — it has served the extraction
correctly and fast on the batches where the free route 404'd.

## The tag survey's cast

The concrete instance, end to end:

| stage | node | role | LLM? |
|---|---|---|---|
| discover | `tag_discover_node` | orchestrator | no |
| dispatch | `tag_dispatch_node` | orchestrator | no |
| extract | `tag_extract_worker_node` | **Worker** (`tag-worker`) | yes — one call per batch |
| merge | `tag_merge_node` | orchestrator | no |
| consolidate | `boss_node` | **Boss** (`tag-boss`) | yes — one call per run |

## The overloaded word

In the code, **boss** names two different things, which is worth
knowing before following a name into a file:

| the name | what it actually is | LLM? |
|---|---|---|
| `boss_agent_nodes`, `boss_agent_graph` | the **generic fan-out engine** — reused by other workflows | no |
| `boss_dispatch_node`, `boss_merge_node` | the generic **dispatcher / merger** | no |
| `boss_node`, `tag-boss` | the **actual Boss role** | yes |

So the file named for the boss contains no boss. The fan-out machinery
should read as `fanout_*` or `orchestrator_*` — a mechanical rename,
worth doing when those files are next touched, not as work of its own.

"Worker" is similarly spread: `worker_fn` (the pluggable-worker config
key), `worker_meta` (the per-batch provenance), `batch_workers_node` (the
fan-out driver), and `tag_extract_worker_node` (this workflow's worker).
Only the last is a *role*; the rest are plumbing around it.

## Related

- [[dev-notes/workflows/workflow-architecture|Workflow Architecture]] —
  the graph structure and state schema
- [[dev-notes/lessons-learned/llm-fallback-chains|LLM Fallback Chains]]
  — the rules the chains follow
- [[dev-notes/lessons-learned/running-a-workflow|Running a Workflow]] —
  the operational rules for driving one
- [[atlas/workflows/tag-survey-fanout|The Tag-Survey Fan-Out]] — the
  first consumer
