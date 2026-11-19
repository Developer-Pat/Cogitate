---
title: Workflow Product Distribution
type: atlas-devnote
category: workflows
order: 7
confidence: high
created: 2026-08-10
updated: 2026-08-10
tags: [type/dev-notes, domain/workflows]
---

# Workflow Product Distribution

> How workflow **products** (digests, alerts, reports) get from a
> workflow run to a consumer — the delivery layer. A configurable
> pipeline pattern (ABC → Registry → factory), the same shape as
> the tool registry.

## The idea

A run's output leaves through **channels** — a delivery layer, not
a write inside the node that produced the product:

```
Workflow product (digest, alert, report)
        │
        ▼
WorkflowProduct (packaging contract — type, title, body,
                 source, created_at, path, meta)
        │
        ▼
  FileDistributor    → writes data/monitor/<type>-<date>.md
  DisplayDistributor → registers in products.json (display index)
```

## Architecture (the pipeline pattern)

- `app/workflows/distribution/models.py` — `WorkflowProduct` +
  `DeliveryResult` (never-raises contract)
- `app/workflows/distribution/distributors.py` — `WorkflowDistributor`
  ABC + `FileDistributor` + `DisplayDistributor` +
  `create_default_distributors()` factory + `deliver_product()`
- New channels = new distributor classes — **no node changes**

## Design decisions

- **No Aggregator ABC.** The `WorkflowProduct` dataclass IS the packaging contract and the execution
  records already hold the output; a one-implementation ABC is ceremony. An aggregator earns its keep
  when a second aggregation source appears (an agent-as-product, say).
- **Product shape**: type / title / body (markdown) / source_template / created_at (Z) / path / meta.
- **Selection**: a run's config JSON may declare `distributors: ["file", "display"]`. A run that
  declares none gets the **default set** — file, display and toast — not every registered channel.
- **The display page polls**: `/workflow-products` reads the index via
  `GET /api/v1/workflows/products`. There is no push infrastructure behind it.

## The products

| product_type | Workflow | Where |
|---|---|---|
| `rss_digest` | rss-monitor | `data/monitor/rss-digest-*.md` |
| `market_alert` | market-watch | `data/monitor/market-*.md` |
| `readiness_report` | readiness-check | `data/monitor/readiness-*.md` |

## Channels

| Channel | Distributor | Delivery |
|---|---|---|
| File | `FileDistributor` | markdown to `data/monitor/` |
| Display | `DisplayDistributor` | products.json index → Products page |
| **Toast** | `ToastDistributor` | toasts.json queue → app-wide in-app toasts (`useWorkflowToasts` polls in the app shell, localStorage cursor dedup) |
| Email / SMS | — | not built — they need external infrastructure |
| **Agent** | `AgentDistributor` | hands a product to an **addressed agent** (`product.meta["recipient_agent"]`, registry identity): *file-it* into `agents/<name>/inbox/`, or *hand-it-a-task* by posting the body into the agent's chat session. An unknown name fails loudly (dead-letter, not a hang). **Not in the default set** — opt in with `"distributors": ["agent"]` |

Default distributor set: `file + display + toast` (triggers ship
deactivated → toasts only fire on manual runs).

The display index (`data/monitor/products.json`) holds the newest
100, newest-first, with a 2000-char body preview — enough for the
list; the file has the full product.

## Backend

- `GET /api/v1/workflows/products?limit=N` — the display index
- Deliver nodes (`rss_deliver_node`, `market_deliver_node`,
  `readiness_deliver_node`) package a `WorkflowProduct` and call
  `deliver_product(product, names=_distributor_names(state))`

## Frontend

- `/workflow-products` page (nav: Workflows → Products): type
  badges, expandable bodies, refresh. Reads the index endpoint.

## Clearing and pruning

- `clear_products()` — deletes product files + the display index
  (keeps `state.json` — monitor dedup state, not a product);
  exposed as `DELETE /api/v1/workflows/products`; the Products
  page's Clear action (confirmation modal, Session-delete pattern)
- `prune_executions(retention_days=30)` — was dead code, now wired
  as the **retention surface** — `GET/PUT /api/v1/workflows/retention` (the policy: rows +
  their checkpoint journals, the debug snapshots, the abandoned grace) and
  `POST /api/v1/workflows/retention/prune` (preview by default; `confirm=true` to apply)
- `delete_product(product_id)` — per-item delete + selection is LANDED on both
  sides: `DELETE /api/v1/workflows/products/{product_id}` behind it, and the
  Products page's selection + delete confirm in front of it

## Verification

- 20 distribution tests (`backend/tests/workflows/test_distribution.py`):
  file write + path, never-raises, index newest-first + capped,
  factory shape, named/default/unknown distributor selection,
  deliver nodes use the layer, clear_products keeps state.json
- LIVE-VERIFIED: readiness run → file + products.json + API +
  page all show the product; Clear → confirmation → 0 products

## Related

- [[dev-notes/workflows/monitor-family|Monitor Workflow Family]] — where the products come from
- [[atlas/api/routers/workflows|Workflows API]] — the products endpoint
- [[dev-notes/configuration/database-topology|Database Topology]] — where data lives
