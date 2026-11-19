---
title: API Atlas
type: atlas-index
path: wiki/atlas/api
confidence: stub
updated: 2026-08-07
tags: [type/api]
---

# API Atlas

The API Atlas documents the Cogitate backend: the HTTP endpoints
and WebSocket routes, organized by domain, plus the services behind
them. Each router page lists its endpoints with what they do; each
service page describes the domain logic and its dependencies. The
status tags (active / dormant / superseded / orphaned) show which
facilities are in use.

## Status legend

Every facility carries a `status/<verdict>` tag (Obsidian-graph
colorable — the pruning picture):

| Status | Meaning | Action |
|--------|---------|--------|
| `active` | used by UI/agents, tested | keep |
| `dormant` | core purpose, un-expanded | keep; document |
| `superseded` | replaced by newer facility | decide |
| `orphaned` | no consumers, no purpose | remove |
| `dead` | no callers/data/tests | remove |
| `legacy-data` | data only, facility gone | migrate/archive |

## Routers

- [[atlas/api/routers/providers|Providers]] — provider config, keys, health
- [[atlas/api/routers/agents|Agents]] — CRUD, templates, provisioning
- [[atlas/api/routers/images|Images]] — image-asset store (list/upload/delete/import/export)
- [[atlas/api/routers/external-agent|External Agent]] — ACP panel backend (config/status/restart + WebSocket bridge)
- [[atlas/api/routers/messaging|Messaging]] — the event bus + the SSE stream (the pub-sub transport; the Boss-Batching pipeline is one consumer)
- [[atlas/api/routers/testing|Testing]] — the user-testing page: the derived catalog, the runs on disk, the live event stream, and one run started/stopped/retired under the runner's lock
- [[atlas/api/routers/trash|Trash]] — the shelf registry's one surface: every shelf listed, read, restored, purged and emptied
## Services map

Each domain has a service page in [[atlas/services|Services]] with
its responsibilities + dependency diagram.

## Cross-cutting

Auth model, SSE endpoints, the cognitive-pipeline chain, and the
workflow services span the domains — see
[[atlas/api/cross-cutting|Cross-cutting]].

## Tags (Obsidian testbed)

Every page carries `tags: [type/api, domain/<n>, status/<v>,
confidence/<l>]` — flow-style so the wiki's line-based frontmatter
parser passes them through. Obsidian reads them natively; the
`status/*` tag colors the vault graph by facility health.
