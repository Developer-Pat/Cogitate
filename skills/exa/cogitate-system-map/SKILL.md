---
name: cogitate-system-map
description: "The Cogitate system's topology — what agents, workflows, triggers, tools, and monitors exist and where to look. Use when asked about the system's structure, what is configured, or where things live."
version: 1.0.0
author: Cogitate Team
tags: [cogitate, topology, system-map, agents, workflows]
---

# Cogitate System Map

The authoritative live topology is the DATABASE — do not enumerate
files by hand. The system's entities and their relationships are
rows in `cogitate.db` with foreign keys connecting them.

## Where the truth lives

- **Agents** — the `agents` table (12 active after the System
  Manager retirement 2026-08-19 — Exa is the system agent now;
  each agent has a workspace dir under `agents/<name>/` + a
  `cognitive_memory.db`). The agent lifecycle, through the
  KEYED tools (never by editing the DB directly):
  - **list-archived-agents** (READ) — the soft-deleted agents
    (id, name, archive folder); the /agents/deleted API's data
  - **delete-agent** with `hard: false` — DEACTIVATE + archive
    (RECOVERABLE — the undo exists)
  - **restore-agent** (keyed) — the UNDO: the archived workspace
    moves back, the profile returns to the pool (verified)
  - **delete-agent** with `hard: true` — PERMANENT SCRUB
    (IRREVERSIBLE — nothing restores it; only with explicit
    user confirmation)
- **Workflow templates** — `workflow_templates` (33 seeds + user
  templates; each is a kind/process shape with concrete params).
- **Triggers** — `workflow_triggers` (schedules + webhooks; the
  monitor triggers are `monitor-rss-hourly`, `monitor-market-5min`).
- **Tools** — the tool registry (29 builtins; capability +
  access_tier declared; the canonical vocabulary is frozen in
  `backend/app/domain/tools/capabilities.py`).
- **Monitors** — the monitor family: rss-monitor (Ars Technica +
  Hacker News feeds, hourly), market-watch (5-min price checks),
  readiness-check. Dedup state lives in `data/monitor/state.json`.
- **Products** — workflow deliveries (digests, alerts, reports) in
  the products index + `data/monitor/`.

## How to answer topology questions

1. Query the DB via the API (`GET /api/v1/workflows/templates`,
   `GET /api/v1/triggers`, `GET /api/v1/agents`) — the live truth.
2. For relationships, call the graph-query tool (the topology
   service: the derived FK walk + the wiki link graph) — it
   returns the verified edges for any entity ('what fires this
   workflow', 'what does this agent depend on').
3. When the question is "how does X connect to Y", graph-query
   answers it: agents→tools (agent_tools), templates→triggers
   (workflow_triggers.workflow_id), executions→compositions.

## Boundary

This is a MAP — read-only. Changes go through the write APIs
(triggers, templates, agents), never by editing the DB directly.
