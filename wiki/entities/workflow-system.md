---
title: Workflow System
type: atlas-entity
path: wiki/entities/workflow-system.md
confidence: medium
updated: 2026-11-18
tags: [type/entity, domain/entities]
---

# Workflow System

## Overview

**LangGraph workflows** (backend/app/workflows/): graphs under
graphs/, nodes under nodes/, state in state/workflow_state.py.
A kind resolves to its graph through `KIND_GRAPH_FACTORIES` in
`app/domain/workflows/kinds/registry.py` (lazy imports).

## Dispatch

A workflow is resolved by name — the kind or template name — to its
compiled graph; results return as structured data.

## Supporting systems

- **Triggers**: event_router, scheduler, webhook_handler.
- **Checkpointing**: checkpointing/config.py.
- **Agent versioning + A/B testing**: agent_versioning/ (registry,
  ab_testing, api/router).
- **Observability**: trace_store (ring buffer) + langfuse_config.
- **API**: workflow_router, composition_router, triggers_router,
  webhooks_router, approval_router, multi_agent_router,
  template_router.
- **Monitor family**: rss-monitor + market-watch +
  readiness-check templates — the first real user-facing workflows
  (graphs/monitor_graph.py, nodes/monitor_nodes.py, seeded by
  scripts/core/seed_monitor_templates.py). Cross-run dedup state
  in data/monitor/state.json (not checkpoint state — fresh thread
  per fire). Readiness reuses RunPostTool (asyncio.run bridge —
  graph router invokes sync).

See [[dev-notes/workflows/workflow-architecture]] for the full
picture.
