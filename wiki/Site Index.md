---
title: Site Index
type: wiki-index
path: wiki/Site Index.md
confidence: high
created: 2026-07-27
updated: 2026-08-07
tags: [type/index]
---

# Site Index

## Navigation

| Page | Type | Confidence | Description |
|------|------|------------|-------------|
| [[backend-architecture]] | entity | high | Backend app structure, router layers, dependency injection |
| [[agent-orchestration]] | entity | high | Agent registry, cognitive pipeline, conduit routing |
| [[memory-system]] | entity | high | KVStoreMemoryManager, fact storage, per-agent DBs |
| [[provider-management]] | entity | high | Provider registry, model caching, credential pooling |
| [[tool-system]] | entity | high | Tool registry, tool handlers, agent-tool linking |
| [[chat-system]] | entity | high | Stream handling, session management, SSE protocol |
| [[concepts/cognitive-profiles|cognitive-profiles]] | concept | high | Profile naming convention, part codes, catalogue |
| [[frontend-architecture]] | entity | medium | Component tree, stores, routing, key views |
| [[database-schema]] | entity | medium | Core tables, migration patterns, session storage |
| [[configuration]] | entity | medium | Config surface, env vars, defaults |
| [[workflow-system]] | entity | medium | Macro system, workflow composition |
| [[conduit-routing]] | concept | high | How messages are routed between agents |

## UI Atlas (Developer Docs)

| Section | Type | Description |
|---------|------|-------------|
| [[atlas/ui/UI Atlas|UI Atlas]] | index | Master index of developer docs |
| [[atlas/ui/pages|Pages]] | atlas-index | All 28 page components |
| [[atlas/ui/components|Components]] | atlas-index | Reusable components by feature area |
| [[atlas/ui/hooks|Hooks]] | atlas-index | Custom React hooks |
| [[atlas/ui/services|Services]] | atlas-index | API and domain services |
| [[atlas/ui/stores|Stores]] | atlas-index | Zustand stores |
| [[atlas/ui/architecture|Architecture]] | atlas-index | Deep-dive architecture docs (Mermaid diagrams) |
| [[docs|Docs]] | atlas-index | Operational & reference docs (system, testing, catalogs) |

## Dev Notes (Developer Docs)

| Page | Category | Description |
|------|----------|-------------|
| [[dev-notes|Dev Notes]] | index | Architecture, howtos, pipelines: the long-form developer knowledge tree |
| [[dev-notes/system-expertise/System Expertise Index|System Expertise]] | system-expertise | The three-legged knowledge pattern the system agents read: the wiki corpus · RAG · the knowledge graph |
| [[dev-notes/workflows/monitor-family|Monitor Workflow Family]] | monitor-family | The 3 automated monitors: RSS news digest, market watch, readiness check |
| [[dev-notes/workflows/examples/rss-monitor|RSS News Monitor (example)]] | monitor-example | Hourly news digest — what it does, real output, how to run it |
| [[dev-notes/workflows/examples/market-watch|Market Watch (example)]] | monitor-example | 5-minute price tripwire — quiet vs alert output |
| [[dev-notes/workflows/examples/readiness-check|Readiness Check (example)]] | monitor-example | "Is my instance ready?" — the 5/5 report |

## Help

| Page | Category | Description |
|------|----------|-------------|
| [[help/chat|chat]] | chat | Sending messages, session requirements |
| [[agent-profiles]] | agents | Profile management |
| [[help/macros|macros]] | macros | Macro sets, meta-topics, F-keys |
| [[help/sessions|sessions]] | sessions | Session management |
| [[help/settings|settings]] | settings | Application settings |
| [[help/tools|tools]] | tools | Tool management |
| [[help/dashboard|dashboard]] | dashboard | Dashboard overview |
| [[help/providers|providers]] | providers | Provider configuration |
| [[help/workflows|workflows]] | workflows | Workflow templates & execution |
| [[help/logs|logs]] | logs | Log viewing & analysis |
| [[help/cognitive-pipeline|cognitive-pipeline]] | cognitive-pipeline | Pipeline configuration |
| [[search]] | search | The nav sidebar's command box — what to type, and where each verb lands |

## Issues

Problem records for the developer: what is wrong, the evidence, the options, the ruling that closes
it. Read while working, not filed away.

[[issues|Issues]] — the section: how a page is written, and why this is the history surface. **Open
pages sit at the top of it; resolved ones move under `resolved/<arc>/`.** The section index carries
each page's status; it is the only place a status is repeated, so it is not repeated here.

## Orphaned Pages

Pages that exist but aren't linked from here yet — will be integrated as the wiki grows.


## Diagrams

| Diagram | File | Description |
|---------|------|-------------|
| [System Architecture](diagrams/system-architecture.html) | `diagrams/system-architecture.html` | Full-stack system overview |
| [Agent Pipeline Flow](diagrams/agent-pipeline-flow.html) | `diagrams/agent-pipeline-flow.html` | Cognitive pipeline message flow |
| [Memory Architecture](diagrams/memory-architecture.html) | `diagrams/memory-architecture.html` | KVStore, per-agent DBs, facts |
