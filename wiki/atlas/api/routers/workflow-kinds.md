---
title: Workflow Kinds
type: atlas-api
path: wiki/atlas/api/routers/workflow-kinds.md
category: api-atlas
order: 20
confidence: high
updated: 2026-08-14
tags: [type/api, domain/workflows, status/active]
---

# Workflow Kinds — API

> Router: `backend/app/api/v1/workflow_kinds_router.py`.

## Purpose

The **kind registry** — the canonical workflow process shapes.
Kinds are CODE-DEFINED (`domain/workflows/kinds/registry.py` — the
source of truth for behavior: builder_key, input schema, product
type); the `workflow_kinds` DB table is a catalog mirror for
browsing.

Kinds are named for the PROCESS, never a persona. Templates (kinds)
are the general shapes; workflows (the `workflow_templates` rows)
are configured instances, each carrying a kind_id (the
classification lives in the `kind_id` column).

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/workflow-kinds` | List kinds — `q` (name/description substring) + `product_type` (report \| file \| index) filters |
| `GET` | `/workflow-kinds/{name}` | One kind: inputs, builder_key, product_type |

## The 8 canonical kinds

monitor · file-processing · batch-orchestration · multi-agent ·
chain · agent-task · context-indexing · simple

## Auth

All endpoints require an authenticated session.

## Related

- [[atlas/api/routers/workflows|Workflows]] — the templates/instances API
- [[dev-notes/workflows/workflow-architecture|Workflow Architecture]]
