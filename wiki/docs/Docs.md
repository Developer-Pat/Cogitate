---
title: Docs
type: atlas-index
path: wiki/docs
confidence: high
updated: 2026-11-18
tags: [type/index, domain/docs]
---

# Docs — Operational & Reference Material

Miscellaneous developer/operational documentation that doesn't belong in
the UI Atlas (which documents code) or the help system (which is
user-facing).

## Pages

- [[factsheet-metrics]] — generated project metrics snapshot (file counts,
  LOC, tech stack, DB info)
- [[workflow-catalog]] — system-level LangGraph workflows: the monitor
  family, agent workflows, and the agentic graphs
- [[script-catalog]] — developer script reference (all scripts, usage,
  backend requirements)
- [[testing]] — how to run tests + sweeps (fast/full suite, specific areas)

## Adding content

This area is the catch-all for docs that don't fit elsewhere:
- Frontmatter: `title`, `type: atlas-docs`, `path` (original source),
  `confidence`, `updated`
- Keep wikilinks wiki-root-relative (`[[docs/script-catalog]]`)
- New pages should be linked from this README

## Related

- [[atlas/ui/UI Atlas|UI Atlas]] — code documentation (different purpose)
