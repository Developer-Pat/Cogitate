---
title: Dynamic Agent Routing
type: atlas-devnote
category: workflows
order: 2
confidence: stub
updated: 2026-08-05
tags: [type/dev-notes, domain/workflows]
---

# Dynamic Agent Routing

How requests are classified and routed to the right agent/workflow.

## Current shape

- **Kind → graph factories** — `app/domain/workflows/kinds/registry.py`:
  `KIND_GRAPH_FACTORIES` maps a kind name to `(module, factory)`, resolved
  lazily by `resolve_kind_graph_factory()` so the module is imported on demand.
- **Kinds** — `KIND_REGISTRY` declares each kind; the `workflow_kinds` table
  carries the same builder as its `builder_key`.
- **Per-template routing** — `app/workflows/api/workflow_router.py` keeps the
  template table for kinds whose graph varies per template (`test-llm-*`,
  `rss-monitor`, `agent-hello`); kinds with one generic graph do not use it.
- **router_node.py / classifier_node.py** (workflows/nodes/) implement routing
  decisions inside graphs.
- conduit-routing (wiki/entities/conduit-routing.md) decides how each message is
  processed at the chat layer.

## Routing decision tree

Workflow routing is **name-based** (the caller selects the kind or template
name), not a learned classifier:

- `KIND_GRAPH_FACTORIES[kind]` → `(module, factory)`, imported lazily and called
- `workflow_kinds.builder_key` names that same builder in the database
- the workflow router's template table covers the per-template kinds
