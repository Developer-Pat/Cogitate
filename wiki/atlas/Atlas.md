---
title: Atlas
type: atlas-index
path: wiki/atlas
confidence: medium
updated: 2026-08-07
tags: [type/index]
---

# Atlas — the collated knowledge maps

One home for the atlas family: the collated views of the application.
Each atlas documents a layer; together they are the map of the system.

## Sub-atlases

- [[atlas/ui/UI Atlas|UI Atlas]] — the frontend: widgets, components,
  pages, stores, and services
- [[atlas/api/API Atlas|API Atlas]] — the backend endpoints, plus the
  [[atlas/services/README|Services map]] (per-domain service tables
  with dependency diagrams) and [[atlas/api/cross-cutting|Cross-cutting]]
- **Services Atlas** — the services map pages above (per-domain
  service tables + mermaid dependency diagrams)

## Status legend (shared)

Every facility in the atlases carries a `status/<verdict>` tag —
the pruning picture, colorable in the Obsidian graph:

| Status | Meaning | Action |
|--------|---------|--------|
| `active` | used by UI/agents, tested | keep |
| `dormant` | core purpose, un-expanded | keep; document |
| `superseded` | replaced by newer facility | decide |
| `orphaned` | no consumers, no purpose | remove |
| `dead` | no callers/data/tests | remove |
| `legacy-data` | data only, facility gone | migrate/archive |

## Conventions

- Frontmatter: `type: atlas-ui` / `atlas-api` / `atlas-index` +
  `title`, `path`, `category`, `confidence`, `updated`
- Tags (Obsidian testbed, trimmed 2026-08-07): flow-style single
  line — `tags: [type/<t>, domain/<n>]`; `status/<v>` added only
  when a real verdict exists (active/dormant/orphaned/dead...).
  Confidence is a property, not a tag (it misted the graph).
- Validator: every atlas/ doc carries the full frontmatter contract;
  atlas/api additionally requires `tags:`
- Mermaid diagrams render in-wiki (theme-aware); SVG reserved for
  hero maps (sparing use decision)

## State map — facility status (the pruning picture)

Every API facility with its audit verdict. This is the summary
table for pre-launch pruning decisions (full audit: `local/roadmaps/
pre-launch-pruning-roadmap.md`).

| Facility | Status | Notes |
|----------|--------|-------|
| Providers API + services | `active` | core infrastructure |
| Agents API + services | `active` | core |
| Tools API + services | `active` | core (30+ builtin tools) |
| Workflows (execution/routing/triggers/approvals) | `active` | core purpose |
| **Versions + A/B testing** | `dormant` | core purpose, un-expanded; demo data kept as test material |
| Chat / Agent-chat / Cognitive / Logs / Macros | `active` | everyday + core |
| Sessions / Teams / Collections / Lists / Wiki | `active` | platform |
| Debug / Diagnostics | `active` | dev tooling (Debugging page) |
| (cheat-sheets API) | — | removed — see history |
| (legacy skills) | — | removed — see history |

## Build status

- UI Atlas: complete (widget/component documentation)
- API Atlas: **COMPLETE** — 35 router pages annotated + services
  map (6 families) + cross-cutting. Roadmap:
  `local/roadmaps/api-atlas-build-roadmap.md`

## Messaging

- [[atlas/messaging/Message map|Message Map]] — the messaging
  infrastructure: the bus, the SSE stream, the topics' catalog
  (publishers + subscribers + payloads), the wire-flows, the
  dead-wire checks.
