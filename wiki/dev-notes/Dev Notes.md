---
title: Dev Notes
type: atlas-index
path: wiki/dev-notes
confidence: stub
updated: 2026-10-12
tags: [type/index, domain/dev-notes]
---

# Dev Notes

Background / architectural knowledge for developers extending or
understanding the system: howtos, flow patterns, pipelines, and
cross-cutting frontend↔backend interplay.

**Boundary with the UI Atlas** (`wiki/atlas/ui/`): the atlas documents
widgets/components; dev-notes document architecture and howtos. When a
topic straddles both (e.g. the Zustand stores — frontend state with
backend backing), stub it here with a `/todo` marker; the exact split
is decided over time.

## Sections

- [[dev-notes/design|Design]] — design philosophy: the why-we-build-
  this-way principles (integration boundaries, enforcement points)
- [[dev-notes/design/research-framework|The Research-Framework
  Identity]] — Cogitate's purpose: the factoring hypothesis (small
  models do the grunt, capable agents orchestrate)
- [[dev-notes/agents|Agents]] — lifecycle, provisioning,
  multi-agent chat, Cognitive Hub
- [[dev-notes/deep-dives|Deep Dives]] — long-form arcs: the narrative,
  the decisions and the reasoning behind a build (not current state, not
  the gotcha register)
- [[dev-notes/macros|Macros]] — macro sets, meta topics,
  export/backup, development workflow
- [[dev-notes/lifecycle|Application Lifecycle]] — what the app does at
  boot, on its own while running (and how to switch it off), and how it
  stops: startup, background work, the shutdown contract
- [[dev-notes/configuration|Configuration]] — settings surface,
  policies, adding a provider
- [[dev-notes/frontend|Frontend]] — title service, attachments,
  collections/teams/toolboxes, the command box
- [[dev-notes/api|API]] — router architecture, field mapping,
  scripts, the capability system (which service answers a call, and the ladder that decides)
- [[dev-notes/tools|Tools]] — tool architecture, error handling,
  troubleshooting
- [[dev-notes/testing|Testing]] — test layout + tool testing
- [[dev-notes/tracing|Tracing]] — trace architecture, langfuse,
  trace stores
- [[dev-notes/workflows|Workflows]] — LangGraph architecture,
  routing, triggers, versioning
- [[dev-notes/assets/agent-images|Agent Images]] — canonical
  home, seed/remap, pixel-fingerprint dedup
- [[dev-notes/system-expertise/System Expertise Index|System Expertise]] — the three-legged knowledge
  pattern the system agents read: the wiki corpus, RAG, the knowledge graph
- [[dev-notes/system-expertise/rag/RAG Index|RAG]] — ingest service, the wiki index, doc index
- [[dev-notes/sessions|Sessions]] — session CRUD
- [[dev-notes/architecture|Architecture]] — zustand FE↔BE patterns
- [[dev-notes/onboarding|Onboarding]] — new-dev pattern guides (stub)
- [[dev-notes/lessons-learned|Lessons Learned]] — what the mypy
  cleanup revealed + potential improvements
- [[dev-notes/known-issues|Known Issues]] — the gotcha register:
  log noise from test sweeps, phantom activity, stale-UI traps,
  two-sources-of-truth drift, loop/tool guards, clone and delegation
  traps (check here first when something surprising shows up)
- [[dev-notes/external-agent/capabilities|Exa Capabilities]] —
  what Exa can/can't do (the QA probe inventory, 2026-08-17)
- [[dev-notes/external-agent/known-issues|Exa Known Issues]] —
  the Exa-reliability issue register (the failure classes + their
  guards + current state)

## Conventions

- **Rewrite-first**: never copy old text; write from the current code.
- **`/todo` marker**: ends a stub section — `> /todo: documentation
  stub — expand later` (frontmatter `confidence: stub`).
- Sources: old `docs/dev_notes/` (topic guide only — migration roadmap
  at local/roadmaps/dev-notes-migration-roadmap.md).
