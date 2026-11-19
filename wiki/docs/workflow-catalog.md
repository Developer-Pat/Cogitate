---
title: Workflow Catalog
type: atlas-docs
path: wiki/docs/workflow-catalog.md
confidence: medium
updated: 2026-11-18
tags: [type/docs, domain/docs]
---

# Workflow Catalog — System-Level Workflows

**Purpose:** Quick reference for all system-level LangGraph workflows.
System-level workflows are built and maintained as infrastructure for the agent system to execute structured operations deterministically.

---

## Overview

| Category | Description | Count |
|----------|-------------|-------|
| Macro Workflows | Not LangGraph workflows: the macro manager + `/api/v1/macros/` handle them (see 1) | 0 |
| [Agent Workflows](#2-agent-workflows) | Agent lifecycle management | 2 |
| [Document Workflows](#3-document-workflows) | Document CRUD | 0 (planned) |

---

## 1. Macro workflows

Macro operations are handled directly by the macro manager tool +
the `/api/v1/macros/` REST surface (list, meta-topics,
export/import, templates) — not by LangGraph workflows.

## 2. Agent Workflows (System-Level)

Agent lifecycle management is handled by the agents domain — the
repository seam + the recoverable delete (see
[[dev-notes/agents/agent-lifecycle|Agent Lifecycle]]) — not by
LangGraph workflows. Agent-facing automation (the recipient
channel) goes through the AgentDistributor; see
[[atlas/api/routers/agents|Agents API]].

---

## 3. Frontend/Agentic Workflows (Separate)

These workflows exist but are part of the frontend agent system,
not the system-level operation layer:

| File | Purpose |
|------|---------|
| `multi_agent_graph.py` | Multi-agent orchestration |
| `boss_agent_graph.py` | Batch orchestration delegation graph |
| `agent_workflows.py` | General agent interaction workflows |
| `composition_graph.py` | Workflow composition graphs |
| `file_clerk_graph.py` | File management agent |
| `context_indexer_graph.py` | Document indexing agent |
| `advanced_workflow.py` | Advanced workflow patterns |
| `default_provider_test_graphs.py` | Provider testing graphs |
| `simple_workflow.py` | Simple planner/executor demo |

---

## 4. Monitor Workflow Family (System-Level)

Monitor → analyze → report at different cadences; the cadence IS
the testability (hourly and 5-min fires verify in-session).

**Delivery:** products (digests, alerts, reports) go through the
distribution layer — [[dev-notes/workflows/product-distribution|Workflow Product Distribution]]:
each run packages a `WorkflowProduct` and delivers via the
distributor registry (file → `data/monitor/*.md`, display →
`products.json` → the Workflow Products page).

| Template | Cadence | Graph | What it does |
|----------|---------|-------|--------------|
| `rss-monitor` | hourly (cron `0 * * * *`) | `graphs/monitor_graph.py` → `rss_monitor` | Fetch configured RSS feeds (XML parse, no key), dedup via `data/monitor/state.json`, summarize via summarize-llm (plain-text fallback — never blocks on LLM), write digest to `data/monitor/rss-digest-<date>.md` |
| `market-watch` | 5-min (cron `*/5 * * * *`) | `graphs/monitor_graph.py` → `market_watch` | Fetch keyless crypto price (CoinGecko simple price), compare vs last price (threshold/trend), write alert to `data/monitor/market-<date>.md` |
| `readiness-check` | manual (TestingDashboard) | `graphs/monitor_graph.py` → `readiness_check` | First-run readiness report: POST health suite (5 checks) + providers/env-keys + agents/curated-models → `data/monitor/readiness-<date>.md` |

**Key design fact:** cross-run state ("last seen" / "last price")
lives in `data/monitor/state.json`, NOT LangGraph checkpoint
state — each trigger fire creates a fresh `wf-<uuid>` thread, so
checkpoint state is per-thread and cannot carry last_seen.
Persistent cross-run state belongs in a file (or DB), not the
journal.

**Nodes:** `nodes/monitor_nodes.py` (rss_fetch, rss_summarize,
rss_deliver, market_fetch, market_deliver). Error-resilient by
design: a dead feed/API records an error but never fails the run.

**Seed:** `python3 scripts/core/seed_monitor_templates.py`
(idempotent — inserts templates + triggers if missing).

**Tests:** `backend/tests/workflows/test_monitor_family.py` (11).

---

## Adding a New Workflow

1. Create the workflow file in `backend/app/workflows/graphs/`
2. Define state dataclass, node functions, and graph factory
3. Declare the kind in `backend/app/domain/workflows/kinds/registry.py` —
   `KIND_REGISTRY` (its `builder_key`) and `KIND_GRAPH_FACTORIES`
   (`kind: (module, factory)`)
4. Make the `workflow_kinds` row carry the same `builder_key`
5. Add entry to this catalog

See `backend/app/workflows/graphs/` existing graphs (e.g. `advanced_workflow.py`) for the reference pattern.
