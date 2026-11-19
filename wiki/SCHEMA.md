---
title: Wiki Schema
confidence: high
created: 2026-07-27
tags: [domain/root]
---

# Wiki Schema — Conventions & Frontmatter

## Directory Structure

```
wiki/
├── atlas/           # The living map — api/, services/, ui/, workflows/
│                    # (the atlas pages: current-state, navigable)
├── dev-notes/       # The engineering notes — agents/, api/, design/,
│                    # frontend/, macros/ + the cross-cutting notes
├── entities/        # Concrete components — services, classes, files
├── concepts/        # Abstract ideas — patterns, protocols, principles
├── comparisons/     # Side-by-side comparisons of related components
├── raw/             # Immutable snapshots of design docs/decisions
├── references/      # External references, links, glossaries
├── diagrams/        # The visual diagrams (SVG sources)
├── display-tests/   # The render-test pages (the UI atlas's fixtures)
├── docs/            # The legacy pre-atlas pages (being absorbed)
├── help/            # The end-user help pages
├── scripts/         # The wiki tooling scripts
├── _archive/        # Deprecated or replaced pages
├── SCHEMA.md        # This file
└── log.md           # Timestamped audit trail of every action
```

## Frontmatter

Every page starts with YAML frontmatter:

```yaml
---
title: Page Title
confidence: high|medium|low
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [type/howto, domain/workflows]
---
```

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `title` | Yes | Human-readable page title |
| `confidence` | Yes | `high` = well-established, `medium` = partially verified, `low` = speculative |
| `created` | Yes | Date first written |
| `updated` | Yes | Date last modified |
| `tags` | No | Space-separated keywords; the wiki PRACTICES a two-axis taxonomy: `type/*` (page kind — type/index, type/howto, type/study, type/feasibility...) and `domain/*` (subject area — domain/dev-notes, domain/workflows, domain/deep-agents...). Most pages carry BOTH (a kind + a subject). See the tag-layer refinement work for the consolidation plan. |

## Wikilinks

Reference other wiki pages with double-bracket syntax:

- `[[entity-name]]` — links to `entities/entity-name.md`
- `[[concept-name]]` — links to `concepts/concept-name.md`

The file path is derived from the title (lowercase, hyphens). The index.md maps titles to paths.

## Confidence Policy

- **high**: Verified against live code, architecturally stable
- **medium**: Partially verified or subject to change
- **low**: Speculative, needs review, or based on stale information

Pages with `confidence: low` should be treated as unreliable. Pages with `confidence: high` can be cited as fact.

## Page Thresholds

Create a page when:
- A component appears in 2+ sources or is architecturally central
- A design decision has trade-offs worth documenting
- A pattern is used in multiple places

Do NOT create pages for:
- Implementation trivia that changes constantly
- Passing mentions in code comments
- Config keys that are self-documenting
